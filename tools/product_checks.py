#!/usr/bin/env python3
"""Product-specific evaluation checks for Discovery Engine (Phase 4, P4.6).

Computes and records product domain checks:
1. Sparse-data behavior (ratio and stats of users with <= 5 interactions)
2. Long-tail items (bottom 80% catalogue volume share and recommendation share)
3. Category diversity of top-k recommendations (mean unique categories represented)
4. Similar alternatives quality spot-check (category sharing rate among top-5 similar items)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add backend directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine.artifacts import compute_file_sha256, load_artifacts
from engine.config import load_config
from engine.evaluation.product_checks import (
    compute_category_diversity_metrics,
    compute_long_tail_metrics,
    compute_product_specific_checks,
    compute_similar_alternatives_spot_check,
    compute_sparse_data_metrics,
    extract_item_categories,
    run_product_checks_hook,
)
from engine.registry import build_model

__all__ = [
    "compute_category_diversity_metrics",
    "compute_long_tail_metrics",
    "compute_product_specific_checks",
    "compute_similar_alternatives_spot_check",
    "compute_sparse_data_metrics",
    "extract_item_categories",
    "run_product_checks_hook",
    "update_products_metrics_and_manifest",
]


def update_products_metrics_and_manifest(
    artifact_dir: Path,
    checks_result: dict[str, Any],
) -> None:
    """Update metrics.json in artifact directory and re-sign manifest.json."""
    metrics_path = artifact_dir / "metrics.json"
    manifest_path = artifact_dir / "manifest.json"

    if not metrics_path.exists():
        raise FileNotFoundError(f"metrics.json not found in {artifact_dir}")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["product_specific_checks"] = checks_result
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["metrics.json"] = compute_file_sha256(metrics_path)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    """CLI to run product-specific checks and update products metrics."""
    parser = argparse.ArgumentParser(
        description="Discovery Engine - Product Specific Checks"
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "products",
        help="Path to products artifact directory",
    )
    parser.add_argument("--fast", action="store_true", help="Use fast config")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    args = parser.parse_args()

    artifacts_dir = args.artifacts_dir
    if not artifacts_dir.exists():
        print(f"Error: Artifacts directory not found at {artifacts_dir}")
        sys.exit(1)

    print("Loading artifacts and model...")
    artifacts = load_artifacts(artifacts_dir)
    spec = load_config("products", fast=args.fast)
    model = build_model(spec)
    model.load(artifacts.model_dir)

    print("Running product-specific checks...")
    results = compute_product_specific_checks(
        model=model,
        interactions=artifacts.interactions,
        items=artifacts.items,
        seed=args.seed,
    )

    print("\n" + "=" * 60)
    print("  Discovery Engine: Product-Specific Checks (P4.6)")
    print("=" * 60)

    sd = results["sparse_data"]
    print(
        f"  1. Sparse-Data Behavior       : {sd['sparse_user_count']} / {sd['total_users']} users "
        f"({sd['sparse_user_ratio']:.2%}) have <= {sd['threshold_interactions']} interactions"
    )
    print(
        f"     (Mean: {sd['mean_interactions_per_user']:.2f}, Median: {sd['median_interactions_per_user']:.1f})"
    )

    lt = results["long_tail"]
    print(
        f"  2. Long-Tail Items (Bottom {lt['tail_percentile']:.0%}) : "
        f"{lt['tail_item_count']} / {lt['total_items']} items account for "
        f"{lt['tail_interaction_volume_share']:.2%} of interaction volume"
    )
    print(
        f"     Tail Recommendation Share  : {lt['tail_recommendation_share_at_k']:.2%} of top-{lt['k']} recs"
    )

    cd = results["category_diversity"]
    print(
        f"  3. Category Diversity at K={cd['k']}  : "
        f"Mean unique categories: {cd['mean_unique_categories']:.2f} "
        f"(range {cd['min_unique_categories']} - {cd['max_unique_categories']})"
    )

    sa = results["similar_alternatives_spot_check"]
    status_str = "PASSED" if sa["passed"] else "FAILED"
    print(
        f"  4. Similar Alternatives Check  : "
        f"{sa['shared_category_count']} / {sa['total_recommendations_evaluated']} "
        f"({sa['shared_category_rate']:.2%}) share categories "
        f"[target > {sa['target_threshold']:.0%}] -> {status_str}"
    )
    print("=" * 60 + "\n")

    print(f"Updating {artifacts_dir / 'metrics.json'} and re-signing manifest...")
    update_products_metrics_and_manifest(artifacts_dir, results)
    print("Done.")


if __name__ == "__main__":
    main()
