"""Unit tests for vendored package imports and purity (P1.5)."""

import subprocess
import sys


def test_vendored_modules_import_cleanly_without_heavy_frameworks():
    """Verify that all used discovery modules import without pulling heavy frameworks."""
    code = """
import sys
import importlib

modules = [
    "discovery",
    "discovery.utils.constants",
    "discovery.utils.python_utils",
    "discovery.utils.notebook_utils",
    "discovery.datasets.download_utils",
    "discovery.datasets.pandas_df_utils",
    "discovery.datasets.split_utils",
    "discovery.datasets.python_splitters",
    "discovery.datasets.movielens",
    "discovery.datasets.amazon_reviews",
    "discovery.datasets.mind",
    "discovery.evaluation.python_evaluation",
    "discovery.models.sar",
    "discovery.models.sar.sar_singlenode",
    "discovery.models.tfidf",
    "discovery.models.tfidf.tfidf_utils",
]

for mod in modules:
    importlib.import_module(mod)

forbidden = ["tensorflow", "pyspark", "torch", "cornac"]
found = [f for f in forbidden if f in sys.modules]
if found:
    print(f"FORBIDDEN_FOUND: {found}")
    sys.exit(1)
print("SUCCESS")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Import test failed:\nStdout: {result.stdout}\nStderr: {result.stderr}"
    )
    assert "SUCCESS" in result.stdout
