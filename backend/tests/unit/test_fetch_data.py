"""Tests for backend/scripts/fetch_data.py (P3.1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.fetch_data import download_url


def test_fetch_data_dry_run() -> None:
    """Verify fetch_data CLI --dry-run prints expected summary without failing."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "fetch_data.py"
    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, str(script_path), "--type", "movies", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo_root),
    )
    assert result.returncode == 0
    assert "[DRY RUN] Dataset: MovieLens" in result.stdout
    assert "Would download to:" in result.stdout


def test_download_url_existing_file(tmp_path: Path) -> None:
    """Verify download_url immediately returns True if file already exists with content."""
    dummy_file = tmp_path / "dummy.zip"
    dummy_file.write_bytes(b"dummy data")

    # Should not make any network request
    assert download_url("https://example.com/not-used.zip", dummy_file) is True
