"""Discovery Engine - Clean-room rebuild verification tests (P6.4).

Verifies that from a fresh clone and clean environment, the entire system builds,
trains, and evaluates using only the README instructions:
    make setup -> make data -> make train-fast -> make eval
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLEAN_ROOM_SCRIPT = REPO_ROOT / "tools" / "clean_room_rebuild.py"


def test_clean_room_script_exists() -> None:
    """Verify that tools/clean_room_rebuild.py exists and can be imported."""
    assert CLEAN_ROOM_SCRIPT.exists(), f"Missing {CLEAN_ROOM_SCRIPT}"
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import clean_room_rebuild

    assert hasattr(clean_room_rebuild, "clean_room_rebuild")


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("RUN_CLEAN_ROOM"),
    reason="Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py",
)
def test_clean_room_rebuild(tmp_path: Path) -> None:
    """Execute clean-room rebuild in tmp_path and verify all steps complete."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from clean_room_rebuild import clean_room_rebuild

    timings = clean_room_rebuild(target_dir=tmp_path)

    assert "git_clone" in timings
    assert "venv_creation" in timings
    assert "make_setup" in timings
    assert "make_data" in timings
    assert "train_fast_movies" in timings
    assert "train_fast_products" in timings
    assert "train_fast_articles" in timings
    assert "make_eval" in timings

    clone_dir = tmp_path / "discovery-engine"
    assert (clone_dir / "docs" / "RESULTS.md").exists()
    assert (clone_dir / "artifacts" / "movies" / "topn.parquet").exists()
    assert (clone_dir / "artifacts" / "products" / "topn.parquet").exists()
    assert (clone_dir / "artifacts" / "articles" / "topn.parquet").exists()
