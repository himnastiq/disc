"""Unit tests for news articles precomputed artifacts, cold start curve, and demo users (Phase 5, P5.9)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.artifacts import load_artifacts

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "artifacts"
pytestmark = [pytest.mark.real_data]


def test_articles_artifact_set_shape_identical_to_movies_and_products() -> None:
    """Assert artifacts/articles has identical shape and file set as movies and products."""
    articles_dir = ARTIFACTS_DIR / "articles"
    movies_dir = ARTIFACTS_DIR / "movies"
    products_dir = ARTIFACTS_DIR / "products"

    if not (articles_dir.exists() and movies_dir.exists() and products_dir.exists()):
        pytest.skip("Full real artifacts not present on disk")

    expected_files = {
        "data_report.json",
        "demo_users.json",
        "interactions.parquet",
        "items.parquet",
        "manifest.json",
        "metrics.json",
        "topn.parquet",
        "users.parquet",
    }

    articles_files = {p.name for p in articles_dir.glob("*.json")} | {
        p.name for p in articles_dir.glob("*.parquet")
    }

    assert expected_files.issubset(articles_files), (
        f"Articles missing files: {expected_files - articles_files}"
    )
    assert (articles_dir / "model").is_dir(), "Articles missing model/ directory"

    # Verify that load_artifacts verifies cryptographic checksums cleanly
    loaded = load_artifacts(articles_dir)
    assert len(loaded.items) > 0
    assert len(loaded.interactions) > 0
    assert len(loaded.users) > 0
    assert len(loaded.demo_users) > 0
    assert loaded.topn is not None and len(loaded.topn) > 0


def test_articles_demo_users_and_personas() -> None:
    """Verify demo users have personas and top categories derived from articles."""
    demo_path = ARTIFACTS_DIR / "articles" / "demo_users.json"
    if not demo_path.exists():
        pytest.skip("artifacts/articles/demo_users.json not found")

    demo_users = json.loads(demo_path.read_text(encoding="utf-8"))
    assert len(demo_users) >= 4, f"Expected at least 4 demo users, got {len(demo_users)}"

    valid_personas = {"heavy", "niche", "casual", "mainstream"}

    for u in demo_users:
        assert "user_id" in u and isinstance(u["user_id"], str)
        assert u["persona"] in valid_personas
        assert u["interaction_count"] > 0
        assert "top_categories" in u and isinstance(u["top_categories"], list)
        # Categories should be text categories, not empty strings
        assert all(isinstance(c, str) and len(c) > 0 for c in u["top_categories"])


def test_articles_cold_start_curves_in_metrics() -> None:
    """Verify cold-start curves exist in metrics.json for tfidf_profile."""
    metrics_path = ARTIFACTS_DIR / "articles" / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("artifacts/articles/metrics.json not found")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "cold_start_curves" in metrics
    curves = metrics["cold_start_curves"]

    assert "tfidf_profile" in curves, "Missing tfidf_profile in cold_start_curves"
    tfidf_curve = curves["tfidf_profile"]
    assert "0" in tfidf_curve, "Cold start curve missing size 0"

    for size_str, size_metrics in tfidf_curve.items():
        assert int(size_str) >= 0
        assert any(k.startswith("hit_rate@") for k in size_metrics)
        assert any(k.startswith("ndcg@") for k in size_metrics)
        assert any(k.startswith("recall@") for k in size_metrics)


def test_articles_topn_and_users_parquet_schemas() -> None:
    """Verify users.parquet and topn.parquet schemas and rank order."""
    articles_dir = ARTIFACTS_DIR / "articles"
    if not articles_dir.exists():
        pytest.skip("artifacts/articles directory not found")

    users_df = pd.read_parquet(articles_dir / "users.parquet")
    expected_user_cols = {
        "user_id",
        "interaction_count",
        "top_categories",
        "first_timestamp",
        "last_timestamp",
        "persona",
    }
    assert expected_user_cols.issubset(set(users_df.columns))

    topn_df = pd.read_parquet(articles_dir / "topn.parquet")
    expected_topn_cols = {"user_id", "item_id", "score", "rank"}
    assert expected_topn_cols.issubset(set(topn_df.columns))

    # Verify rank order per user
    for _, group in topn_df.groupby("user_id"):
        ranks = list(group["rank"])
        assert ranks == list(range(1, len(ranks) + 1)), f"Non-consecutive ranks: {ranks}"
        scores = list(group["score"])
        # Scores should be non-increasing
        for idx in range(len(scores) - 1):
            assert scores[idx] >= scores[idx + 1] - 1e-6, (
                f"Scores not non-increasing: {scores[idx]} < {scores[idx + 1]}"
            )
