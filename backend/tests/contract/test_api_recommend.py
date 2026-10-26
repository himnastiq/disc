"""Contract tests for GET /v1/recommend asserting R3 invariants across all content types (Phase 7, P7.5)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import RecommendResponse
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


def assert_r3_invariants_on_response(
    resp_data: dict[str, Any],
    catalogue_ids: set[str],
    user_seen_ids: set[str],
    excluded_ids: set[str],
    k: int,
) -> None:
    """Verify core R3 invariants on recommendation API response."""
    recs = RecommendResponse.model_validate(resp_data)

    assert recs.k == len(recs.results)
    assert recs.k <= k
    assert recs.mode in ("personalized", "popularity")

    seen_ids: set[str] = set()
    prev_raw_score = float("inf")
    prev_display_score = float("inf")

    for idx, item in enumerate(recs.results):
        iid = item.item_id

        # 1. Valid catalogue membership
        assert iid in catalogue_ids, f"Recommended item {iid} is not in catalogue"

        # 2. No duplicate items
        assert iid not in seen_ids, f"Duplicate item {iid} at rank {idx}"
        seen_ids.add(iid)

        # 3. Seen items strictly excluded
        assert iid not in user_seen_ids, f"Seen item {iid} was recommended at rank {idx}"

        # 4. Excluded items strictly excluded
        assert iid not in excluded_ids, f"Explicitly excluded item {iid} was returned"

        # 5. Non-increasing monotonic raw scores
        assert item.score <= prev_raw_score + 1e-6, (
            f"Raw scores not monotonic at rank {idx}: {item.score} > {prev_raw_score}"
        )
        prev_raw_score = item.score

        # 6. Non-increasing monotonic display scores within [0.0, 1.0]
        assert 0.0 <= item.display_score <= 1.0, (
            f"Display score out of bounds: {item.display_score}"
        )
        assert item.display_score <= prev_display_score + 1e-6, (
            f"Display scores not monotonic at rank {idx}: {item.display_score} > {prev_display_score}"
        )
        prev_display_score = item.display_score

        # 7. Faithful explanation attribution
        if item.reason is not None and item.reason.item_id is not None:
            # Reason item must be in user's history and never the recommended item itself
            assert item.reason.item_id in user_seen_ids, (
                f"Reason item {item.reason.item_id} not in user history"
            )
            assert item.reason.item_id != iid, "Reason item cannot be the recommended item itself"


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_recommend_endpoint_r3_invariants(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/recommend satisfies R3 invariants for standard known users."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    catalogue_ids = set(loaded.items["item_id"].astype(str))

    # Pick first demo user
    test_user_id = str(loaded.demo_users[0]["user_id"])
    u_interactions = loaded.interactions[loaded.interactions["user_id"].astype(str) == test_user_id]
    user_seen_ids = set(u_interactions["item_id"].astype(str))

    resp = api_client.get(f"/v1/recommend?type={content_type}&user_id={test_user_id}&k=10")
    assert resp.status_code == 200
    data = resp.json()

    assert_r3_invariants_on_response(
        resp_data=data,
        catalogue_ids=catalogue_ids,
        user_seen_ids=user_seen_ids,
        excluded_ids=set(),
        k=10,
    )


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_recommend_with_explicit_exclusions(api_client: TestClient, content_type: str) -> None:
    """Verify that items in exclude disappear from results and trigger live fallback if needed."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    catalogue_ids = set(loaded.items["item_id"].astype(str))
    test_user_id = str(loaded.demo_users[0]["user_id"])
    user_seen_ids = set(
        loaded.interactions[loaded.interactions["user_id"].astype(str) == test_user_id][
            "item_id"
        ].astype(str)
    )

    # 1. First fetch top 5 recommendations
    resp_init = api_client.get(f"/v1/recommend?type={content_type}&user_id={test_user_id}&k=5")
    assert resp_init.status_code == 200
    initial_items = [r["item_id"] for r in resp_init.json()["results"]]
    assert len(initial_items) >= 2

    # 2. Add the first two recommended items to exclude
    exclude_targets = initial_items[:2]
    exclude_param = ",".join(exclude_targets)

    resp_ex = api_client.get(
        f"/v1/recommend?type={content_type}&user_id={test_user_id}&k=5&exclude={exclude_param}"
    )
    assert resp_ex.status_code == 200
    ex_data = resp_ex.json()

    # None of the excluded items must appear in the new results
    new_items = [r["item_id"] for r in ex_data["results"]]
    for target in exclude_targets:
        assert target not in new_items, f"Excluded item {target} reappeared in recommendations"

    # Must still satisfy all R3 invariants
    assert_r3_invariants_on_response(
        resp_data=ex_data,
        catalogue_ids=catalogue_ids,
        user_seen_ids=user_seen_ids,
        excluded_ids=set(exclude_targets),
        k=5,
    )


def test_recommend_unknown_user(api_client: TestClient) -> None:
    """Verify 404 unknown_user when recommending for nonexistent user."""
    resp = api_client.get("/v1/recommend?type=movies&user_id=completely_unknown_uid_99999&k=10")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_user"
    assert data["error"]["details"]["user_id"] == "completely_unknown_uid_99999"


def test_recommend_unknown_type(api_client: TestClient) -> None:
    """Verify 404 unknown_type when recommending for invalid content type."""
    resp = api_client.get("/v1/recommend?type=invalid_type_xyz&user_id=1&k=10")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_recommend_user_with_fewer_positives_returns_popularity(
    api_client: TestClient, content_type: str
) -> None:
    """FIX-33: When a user has fewer positive interactions than the minimum required,
    mode must be 'popularity' and results must agree with popularity serving.
    """
    from engine.config import load_config

    spec = load_config(content_type, fast=True)
    min_pos = spec.serving.min_positive_items_for_personalization
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    inter = loaded.interactions

    # Find a user with fewer positive interactions than min_pos
    target_user = None
    for uid in inter["user_id"].astype(str).unique():
        sub = inter[inter["user_id"].astype(str) == uid]
        if "positive" in sub.columns:
            pos_count = int(sub["positive"].sum())
        else:
            pos_count = int((sub["signal"] >= spec.signal.positive_threshold).sum())
        if pos_count < min_pos:
            target_user = uid
            break

    assert target_user is not None, (
        f"Could not find a user with < {min_pos} positives in {content_type}"
    )

    resp = api_client.get(f"/v1/recommend?type={content_type}&user_id={target_user}&k=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "popularity"
    assert data["meta"]["source"] == "popularity"
    assert len(data["results"]) == 5
    # Popular results should not have personalized explanation reasons
    for r in data["results"]:
        assert r["reason"] is None
