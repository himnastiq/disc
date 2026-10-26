"""Contract tests asserting non-empty categories across API endpoints (FIX-42).

Asserts that categories are properly parsed as list[str] and non-empty across:
  1. GET /v1/recommend
  2. GET /v1/similar
  3. GET /v1/popular
  4. GET /v1/items/{item_id}
  5. GET /v1/items/search
  6. GET /v1/users/{user_id}/profile
  7. GET /v1/types/{type}/users
for both 'movies' and 'products'.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from engine.artifacts import load_artifacts

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


@pytest.fixture(scope="module")
def api_client() -> Any:
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_recommend(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/recommend returns non-empty categories list of strings."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    user_id = str(loaded.demo_users[0]["user_id"])

    resp = api_client.get(f"/v1/recommend?type={content_type}&user_id={user_id}&k=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0

    for item in data["results"]:
        cats = item["categories"]
        assert isinstance(cats, list), f"Expected list, got {type(cats)} for item {item['item_id']}"
        assert len(cats) > 0, (
            f"Expected non-empty categories for recommended item {item['item_id']}"
        )
        assert all(isinstance(c, str) and len(c) > 0 for c in cats)


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_similar(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/similar returns non-empty categories list of strings."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    item_id = str(loaded.items["item_id"].iloc[0])

    resp = api_client.get(f"/v1/similar?type={content_type}&item_id={item_id}&k=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0

    for item in data["results"]:
        cats = item["categories"]
        assert isinstance(cats, list), f"Expected list, got {type(cats)} for item {item['item_id']}"
        assert len(cats) > 0, f"Expected non-empty categories for similar item {item['item_id']}"
        assert all(isinstance(c, str) and len(c) > 0 for c in cats)


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_popular(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/popular returns non-empty categories list of strings."""
    resp = api_client.get(f"/v1/popular?type={content_type}&k=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0

    for item in data["results"]:
        cats = item["categories"]
        assert isinstance(cats, list), f"Expected list, got {type(cats)} for item {item['item_id']}"
        assert len(cats) > 0, f"Expected non-empty categories for popular item {item['item_id']}"
        assert all(isinstance(c, str) and len(c) > 0 for c in cats)


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_item_detail(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/items/{id} returns non-empty categories list of strings."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    item_id = str(loaded.items["item_id"].iloc[0])

    resp = api_client.get(f"/v1/items/{item_id}?type={content_type}")
    assert resp.status_code == 200
    item = resp.json()

    cats = item["categories"]
    assert isinstance(cats, list), f"Expected list, got {type(cats)}"
    assert len(cats) > 0, f"Expected non-empty categories for item {item_id}"
    assert all(isinstance(c, str) and len(c) > 0 for c in cats)


@pytest.mark.parametrize(
    ("content_type", "query"),
    [("movies", "a"), ("products", "a")],
)
def test_categories_non_empty_on_search(
    api_client: TestClient, content_type: str, query: str
) -> None:
    """Verify /v1/items/search returns non-empty categories on matched items."""
    resp = api_client.get(f"/v1/items/search?type={content_type}&q={query}&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) > 0

    for item in data["results"]:
        cats = item["categories"]
        assert isinstance(cats, list), f"Expected list, got {type(cats)} for item {item['item_id']}"
        assert len(cats) > 0, f"Expected non-empty categories for search item {item['item_id']}"
        assert all(isinstance(c, str) and len(c) > 0 for c in cats)


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_user_profile(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/users/{id}/profile returns top_categories with valid categories."""
    loaded = load_artifacts(get_artifacts_dir() / content_type, verify=False)
    user_id = str(loaded.demo_users[0]["user_id"])

    resp = api_client.get(f"/v1/users/{user_id}/profile?type={content_type}")
    assert resp.status_code == 200
    profile = resp.json()

    top_cats = profile["top_categories"]
    assert isinstance(top_cats, list), f"Expected list, got {type(top_cats)}"
    assert len(top_cats) > 0, f"Expected non-empty top_categories for user {user_id}"
    for cat_share in top_cats:
        assert isinstance(cat_share["category"], str)
        assert len(cat_share["category"]) > 0
        assert cat_share["count"] > 0
        assert 0.0 <= cat_share["share"] <= 1.0


@pytest.mark.parametrize("content_type", ["movies", "products"])
def test_categories_non_empty_on_users_list(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/types/{type}/users returns demo and sampled users with non-empty top_categories."""
    resp = api_client.get(f"/v1/types/{content_type}/users?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["users"]) > 0

    for user in data["users"]:
        cats = user["top_categories"]
        assert isinstance(cats, list), f"Expected list, got {type(cats)} for user {user['user_id']}"
        assert len(cats) > 0, f"Expected non-empty top_categories for user {user['user_id']}"
        assert all(isinstance(c, str) and len(c) > 0 for c in cats)
