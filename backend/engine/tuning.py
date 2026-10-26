"""Discovery Engine - Hyperparameter search and validation tuning (P3.8).

Conducts hyperparameter optimization over candidate grids using ONLY the validation
split. Ensures the test split remains completely unread and untouched during selection.
Logs all evaluated trials to artifacts/<type>/tuning.json with explicit split attribution.
"""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.config import compute_config_hash
from engine.evaluation.harness import get_git_sha
from engine.evaluation.metrics import hit_rate, ndcg, precision, recall
from engine.logging_utils import get_logger, log_event
from engine.models.sar import SarModel

if TYPE_CHECKING:
    from pathlib import Path

    from engine.schema import ContentTypeSpec


def get_default_tuning_grid(fast: bool = False) -> list[dict[str, Any]]:
    """Return a candidate hyperparameter grid for SAR model tuning.

    Sweeps:
    - similarity_type: jaccard, lift, cooccurrence
    - timedecay_formula: true / false
    - time_decay_coefficient: half-life in days (30, 90)
    - positive_threshold: minimum signal rating for positive feedback (3.5, 4.0)
    - top_neighbors_per_item: sparsification neighbor cap (20, 50, 100)
    """
    if fast:
        return [
            {
                "similarity_type": "jaccard",
                "timedecay_formula": True,
                "time_decay_coefficient": 30,
                "positive_threshold": 4.0,
                "top_neighbors_per_item": 50,
            },
            {
                "similarity_type": "jaccard",
                "timedecay_formula": False,
                "time_decay_coefficient": None,
                "positive_threshold": 4.0,
                "top_neighbors_per_item": 50,
            },
            {
                "similarity_type": "cooccurrence",
                "timedecay_formula": True,
                "time_decay_coefficient": 30,
                "positive_threshold": 4.0,
                "top_neighbors_per_item": 50,
            },
            {
                "similarity_type": "lift",
                "timedecay_formula": True,
                "time_decay_coefficient": 30,
                "positive_threshold": 4.0,
                "top_neighbors_per_item": 50,
            },
            {
                "similarity_type": "jaccard",
                "timedecay_formula": True,
                "time_decay_coefficient": 30,
                "positive_threshold": 4.0,
                "top_neighbors_per_item": 20,
            },
        ]

    return [
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "jaccard",
            "timedecay_formula": False,
            "time_decay_coefficient": None,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 90,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "cooccurrence",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "lift",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 3.5,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 20,
        },
        {
            "similarity_type": "jaccard",
            "timedecay_formula": True,
            "time_decay_coefficient": 30,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 100,
        },
        {
            "similarity_type": "lift",
            "timedecay_formula": False,
            "time_decay_coefficient": None,
            "positive_threshold": 3.5,
            "top_neighbors_per_item": 50,
        },
        {
            "similarity_type": "cooccurrence",
            "timedecay_formula": False,
            "time_decay_coefficient": None,
            "positive_threshold": 4.0,
            "top_neighbors_per_item": 50,
        },
    ]


def tune_sar_on_validation(
    spec: ContentTypeSpec,
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    items: pd.DataFrame,
    grid: list[dict[str, Any]] | None = None,
    max_eval_users: int = 200,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute hyperparameter sweep on the validation split only.

    The test split is strictly omitted from the function parameters to guarantee
    zero contamination or leakage during model selection.

    Args:
        spec: Base ContentTypeSpec.
        train_df: Training interactions.
        valid_df: Validation interactions (used exclusively for selection).
        items: Item catalogue DataFrame.
        grid: Optional explicit list of hyperparameter dictionary trials.
        max_eval_users: Maximum number of validation users to score.
        output_path: Path to write artifacts/<type>/tuning.json.

    Returns:
        dict[str, Any]: Complete tuning record with trial metrics and best configuration.
    """
    logger = get_logger("tune")
    trials_grid = grid or get_default_tuning_grid(fast=spec.dataset.variant == "100k")

    log_event(
        logger,
        "tuning_start",
        content_type=spec.type,
        variant=spec.dataset.variant,
        num_trials=len(trials_grid),
    )

    trials_results: list[dict[str, Any]] = []

    for trial_idx, params in enumerate(trials_grid, start=1):
        t_start = time.time()

        # Build candidate spec with modified parameters
        candidate_spec = spec.model_copy(deep=True)
        candidate_spec.model.params["similarity_type"] = params["similarity_type"]
        candidate_spec.model.params["timedecay_formula"] = params["timedecay_formula"]
        if params["time_decay_coefficient"] is not None:
            candidate_spec.model.params["time_decay_coefficient"] = params["time_decay_coefficient"]
        candidate_spec.signal.positive_threshold = float(params["positive_threshold"])
        candidate_spec.serving.top_neighbors_per_item = int(params["top_neighbors_per_item"])

        # Determine ground-truth positive validation interactions for this candidate threshold (F-006)
        thresh = candidate_spec.signal.positive_threshold
        if "signal" in valid_df.columns:
            pos_valid = valid_df[valid_df["signal"] >= thresh]
        elif "positive" in valid_df.columns:
            pos_valid = valid_df[valid_df["positive"] == True]  # noqa: E712
        else:
            pos_valid = valid_df

        # Fit model on training split
        model = SarModel(candidate_spec)
        t_fit0 = time.time()
        model.fit(train_df, items)
        train_time_s = time.time() - t_fit0

        # Select validation evaluation users present in train_df
        common_users = sorted(
            set(train_df["user_id"].astype(str)).intersection(set(pos_valid["user_id"].astype(str)))
        )
        if not common_users:
            eval_users: list[str] = []
        elif len(common_users) > max_eval_users:
            rng = random.Random(spec.split.seed or 42)
            eval_users = sorted(rng.sample(common_users, max_eval_users))
        else:
            eval_users = common_users

        pos_valid_eval = pos_valid[pos_valid["user_id"].isin(eval_users)]

        # Generate top-10 recommendations
        t_eval0 = time.time()
        preds_rows = []
        for uid in eval_users:
            recs = model.recommend_user(user_id=uid, k=10)
            for r in recs:
                preds_rows.append(
                    {
                        "user_id": uid,
                        "item_id": r.item_id,
                        "score": r.score,
                        "rank": r.rank,
                    }
                )
        eval_time_s = time.time() - t_eval0

        preds_df = (
            pd.DataFrame(preds_rows)
            if preds_rows
            else pd.DataFrame(columns=["user_id", "item_id", "score", "rank"])
        )

        val_ndcg = ndcg(pos_valid_eval, preds_df, k=10)
        val_recall = recall(pos_valid_eval, preds_df, k=10)
        val_hit_rate = hit_rate(pos_valid_eval, preds_df, k=10)
        val_precision = precision(pos_valid_eval, preds_df, k=10)

        trial_record = {
            "trial_id": trial_idx,
            "split_used": "validation",
            "params": params,
            "validation_metrics": {
                "ndcg@10": round(val_ndcg, 5),
                "recall@10": round(val_recall, 5),
                "hit_rate@10": round(val_hit_rate, 5),
                "precision@10": round(val_precision, 5),
            },
            "evaluated_users": len(eval_users),
            "train_time_s": round(train_time_s, 2),
            "eval_time_s": round(eval_time_s, 2),
            "total_time_s": round(time.time() - t_start, 2),
        }
        trials_results.append(trial_record)

        log_event(
            logger,
            "trial_complete",
            trial_id=trial_idx,
            split_used="validation",
            ndcg_10=val_ndcg,
            recall_10=val_recall,
            similarity=params["similarity_type"],
            decay=params["timedecay_formula"],
            top_k=params["top_neighbors_per_item"],
        )

    # Choose best trial strictly by highest validation ndcg@10
    best_trial = max(trials_results, key=lambda t: t["validation_metrics"]["ndcg@10"])

    tuning_payload: dict[str, Any] = {
        "content_type": spec.type,
        "dataset_variant": spec.dataset.variant,
        "split_strategy": spec.split.strategy,
        "selection_metric": "ndcg@10",
        "selection_split": "validation",
        "best_trial_id": best_trial["trial_id"],
        "best_params": best_trial["params"],
        "best_validation_ndcg10": best_trial["validation_metrics"]["ndcg@10"],
        "best_validation_metrics": best_trial["validation_metrics"],
        "trials": trials_results,
        "created_at": datetime.now(UTC).isoformat(),
        "git_sha": get_git_sha(),
        "config_hash": compute_config_hash(spec),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(tuning_payload, indent=2), encoding="utf-8")
        log_event(logger, "tuning_saved", path=str(output_path))

    return tuning_payload
