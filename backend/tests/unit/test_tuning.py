"""Unit tests for SAR hyperparameter search and validation isolation (P3.8)."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

from engine.config import load_config
from engine.evaluation.metrics import hit_rate, ndcg, recall
from engine.models.baselines import RandomModel
from engine.models.sar import SarModel
from engine.tuning import tune_sar_on_validation

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tuning_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create train, valid, items DataFrames for tuning tests."""
    catalogue = [f"movie_{i}" for i in range(1, 21)]
    items = pd.DataFrame(
        [{"item_id": m, "title": f"Movie {m}", "categories": ["Drama"]} for m in catalogue]
    )

    train_rows = []
    valid_rows = []
    for u in range(1, 15):
        uid = f"user_{u}"
        for step in range(1, 7):
            train_rows.append(
                {
                    "user_id": uid,
                    "item_id": f"movie_{((u * 3 + step) % 20) + 1}",
                    "signal": 5.0 if step % 2 == 0 else 3.0,
                    "timestamp": 1000 + step * 10,
                    "positive": True,
                }
            )
        # Validation interaction
        valid_rows.append(
            {
                "user_id": uid,
                "item_id": f"movie_{((u * 3 + 7) % 20) + 1}",
                "signal": 5.0,
                "timestamp": 2000,
                "positive": True,
            }
        )

    return pd.DataFrame(train_rows), pd.DataFrame(valid_rows), items


def test_tuning_validation_only_and_schema(
    tuning_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    tmp_path: Path,
) -> None:
    """Verify tune_sar_on_validation records split_used as validation, includes top_neighbors_per_item, and selects best."""
    train_df, valid_df, items = tuning_fixture
    spec = load_config("movies", fast=True)

    grid = [
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 20,
        },
        {
            "similarity_type": "lift",
            "timedecay_formula": False,
            "time_decay_coefficient": None,
            "positive_threshold": 3.5,
            "top_neighbors_per_item": 50,
        },
    ]

    out_file = tmp_path / "tuning.json"
    results = tune_sar_on_validation(
        spec=spec,
        train_df=train_df,
        valid_df=valid_df,
        items=items,
        grid=grid,
        max_eval_users=50,
        output_path=out_file,
    )

    assert out_file.exists()
    assert results["selection_metric"] == "ndcg@10"
    assert results["selection_split"] == "validation"
    assert results["best_trial_id"] in [1, 2]
    assert "top_neighbors_per_item" in results["best_params"]

    for trial in results["trials"]:
        assert trial["split_used"] == "validation"
        assert "top_neighbors_per_item" in trial["params"]
        assert "ndcg@10" in trial["validation_metrics"]
        assert "recall@10" in trial["validation_metrics"]


def test_test_split_strictly_isolated_from_tuning_interface() -> None:
    """Verify tune_sar_on_validation structurally rejects test split input."""
    sig = inspect.signature(tune_sar_on_validation)
    params = list(sig.parameters.keys())
    assert "test_df" not in params, "tune_sar_on_validation must not accept test_df parameter"
    assert "test_interactions" not in params


def test_shuffled_label_sanity_test_near_random(
    tuning_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Sanity test: training SAR on shuffled user-item pairs degrades near Random."""
    train_df, valid_df, items = tuning_fixture
    spec = load_config("movies", fast=True)

    # 1. Genuine SAR
    model_genuine = SarModel(spec)
    model_genuine.fit(train_df, items)

    # 2. Shuffled SAR (permute item_id across training interactions)
    rng = np.random.RandomState(42)
    shuffled_train = train_df.copy()
    shuffled_train["item_id"] = rng.permutation(shuffled_train["item_id"].values)
    model_shuffled = SarModel(spec)
    model_shuffled.fit(shuffled_train, items)

    # 3. Random baseline
    model_random = RandomModel(spec, seed=42)
    model_random.fit(train_df, items)

    eval_users = list(valid_df["user_id"].unique())
    preds_genuine = []
    preds_shuffled = []
    preds_random = []

    for uid in eval_users:
        for r in model_genuine.recommend_user(uid, k=10):
            preds_genuine.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )
        for r in model_shuffled.recommend_user(uid, k=10):
            preds_shuffled.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )
        for r in model_random.recommend_user(uid, k=10):
            preds_random.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )

    pos_valid = valid_df[valid_df["signal"] >= spec.signal.positive_threshold]
    df_genuine = pd.DataFrame(preds_genuine)
    df_shuffled = pd.DataFrame(preds_shuffled)
    df_random = pd.DataFrame(preds_random)

    # 1. NDCG@10
    ndcg_genuine = ndcg(pos_valid, df_genuine, k=10)
    ndcg_shuffled = ndcg(pos_valid, df_shuffled, k=10)
    ndcg_random = ndcg(pos_valid, df_random, k=10)
    assert ndcg_genuine > 2 * ndcg_shuffled, (
        f"NDCG@10 did not collapse: genuine={ndcg_genuine:.4f}, shuffled={ndcg_shuffled:.4f}"
    )
    assert abs(ndcg_shuffled - ndcg_random) < 0.15, (
        f"NDCG@10 shuffled not near random: shuffled={ndcg_shuffled:.4f}, random={ndcg_random:.4f}"
    )

    # 2. HitRate@10
    hr_genuine = hit_rate(pos_valid, df_genuine, k=10)
    hr_shuffled = hit_rate(pos_valid, df_shuffled, k=10)
    hr_random = hit_rate(pos_valid, df_random, k=10)
    assert hr_genuine >= hr_shuffled, (
        f"HitRate@10 did not degrade: genuine={hr_genuine:.4f}, shuffled={hr_shuffled:.4f}"
    )
    assert abs(hr_shuffled - hr_random) < 0.25, (
        f"HitRate@10 shuffled not near random: shuffled={hr_shuffled:.4f}, random={hr_random:.4f}"
    )

    # 3. Recall@10
    rec_genuine = recall(pos_valid, df_genuine, k=10)
    rec_shuffled = recall(pos_valid, df_shuffled, k=10)
    rec_random = recall(pos_valid, df_random, k=10)
    assert rec_genuine >= rec_shuffled, (
        f"Recall@10 did not degrade: genuine={rec_genuine:.4f}, shuffled={rec_shuffled:.4f}"
    )
    assert abs(rec_shuffled - rec_random) < 0.25, (
        f"Recall@10 shuffled not near random: shuffled={rec_shuffled:.4f}, random={rec_random:.4f}"
    )
