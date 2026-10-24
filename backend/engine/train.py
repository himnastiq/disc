"""Discovery Engine - Training CLI entry point (P2.12).

Usage:
    python -m engine.train --type <content_type> [--fast] [--seed <int>] [--artifacts-dir <path>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.adapters import movielens as _movielens_adapter  # noqa: F401
from engine.adapters import toy as _toy_adapter  # noqa: F401
from engine.artifacts import save_artifacts
from engine.config import load_config
from engine.evaluation.harness import EvaluationHarness
from engine.logging_utils import configure_logging, get_logger, log_event
from engine.registry import build_model, get_adapter

if TYPE_CHECKING:
    from engine.models.base import RecommenderModel


def compute_user_stats_and_personas(
    interactions: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Compute per-user interaction statistics, persona labels, and demo user selections."""
    user_counts = interactions.groupby("user_id").size().to_dict()

    user_rows = []
    demo_users: list[dict[str, Any]] = []

    for uid, count in sorted(user_counts.items()):
        # Assign transparent persona labels based on activity volume
        if count >= 15:
            persona = "heavy"
        elif count <= 3:
            persona = "casual"
        else:
            persona = "mainstream"

        user_rows.append(
            {
                "user_id": str(uid),
                "interaction_count": int(count),
                "persona": persona,
            }
        )

    users_df = pd.DataFrame(user_rows)

    # Select representative demo users across personas
    for persona_type in ["heavy", "mainstream", "casual"]:
        matching = users_df[users_df["persona"] == persona_type]
        if not matching.empty:
            for uid in matching["user_id"].head(3):
                demo_users.append(
                    {
                        "user_id": str(uid),
                        "persona": persona_type,
                        "interaction_count": int(user_counts[uid]),
                    }
                )

    if not demo_users and not users_df.empty:
        for uid in users_df["user_id"].head(5):
            demo_users.append(
                {
                    "user_id": str(uid),
                    "persona": "standard",
                    "interaction_count": int(user_counts[uid]),
                }
            )

    return users_df, demo_users


def precompute_topn_for_users(
    model: RecommenderModel,
    users: list[str],
    k: int = 50,
) -> pd.DataFrame:
    """Precompute top-N recommendations for all known users."""
    rows = []
    for uid in users:
        try:
            recs = model.recommend_user(user_id=uid, k=k)
            for r in recs:
                rows.append(
                    {
                        "user_id": uid,
                        "item_id": r.item_id,
                        "score": r.score,
                        "rank": r.rank,
                    }
                )
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=["user_id", "item_id", "score", "rank"])
    return pd.DataFrame(rows)


def run_pipeline(
    content_type: str,
    fast: bool = False,
    seed: int | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute end-to-end training and evaluation pipeline for a content type.

    Args:
        content_type: Slug of content type (e.g. 'movies', 'toy').
        fast: Whether to apply fast developer overrides.
        seed: Optional explicit random seed.
        artifacts_dir: Optional custom artifact output root directory.

    Returns:
        dict[str, Any]: Evaluation metrics dictionary.
    """
    logger = get_logger("train")
    log_event(logger, "pipeline_start", content_type=content_type, fast=fast, seed=seed)

    # 1. Load config
    spec = load_config(content_type, fast=fast)
    if seed is not None:
        spec.split.seed = seed

    target_artifacts_dir = artifacts_dir or (
        Path(__file__).resolve().parent.parent.parent / "artifacts" / content_type
    )

    # 2. Get and validate adapter
    adapter = get_adapter(spec)
    log_event(logger, "adapter_loaded", adapter=spec.dataset.adapter)

    interactions = adapter.interactions()
    items = adapter.items()
    report = adapter.validate()

    log_event(
        logger,
        "data_validated",
        total_interactions=report.total_interactions,
        unique_users=report.unique_users,
        unique_items=report.unique_items,
        sparsity=report.sparsity,
    )

    # 3. Build primary model and baselines
    model = build_model(spec)
    log_event(logger, "model_built", model_name=spec.model.name)

    # 4. Run evaluation harness
    harness = EvaluationHarness(spec, models=[model])
    max_test = 50 if fast else 200
    metrics = harness.run(
        interactions=interactions,
        items=items,
        max_test_users=max_test,
        cold_start_sample_users=20 if fast else 50,
    )

    # 5. Precompute personas and demo users
    users_df, demo_users = compute_user_stats_and_personas(interactions)

    # 6. Precompute top-N recommendations
    known_users = list(users_df["user_id"])
    topn_df = precompute_topn_for_users(model, users=known_users[: 100 if fast else 500], k=50)

    # 7. Save model parameters to model/ subfolder
    model_dir = target_artifacts_dir / "model"
    model.save(model_dir)

    # 8. Save artifacts and generate cryptographic manifest
    manifest_p = save_artifacts(
        artifact_dir=target_artifacts_dir,
        spec=spec,
        items=items,
        interactions=interactions,
        users=users_df,
        metrics=metrics,
        demo_users=demo_users,
        topn=topn_df,
        extra_files={"data_report.json": report.model_dump()},
    )

    log_event(logger, "artifacts_saved", manifest_path=str(manifest_p))

    # 9. Print formatted summary
    print("\n" + "=" * 60)
    print(f"  Discovery Engine: Training Complete [{content_type.upper()}]")
    print("=" * 60)
    print(f"  Total Interactions : {report.total_interactions:,}")
    print(f"  Unique Users        : {report.unique_users:,}")
    print(f"  Catalogue Items     : {report.unique_items:,}")
    print(f"  Matrix Sparsity     : {report.sparsity * 100:.2f}%")
    print(f"  Artifact Directory  : {target_artifacts_dir}")

    ref_k = str(spec.evaluation.k[0]) if spec.evaluation.k else "10"
    print(f"\n  Metrics Summary (at K={ref_k}):")
    print("  " + "-" * 56)
    for m_name, k_dict in metrics.get("models", {}).items():
        res_k = k_dict.get(ref_k, {})
        ndcg_v = res_k.get("ndcg", 0.0)
        hr_v = res_k.get("hit_rate", 0.0)
        rec_v = res_k.get("recall", 0.0)
        cov_v = res_k.get("coverage", 0.0)
        div_v = res_k.get("diversity", 0.0)
        pers_v = res_k.get("personalisation", 0.0)
        print(
            f"  {m_name:<12} | NDCG: {ndcg_v:.4f} | HitRate: {hr_v:.4f} | Recall: {rec_v:.4f} | Coverage: {cov_v:.4f} | Div: {div_v:.4f} | Pers: {pers_v:.4f}"
        )
    print("=" * 60 + "\n")

    return metrics


def main() -> None:
    """CLI entry point for python -m engine.train."""
    parser = argparse.ArgumentParser(
        description="Discovery Engine - Train and evaluate recommender pipeline."
    )
    parser.add_argument(
        "--type",
        required=True,
        help="Content type identifier (e.g. movies, products, articles, toy)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Apply fast developer overrides (smaller datasets/grids)",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Explicit random seed for splits and modeling"
    )
    parser.add_argument(
        "--artifacts-dir", type=Path, default=None, help="Custom output directory for artifacts"
    )

    args = parser.parse_args()
    configure_logging()

    try:
        run_pipeline(
            content_type=args.type,
            fast=args.fast,
            seed=args.seed,
            artifacts_dir=args.artifacts_dir,
        )
    except Exception as e:
        logger = get_logger("train")
        logger.error(f"Pipeline training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
