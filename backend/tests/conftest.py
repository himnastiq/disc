"""Global pytest configuration and fixtures (FIX-31).

Sets ARTIFACT_DIR to committed synthetic mini-artifacts for API tests
(contract, fuzz, purity, gate, startup).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MINI_ARTIFACTS_DIR = Path(__file__).resolve().parent / "fixtures" / "artifacts_mini"

# Fallback ARTIFACT_DIR to MINI_ARTIFACTS_DIR if unset, empty, or points to an invalid directory
_current_art = os.environ.get("ARTIFACT_DIR")
if not _current_art or not (Path(_current_art) / "movies" / "items.parquet").exists():
    os.environ["ARTIFACT_DIR"] = str(MINI_ARTIFACTS_DIR)

API_TEST_SUBPATHS = (
    "contract",
    "test_api_fuzzing",
    "test_api_runtime_purity",
    "test_phase7_gate",
    "test_api_startup",
    "test_api_security",
    "test_api_openapi",
    "test_api_errors",
)


@pytest.fixture(autouse=True)
def configure_artifact_dir(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Ensure API tests (contract, fuzz, purity, gate, startup) use MINI_ARTIFACTS_DIR."""
    test_path = str(request.fspath).replace("\\", "/")
    if any(sub in test_path for sub in API_TEST_SUBPATHS):
        monkeypatch.setenv("ARTIFACT_DIR", str(MINI_ARTIFACTS_DIR))
    yield
