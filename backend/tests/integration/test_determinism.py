"""Discovery Engine - Pipeline Determinism and Hash Invariance Tests (P6.3).

Verifies that executing run_pipeline twice in --fast mode with identical seeds
produces byte-for-byte identical topn.parquet SHA-256 cryptographic hashes and
identical evaluation metrics across all supported content domains:
- Movies (MovieLens 100K + SAR)
- Products (Amazon Instruments + SAR)
- Articles (MIND + TF-IDF Profile Model)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from engine.train import run_pipeline

pytestmark = [pytest.mark.integration]


def _assert_topn_determinism(content_type: str, tmp_path: Path, seed: int = 42) -> None:
    """Helper to execute training twice into isolated directories and assert hash identity."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    raw_data_map = {
        "movies": repo_root / "data" / "raw" / "movielens",
        "products": repo_root / "data" / "raw" / "amazon",
        "articles": repo_root / "data" / "raw" / "mind",
    }
    raw_path = raw_data_map.get(content_type)
    if raw_path and not raw_path.exists():
        pytest.skip(f"Raw data directory for '{content_type}' not found at {raw_path}")

    dir1 = tmp_path / f"{content_type}_run1"
    dir2 = tmp_path / f"{content_type}_run2"

    metrics1 = run_pipeline(content_type, fast=True, seed=seed, artifacts_dir=dir1)
    metrics2 = run_pipeline(content_type, fast=True, seed=seed, artifacts_dir=dir2)

    topn1_path = dir1 / "topn.parquet"
    topn2_path = dir2 / "topn.parquet"

    assert topn1_path.exists(), f"Missing topn.parquet in {dir1}"
    assert topn2_path.exists(), f"Missing topn.parquet in {dir2}"

    # 1. Assert cryptographic SHA-256 identity
    hash1 = hashlib.sha256(topn1_path.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(topn2_path.read_bytes()).hexdigest()
    assert hash1 == hash2, (
        f"Non-deterministic topn.parquet for '{content_type}': run1={hash1} != run2={hash2}"
    )

    # 2. Assert DataFrame equality
    df1 = pd.read_parquet(topn1_path)
    df2 = pd.read_parquet(topn2_path)
    pd.testing.assert_frame_equal(df1, df2)

    # 3. Assert evaluation metrics reproducibility
    assert metrics1["content_type"] == metrics2["content_type"]
    assert metrics1["dataset_variant"] == metrics2["dataset_variant"]
    assert metrics1["sanity_checks"] == metrics2["sanity_checks"]


def test_pipeline_determinism_toy(tmp_path: Path) -> None:
    """Assert byte-for-byte identical topn.parquet hash on synthetic Toy pipeline (runs in CI without real data)."""
    _assert_topn_determinism("toy", tmp_path, seed=42)


@pytest.mark.real_data
def test_pipeline_determinism_movies(tmp_path: Path) -> None:
    """Assert byte-for-byte identical topn.parquet hash on Movies in fast mode."""
    _assert_topn_determinism("movies", tmp_path, seed=42)


@pytest.mark.real_data
def test_pipeline_determinism_products(tmp_path: Path) -> None:
    """Assert byte-for-byte identical topn.parquet hash on Products in fast mode."""
    _assert_topn_determinism("products", tmp_path, seed=42)


@pytest.mark.real_data
def test_pipeline_determinism_articles(tmp_path: Path) -> None:
    """Assert byte-for-byte identical topn.parquet hash on Articles in fast mode."""
    _assert_topn_determinism("articles", tmp_path, seed=42)
