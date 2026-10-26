"""Contract tests for GET /v1/users/{user_id}/profile verifying direct pandas agreement (Phase 7, P7.4)."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import UserProfileResponse
from engine.artifacts import load_artifacts
from engine.config import load_config

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
def test_user_profile_matches_direct_pandas_computation(
    api_client: TestClient, content_type: str
) -> None:
    """Acceptance requirement: values match a direct pandas computation in tests."""
    type_dir = get_artifacts_dir() / content_type
    loaded = load_artifacts(type_dir, verify=False)
    spec = load_config(content_type, fast=True)

    # Select a real demo user
    assert len(loaded.demo_users) > 0
    test_user_id = str(loaded.demo_users[0]["user_id"])

    # 1. Direct pandas computation
    user_interactions = loaded.interactions[
        loaded.interactions["user_id"].astype(str) == test_user_id
    ]
    assert len(user_interactions) > 0, f"No interactions for test user {test_user_id}"

    user_matches = loaded.users[loaded.users["user_id"].astype(str) == test_user_id]
    user_row = user_matches.iloc[0] if not user_matches.empty else None

    expected_interaction_count = len(user_interactions)
    if "positive" in user_interactions.columns:
        expected_positive_count = int(user_interactions["positive"].sum())
    else:
        threshold = spec.signal.positive_threshold
        expected_positive_count = int((user_interactions["signal"] >= threshold).sum())

    expected_first = (
        int(user_row["first_timestamp"])
        if user_row is not None and "first_timestamp" in user_row
        else int(user_interactions["timestamp"].min())
    )
    expected_last = (
        int(user_row["last_timestamp"])
        if user_row is not None and "last_timestamp" in user_row
        else int(user_interactions["timestamp"].max())
    )
    expected_persona = str(user_row["persona"]) if user_row is not None else None

    # Expected recent 10 items
    sorted_df = user_interactions.sort_values(by="timestamp", ascending=False).head(10)
    expected_recent_ids = sorted_df["item_id"].astype(str).tolist()

    # Expected top categories
    cat_counts: Counter[str] = Counter()
    item_cats_map: dict[str, list[str]] = {}
    for _, irow in loaded.items.iterrows():
        raw_c = irow.get("categories")
        if isinstance(raw_c, (list, tuple)):
            item_cats_map[str(irow["item_id"])] = [str(c) for c in raw_c if c]

    for _, row in user_interactions.iterrows():
        for cat in item_cats_map.get(str(row["item_id"]), []):
            cat_counts[cat] += 1

    expected_top_cat_names = [c for c, _ in cat_counts.most_common()]

    # 2. Call API endpoint
    resp = api_client.get(f"/v1/users/{test_user_id}/profile?type={content_type}")
    assert resp.status_code == 200
    data = resp.json()

    # 3. Assert agreement between API and direct pandas computation
    profile = UserProfileResponse.model_validate(data)
    assert profile.user_id == test_user_id
    assert profile.content_type == content_type
    assert profile.interaction_count == expected_interaction_count
    assert profile.positive_count == expected_positive_count
    assert profile.first_activity == expected_first
    assert profile.last_activity == expected_last
    assert profile.persona == expected_persona

    # Recent items must match in exact sequence
    returned_recent_ids = [r.item_id for r in profile.recent_items]
    assert returned_recent_ids == expected_recent_ids
    assert len(profile.recent_items) <= 10

    # Top categories order and counts must agree
    returned_cat_names = [c.category for c in profile.top_categories]
    assert returned_cat_names == expected_top_cat_names

    for c in profile.top_categories:
        assert c.count == cat_counts[c.category]
        assert 0.0 <= c.share <= 1.0


def test_user_profile_unknown_user(api_client: TestClient) -> None:
    """Verify 404 unknown_user for non-existent user."""
    resp = api_client.get("/v1/users/nonexistent_user_99999/profile?type=movies")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_user"
    assert data["error"]["details"]["user_id"] == "nonexistent_user_99999"


def test_user_profile_unknown_type(api_client: TestClient) -> None:
    """Verify 404 unknown_type for non-existent content type."""
    resp = api_client.get("/v1/users/1/profile?type=bogus_type_xyz")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"
