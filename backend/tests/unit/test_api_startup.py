"""Unit tests for FastAPI startup, lifespan, and artifact loading (Phase 7, P7.1)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from api.main import create_app

if TYPE_CHECKING:
    import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


def test_api_environment_thread_isolation() -> None:
    """Verify that thread environment variables are set to 1 before numpy operations."""
    assert os.environ.get("OPENBLAS_NUM_THREADS") == "1"
    assert os.environ.get("MKL_NUM_THREADS") == "1"
    assert os.environ.get("OMP_NUM_THREADS") == "1"


def test_api_startup_normal_lifespan() -> None:
    """Verify that the FastAPI app initializes successfully and loads all real artifacts."""
    app = create_app()
    with TestClient(app):
        # App state must contain availability records for all 3 standard domains
        assert app.state.availability.get("movies") is True
        assert app.state.availability.get("products") is True
        assert app.state.availability.get("articles") is True

        assert "movies" in app.state.artifacts
        assert "products" in app.state.artifacts
        assert "articles" in app.state.artifacts

        assert "movies" in app.state.models
        assert "products" in app.state.models
        assert "articles" in app.state.models


def test_api_startup_with_corrupt_artifact_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance test: app starts even if one artifact directory is corrupted, marking it unavailable."""
    temp_artifacts = tmp_path / "artifacts"
    shutil.copytree(get_artifacts_dir(), temp_artifacts)

    # Deliberately corrupt the movies artifact directory: alter topn.parquet byte payload
    corrupt_file = temp_artifacts / "movies" / "topn.parquet"
    assert corrupt_file.exists()
    payload = bytearray(corrupt_file.read_bytes())
    payload[15] ^= 0xFF
    corrupt_file.write_bytes(payload)

    # Point ARTIFACT_DIR env var to the temporary corrupted artifacts
    monkeypatch.setenv("ARTIFACT_DIR", str(temp_artifacts))

    app = create_app()
    with TestClient(app):
        # The app starts without crashing
        assert app.state.availability.get("movies") is False
        assert "movies" in app.state.unavailable_reasons
        assert len(app.state.unavailable_reasons["movies"]) > 0

        # Uncorrupted types must remain fully available
        assert app.state.availability.get("products") is True
        assert app.state.availability.get("articles") is True
        assert "products" in app.state.models
        assert "articles" in app.state.models
