"""Contract tests for GET /v1/popular and GET /v1/similar (Phase 7, P7.7)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import PopularResponse, SimilarResponse
from engine.artifacts import load_artifacts

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


CONTENT_TYPES = ["movies", "products", "articles"]


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# ===========================================================================
# GET /v1/popular Tests
# ===========================================================================


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_get_popular_success(api_client: TestClient, content_type: str) -> None:
    """Test /v1/popular returns top items with monotonicity and display scores."""
    resp = api_client.get(f"/v1/popular?type={content_type}&k=10")
    assert resp.status_code == 200
    data = resp.json()

    res = PopularResponse.model_validate(data)
    assert res.content_type == content_type
    assert 0 < res.k <= 10
    assert len(res.results) == res.k

    if content_type in ("movies", "products"):
        assert res.k == 10

    seen_ids: set[str] = set()
    prev_score = float("inf")
    for item in res.results:
        assert item.item_id not in seen_ids
        seen_ids.add(item.item_id)
        assert item.score <= prev_score + 1e-6
        prev_score = item.score
        assert 0.0 <= item.display_score <= 1.0
        assert item.reason is not None
        assert item.reason.kind == "popular"

    assert "model" in res.meta
    assert "artifact_version" in res.meta
    assert "latency_ms" in res.meta
    assert res.meta["latency_ms"] >= 0.0
    assert res.meta["type"] == content_type


def test_get_popular_unknown_type(api_client: TestClient) -> None:
    """Test /v1/popular returns 404 unknown_type for non-existent content type."""
    resp = api_client.get("/v1/popular?type=non_existent_type&k=5")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"


def test_get_popular_invalid_k(api_client: TestClient) -> None:
    """Test /v1/popular rejects k < 1 or k > 50 with 422 validation_error."""
    resp_zero = api_client.get("/v1/popular?type=movies&k=0")
    assert resp_zero.status_code == 422
    assert resp_zero.json()["error"]["code"] == "validation_error"

    resp_51 = api_client.get("/v1/popular?type=movies&k=51")
    assert resp_51.status_code == 422
    assert resp_51.json()["error"]["code"] == "validation_error"

    resp_huge = api_client.get("/v1/popular?type=movies&k=101")
    assert resp_huge.status_code == 422
    assert resp_huge.json()["error"]["code"] == "validation_error"


# ===========================================================================
# GET /v1/similar Tests
# ===========================================================================


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_get_similar_success_and_never_returns_query_item(
    api_client: TestClient, content_type: str
) -> None:
    """Test /v1/similar returns valid similar items and NEVER returns the query item."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    catalogue_ids = list(loaded.items["item_id"].astype(str))
    assert len(catalogue_ids) >= 3

    # Pick the first 3 items in the catalogue to test
    for query_id in catalogue_ids[:3]:
        resp = api_client.get(f"/v1/similar?type={content_type}&item_id={query_id}&k=5")
        assert resp.status_code == 200
        data = resp.json()

        res = SimilarResponse.model_validate(data)
        assert res.content_type == content_type
        assert res.query_item_id == query_id
        assert len(res.results) == res.k
        assert res.k <= 5

        seen_ids: set[str] = set()
        prev_score = float("inf")
        for item in res.results:
            # Acceptance requirement: similar NEVER returns the query item
            assert item.item_id != query_id, (
                f"Query item {query_id} was returned in similar results"
            )
            assert item.item_id in catalogue_ids, f"Item {item.item_id} not in catalogue"
            assert item.item_id not in seen_ids, f"Duplicate item {item.item_id}"
            seen_ids.add(item.item_id)

            assert item.score <= prev_score + 1e-6
            prev_score = item.score
            assert 0.0 <= item.display_score <= 1.0
            assert item.reason is not None
            assert item.reason.kind == "similar_item"
            assert item.reason.item_id == query_id

        assert "model" in res.meta
        assert "artifact_version" in res.meta
        assert "latency_ms" in res.meta
        assert res.meta["latency_ms"] >= 0.0
        assert res.meta["type"] == content_type


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_get_similar_unknown_item_returns_404(api_client: TestClient, content_type: str) -> None:
    """Acceptance requirement: unknown item gives 404 unknown_item."""
    unknown_item_id = "completely_unknown_item_xyz_9999"
    resp = api_client.get(f"/v1/similar?type={content_type}&item_id={unknown_item_id}&k=5")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_item"
    assert data["error"]["details"]["item_id"] == unknown_item_id
    assert data["error"]["details"]["content_type"] == content_type


def test_get_similar_unknown_type(api_client: TestClient) -> None:
    """Test /v1/similar returns 404 unknown_type for non-existent content type."""
    resp = api_client.get("/v1/similar?type=unknown_type&item_id=1&k=5")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"


def test_get_similar_invalid_k(api_client: TestClient) -> None:
    """Test /v1/similar rejects k < 1 or k > 50 with 422 validation_error."""
    resp_zero = api_client.get("/v1/similar?type=movies&item_id=1&k=0")
    assert resp_zero.status_code == 422
    assert resp_zero.json()["error"]["code"] == "validation_error"

    resp_51 = api_client.get("/v1/similar?type=movies&item_id=1&k=51")
    assert resp_51.status_code == 422
    assert resp_51.json()["error"]["code"] == "validation_error"

    resp_huge = api_client.get("/v1/similar?type=movies&item_id=1&k=101")
    assert resp_huge.status_code == 422
    assert resp_huge.json()["error"]["code"] == "validation_error"
