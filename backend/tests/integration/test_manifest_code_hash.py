"""Integrity test for artifact manifests code_hash (FIX-54).

Verifies that every production artifact manifest in artifacts/ contains
a 'code_hash' key that matches the current SHA-256 digest of Python source files
in backend/engine/ and backend/discovery/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.artifacts import compute_code_hash

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

pytestmark = [pytest.mark.real_data]


@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_manifest_code_hash_up_to_date(content_type: str) -> None:
    """Verify that manifest.json has 'code_hash' matching current engine/ and discovery/ sources."""
    manifest_p = ARTIFACTS_DIR / content_type / "manifest.json"
    if not manifest_p.exists():
        pytest.skip(f"Artifact manifest not found at {manifest_p}")

    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert "code_hash" in manifest, f"Manifest for {content_type} missing 'code_hash'"

    expected_hash = compute_code_hash()
    actual_hash = manifest["code_hash"]

    assert actual_hash == expected_hash, (
        f"Manifest {content_type} code_hash is stale: "
        f"manifest has {actual_hash}, but current sources hash to {expected_hash}. "
        "Artifacts must be rebuilt or manifest re-signed when engine/discovery code changes."
    )
