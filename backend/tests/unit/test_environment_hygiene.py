"""Environment hygiene tests (P1.8)."""

import importlib.util
import subprocess
import sys


def test_recommenders_not_installed_via_pip():
    """Assert that pip show recommenders fails in the project environment."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "recommenders"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "recommenders should not be installed via pip"
    assert "recommenders" not in result.stdout.lower()


def test_recommenders_module_not_importable():
    """Assert that find_spec('recommenders') is None."""
    spec = importlib.util.find_spec("recommenders")
    assert spec is None, "recommenders module should not be resolvable or importable"
