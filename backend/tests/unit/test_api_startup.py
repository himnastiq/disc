"""Unit tests for FastAPI startup, lifespan, and artifact loading (Phase 7, P7.1)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

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


@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_recommend_known_user_not_in_model_falls_back_to_popularity(content_type: str) -> None:
    """FIX-55: When user exists in lookups but model raises UnknownUser, return mode 'popularity' with popular list & reason."""
    app = create_app()
    with TestClient(app) as client:
        lookups = app.state.lookups[content_type]
        target_uid = f"GHOST_LOOKUP_USER_FIX55_{content_type.upper()}"
        lookups.user_ids.add(target_uid)
        lookups.user_positive_count[target_uid] = (
            10  # Ensure it qualifies for personalization if known
        )

        resp = client.get(
            "/v1/recommend", params={"type": content_type, "user_id": target_uid, "k": 5}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "popularity"
        assert len(data["results"]) == 5

        # Check popular list and popular reason
        pop_resp = client.get("/v1/popular", params={"type": content_type, "k": 5})
        assert pop_resp.status_code == 200
        expected_items = [r["item_id"] for r in pop_resp.json()["results"]]
        actual_items = [r["item_id"] for r in data["results"]]
        assert actual_items == expected_items

        for item in data["results"]:
            assert item["reason"] is not None
            assert item["reason"]["kind"] == "popular"
            assert item["reason"]["item_id"] is None
            assert "Popular" in item["reason"]["text"]


@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_types_users_endpoint_lists_only_modelled_users(content_type: str) -> None:
    """FIX-55: GET /v1/types/{type}/users returns only users known and modelled by the serving model."""
    app = create_app()
    with TestClient(app) as client:
        model = app.state.models[content_type]
        modelled_uids = model.get_modelled_user_ids()
        assert len(modelled_uids) > 0, f"Expected non-empty modelled users for {content_type}"

        resp = client.get(f"/v1/types/{content_type}/users", params={"limit": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert len(data["users"]) > 0

        for user in data["users"]:
            uid = str(user["user_id"])
            assert uid in modelled_uids, (
                f"User {uid} returned in /v1/types/{content_type}/users is not in modelled users"
            )
