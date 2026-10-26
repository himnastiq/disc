"""Golden-file regression test for MovieLens 100K fast pipeline (P3.12).

Tests top-5 recommendations for 3 fixed users ('1', '2', '3') and key metrics
against recorded golden values within numerical tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.config import load_config
from engine.registry import build_model
from engine.train import run_pipeline


@pytest.mark.integration
@pytest.mark.real_data
def test_movies_100k_golden_regression(tmp_path: Path) -> None:
    """Execute fast pipeline on 100K and assert recommendations and metrics match golden values."""
    golden_path = Path(__file__).resolve().parent.parent / "fixtures" / "golden_movies_100k.json"
    assert golden_path.exists(), f"Golden file not found at {golden_path}"

    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)

    # Execute pipeline with fixed seed into isolated tmp_path
    metrics = run_pipeline(
        content_type="movies",
        fast=True,
        seed=golden["seed"],
        artifacts_dir=tmp_path,
    )

    # 1. Verify model output for 3 fixed users against golden values
    spec = load_config("movies", fast=True)
    model = build_model(spec)
    model_dir = tmp_path / "model"
    assert model_dir.exists()
    model.load(model_dir)

    for user_id, expected_recs in golden["users"].items():
        recs = model.recommend_user(user_id=user_id, k=5)
        assert len(recs) == 5, f"Expected 5 recommendations for user {user_id}, got {len(recs)}"

        for actual, expected in zip(recs, expected_recs, strict=True):
            assert actual.rank == expected["rank"]
            assert actual.item_id == expected["item_id"], (
                f"User {user_id} rank {actual.rank} mismatch: got {actual.item_id}, "
                f"expected {expected['item_id']}"
            )
            assert actual.score == pytest.approx(expected["score"], abs=1e-3), (
                f"User {user_id} rank {actual.rank} score mismatch: got {actual.score}, "
                f"expected {expected['score']}"
            )

    # 2. Verify topn.parquet precomputed recommendations match for these users
    topn_path = tmp_path / "topn.parquet"
    assert topn_path.exists()
    topn_df = pd.read_parquet(topn_path)
    for user_id, expected_recs in golden["users"].items():
        user_topn = topn_df[topn_df["user_id"] == user_id].sort_values("rank").head(5)
        assert len(user_topn) == 5, f"topn.parquet missing user {user_id}"
        expected_items = [r["item_id"] for r in expected_recs]
        actual_items = list(user_topn["item_id"])
        assert actual_items == expected_items

    # 3. Verify key evaluation metrics against golden values within tolerance
    golden_metrics = golden["metrics"]

    sar_5 = metrics["models"]["sar"]["5"]
    assert sar_5["ndcg"] == pytest.approx(golden_metrics["sar_5"]["ndcg"], abs=1e-4)
    assert sar_5["recall"] == pytest.approx(golden_metrics["sar_5"]["recall"], abs=1e-4)
    assert sar_5["hit_rate"] == pytest.approx(golden_metrics["sar_5"]["hit_rate"], abs=1e-4)
    assert sar_5["coverage"] == pytest.approx(golden_metrics["sar_5"]["coverage"], abs=1e-4)

    sar_10 = metrics["models"]["sar"]["10"]
    assert sar_10["ndcg"] == pytest.approx(golden_metrics["sar_10"]["ndcg"], abs=1e-4)
    assert sar_10["recall"] == pytest.approx(golden_metrics["sar_10"]["recall"], abs=1e-4)
    assert sar_10["hit_rate"] == pytest.approx(golden_metrics["sar_10"]["hit_rate"], abs=1e-4)

    # 4. Verify baseline sanity ordering: SAR > Popularity > Random
    pop_5 = metrics["models"]["popularity"]["5"]
    rand_5 = metrics["models"]["random"]["5"]
    assert sar_5["ndcg"] > pop_5["ndcg"] > rand_5["ndcg"]
    assert sar_5["hit_rate"] > pop_5["hit_rate"] > rand_5["hit_rate"]
    assert sar_5["recall"] > pop_5["recall"] > rand_5["recall"]

    # 5. Verify all required artifact files exist
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "data_report.json").exists()
    assert (tmp_path / "tuning.json").exists()
    assert (tmp_path / "demo_users.json").exists()
    assert (tmp_path / "users.parquet").exists()
    assert (tmp_path / "items.parquet").exists()
    assert (tmp_path / "interactions.parquet").exists()

    with open(tmp_path / "demo_users.json", encoding="utf-8") as f:
        demo_users = json.load(f)
    assert len(demo_users) == 8
