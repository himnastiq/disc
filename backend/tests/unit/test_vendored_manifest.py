"""Tests for tools/vendored_manifest.py (P1.6)."""

import subprocess
import sys
from pathlib import Path


def test_vendored_manifest_up_to_date():
    """Verify that docs/VENDORED_FILES.md is up to date and matches disk."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    script_path = repo_root / "tools" / "vendored_manifest.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Manifest check failed:\n{result.stderr}\n{result.stdout}"
    assert "Manifest check passed" in result.stdout
