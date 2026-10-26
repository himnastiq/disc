"""Contract tests for POST /v1/recommend/cold-start edge cases and invariants (Phase 7, P7.6)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import ColdStartResponse
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


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_cold_start_personalized_flow(api_client: TestClient, content_type: str) -> None:
    """Verify personalized cold-start recommendation with valid positive items."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    catalogue = list(loaded.items["item_id"].astype(str))
    assert len(catalogue) >= 5
    sample_history = [{"item_id": iid, "signal": 5.0} for iid in catalogue[:5]]
    history_ids = {h["item_id"] for h in sample_history}

    payload = {
        "type": content_type,
        "history": sample_history,
        "exclude": [],
        "k": 10,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    res = ColdStartResponse.model_validate(data)
    assert res.content_type == content_type
    assert res.mode == "personalized"
    assert res.k == len(res.results)
    assert len(res.ignored_item_ids) == 0

    # Verify R3 invariants
    prev_raw = float("inf")
    seen_ids: set[str] = set()
    for item in res.results:
        assert item.item_id not in history_ids, f"History item {item.item_id} was recommended"
        assert item.item_id not in seen_ids, f"Duplicate item {item.item_id}"
        seen_ids.add(item.item_id)
        assert item.score <= prev_raw + 1e-6
        prev_raw = item.score
        assert 0.0 <= item.display_score <= 1.0


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_cold_start_empty_history(api_client: TestClient, content_type: str) -> None:
    """Acceptance test: empty history falls back to popularity mode with 200 OK."""
    payload = {
        "type": content_type,
        "history": [],
        "k": 10,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    res = ColdStartResponse.model_validate(data)
    assert res.mode == "popularity"
    assert len(res.ignored_item_ids) == 0
    assert 0 < len(res.results) <= 10
    if content_type in ("movies", "products"):
        assert len(res.results) == 10


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_cold_start_only_unknown_ids(api_client: TestClient, content_type: str) -> None:
    """Acceptance test: unknown IDs are ignored and listed in ignored_item_ids."""
    unknown_ids = ["unknown_item_x1", "unknown_item_y2"]
    payload = {
        "type": content_type,
        "history": [{"item_id": iid, "signal": 5.0} for iid in unknown_ids],
        "k": 5,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    res = ColdStartResponse.model_validate(data)
    assert res.mode == "popularity"
    assert set(res.ignored_item_ids) == set(unknown_ids)
    assert len(res.results) == 5


def test_cold_start_duplicate_ids_rejected(api_client: TestClient) -> None:
    """Acceptance test: duplicate IDs in history return 422 duplicate_ids."""
    payload = {
        "type": "movies",
        "history": [
            {"item_id": "1", "signal": 5.0},
            {"item_id": "2", "signal": 4.0},
            {"item_id": "1", "signal": 3.0},
        ],
        "k": 5,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "duplicate_ids"
    assert "1" in data["error"]["details"]["duplicates"]


def test_cold_start_200_and_201_entries_boundary(api_client: TestClient) -> None:
    """Acceptance test: exactly 200 entries accepted; 201 entries rejected with 422."""
    # 1. Exactly 200 entries -> accepted
    history_200 = [{"item_id": f"dummy_{i}", "signal": 1.0} for i in range(200)]
    resp_200 = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history_200, "k": 5},
    )
    assert resp_200.status_code == 200
    assert len(resp_200.json()["ignored_item_ids"]) == 200

    # 2. 201 entries -> rejected by Pydantic max_length=200 validation
    history_201 = [{"item_id": f"dummy_{i}", "signal": 1.0} for i in range(201)]
    resp_201 = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history_201, "k": 5},
    )
    assert resp_201.status_code == 422
    assert resp_201.json()["error"]["code"] == "validation_error"


def test_cold_start_signal_out_of_range(api_client: TestClient) -> None:
    """Acceptance test: signals < 0.0 or > 5.0 return 422 validation_error."""
    # Negative signal
    resp_neg = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": [{"item_id": "1", "signal": -1.5}], "k": 5},
    )
    assert resp_neg.status_code == 422
    assert resp_neg.json()["error"]["code"] == "validation_error"

    # Excess signal > 5.0
    resp_pos = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": [{"item_id": "1", "signal": 10.0}], "k": 5},
    )
    assert resp_pos.status_code == 422
    assert resp_pos.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_cold_start_no_signal_counts_as_liked(api_client: TestClient, content_type: str) -> None:
    """FIX-32: A history item without signal counts as liked (mode == 'personalized')."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    catalogue = list(loaded.items["item_id"].astype(str))
    assert len(catalogue) >= 5
    sample_history = [{"item_id": iid} for iid in catalogue[:5]]

    payload = {
        "type": content_type,
        "history": sample_history,
        "k": 10,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "personalized"
    assert len(data["results"]) > 0
