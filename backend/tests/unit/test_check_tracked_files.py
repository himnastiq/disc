"""Unit tests for tools/check_tracked_files.py (FIX-53)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from check_tracked_files import (  # noqa: E402
    MAX_FILE_SIZE_BYTES,
    check_tracked_files,
    is_forbidden_path,
)


def test_is_forbidden_path_detects_forbidden_directories() -> None:
    # Forbidden artifacts and data paths
    assert is_forbidden_path("artifacts/movies/manifest.json") is True
    assert is_forbidden_path("artifacts_backup_20261026_2201/movies/model.json") is True
    assert is_forbidden_path("data/raw/mind/news.tsv") is True
    assert is_forbidden_path("data/processed/interactions.parquet") is True
    assert is_forbidden_path("subfolder/artifacts/items.parquet") is True
    assert is_forbidden_path("subfolder/data/ratings.csv") is True


def test_is_forbidden_path_allows_mini_fixtures_and_normal_code() -> None:
    # Allowed mini artifacts fixture
    assert is_forbidden_path("backend/tests/fixtures/artifacts_mini/movies/manifest.json") is False
    assert is_forbidden_path("tests/fixtures/artifacts_mini/articles/items.parquet") is False

    # Allowed code and docs
    assert is_forbidden_path("backend/engine/artifacts.py") is False
    assert is_forbidden_path("backend/discovery/datasets/movielens.py") is False
    assert is_forbidden_path("docs/DATASETS.md") is False
    assert is_forbidden_path("README.md") is False


def test_check_tracked_files_passes_on_current_clean_repo() -> None:
    violations = check_tracked_files(REPO_ROOT)
    assert violations == [], f"Expected zero tracked file violations, got: {violations}"


def test_max_file_size_is_5mb() -> None:
    assert MAX_FILE_SIZE_BYTES == 5 * 1024 * 1024
