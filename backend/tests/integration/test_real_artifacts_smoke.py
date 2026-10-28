"""Discovery Engine - Real Artifact Smoke Tests (FIX-48).

Executes comprehensive end-to-end smoke tests against real-world trained artifacts
across all supported content types (movies, products, articles):
- Tests 20 users and 30 items per content type.
- Exercises all 12 API endpoints.
- Asserts HTTP 200 for all valid requests (with documented 404 allowed only on /v1/similar for unindexed items).
- Asserts zero duplicate IDs across all item response lists.
- Asserts strictly non-empty category lists on all item responses.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_ROOT = REPO_ROOT / "artifacts"


@pytest.fixture(scope="module")
def real_api_client() -> Any:
    """Initialize FastAPI test client pointing strictly to real production artifacts."""
    for ctype in ("movies", "products", "articles"):
        manifest_path = ARTIFACTS_ROOT / ctype / "manifest.json"
        if not manifest_path.exists():
            pytest.skip(
                f"Real artifact manifest missing at {manifest_path}; skipping real_data smoke."
            )

    old_art = os.environ.get("ARTIFACT_DIR")
    os.environ["ARTIFACT_DIR"] = str(ARTIFACTS_ROOT)
    try:
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        if old_art is not None:
            os.environ["ARTIFACT_DIR"] = old_art
        else:
            os.environ.pop("ARTIFACT_DIR", None)


@pytest.mark.real_data
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_real_artifact_smoke_all_endpoints(
    real_api_client: TestClient,
    content_type: str,
) -> None:
    """Smoke test 20 users and 30 items per type across all endpoints with strict invariant assertions."""
    client = real_api_client

    # 1. Root and metadata endpoints
    r_health = client.get("/v1/health")
    assert r_health.status_code == 200, f"/v1/health failed with {r_health.status_code}"
    health_data = r_health.json()
    assert health_data["status"] == "ok"
    assert health_data["types"].get(content_type, {}).get("available") is True

    r_root_health = client.get("/health")
    assert r_root_health.status_code == 200

    r_types = client.get("/v1/types")
    assert r_types.status_code == 200
    type_ids = [t["id"] for t in r_types.json()]
    assert content_type in type_ids

    r_about = client.get("/v1/about")
    assert r_about.status_code == 200

    r_metrics = client.get(f"/v1/metrics?type={content_type}")
    assert r_metrics.status_code == 200
    metrics_data = r_metrics.json()
    assert metrics_data["content_type"] == content_type

    r_demo = client.get(f"/v1/types/{content_type}/demo-users")
    assert r_demo.status_code == 200
    demo_users = r_demo.json()
    assert len(demo_users) > 0

    # 2. Retrieve 20 users and 30 items
    r_users = client.get(f"/v1/types/{content_type}/users?limit=20")
    assert r_users.status_code == 200
    user_records = r_users.json()
    assert len(user_records) >= 20, f"Expected at least 20 users, got {len(user_records)}"
    user_ids = [u["user_id"] for u in user_records[:20]]

    r_items = client.get(f"/v1/types/{content_type}/items?limit=30")
    assert r_items.status_code == 200
    item_records = r_items.json()
    assert len(item_records) >= 30, f"Expected at least 30 items, got {len(item_records)}"
    item_ids = [it["item_id"] for it in item_records[:30]]

    # Invariant check: all catalogue items from /types/{type}/items must have non-empty categories
    for it in item_records[:30]:
        cats = it.get("categories")
        assert isinstance(cats, list) and len(cats) > 0, (
            f"Catalogue item {it.get('item_id')} in {content_type} has empty or non-list categories: {cats}"
        )

    # 3. Test 20 users across /v1/users/{user_id} and /v1/recommend
    for uid in user_ids:
        # User profile
        r_prof = client.get(f"/v1/users/{uid}?type={content_type}")
        assert r_prof.status_code == 200, f"/v1/users/{uid} returned {r_prof.status_code}"
        prof_data = r_prof.json()
        assert prof_data["user_id"] == uid
        assert isinstance(prof_data.get("top_categories"), list)

        # Recommendation
        r_rec = client.get(f"/v1/recommend?type={content_type}&user_id={uid}&k=10")
        assert r_rec.status_code == 200, f"/v1/recommend for {uid} returned {r_rec.status_code}"
        rec_data = r_rec.json()
        rec_items = rec_data.get("items", [])

        # Invariant: No duplicate IDs
        rec_ids = [it["item_id"] for it in rec_items]
        assert len(rec_ids) == len(set(rec_ids)), (
            f"Duplicate IDs found in recommend for user {uid}: {rec_ids}"
        )

        # Invariant: Non-empty categories
        for it in rec_items:
            cats = it.get("categories")
            assert isinstance(cats, list) and len(cats) > 0, (
                f"Recommended item {it.get('item_id')} has empty categories for user {uid}: {cats}"
            )

    # 4. Test 30 items across /v1/items/{item_id} and /v1/similar
    for iid in item_ids:
        # Item detail
        r_detail = client.get(f"/v1/items/{iid}?type={content_type}")
        assert r_detail.status_code == 200, f"/v1/items/{iid} returned {r_detail.status_code}"
        detail_data = r_detail.json()
        assert detail_data["item_id"] == iid
        cats = detail_data.get("categories")
        assert isinstance(cats, list) and len(cats) > 0, (
            f"Item detail for {iid} has empty categories: {cats}"
        )

        # Similar items (may return 200 or documented 404 if item has no similarity entries)
        r_sim = client.get(f"/v1/similar?type={content_type}&item_id={iid}&k=10")
        assert r_sim.status_code in (200, 404), (
            f"/v1/similar for {iid} returned unexpected status {r_sim.status_code}"
        )

        if r_sim.status_code == 200:
            sim_data = r_sim.json()
            sim_items = sim_data.get("items", [])

            # Invariant: No duplicate IDs
            sim_ids = [it["item_id"] for it in sim_items]
            assert len(sim_ids) == len(set(sim_ids)), (
                f"Duplicate IDs in similar for item {iid}: {sim_ids}"
            )

            # Invariant: Non-empty categories
            for it in sim_items:
                scats = it.get("categories")
                assert isinstance(scats, list) and len(scats) > 0, (
                    f"Similar item {it.get('item_id')} has empty categories: {scats}"
                )

    # 5. Test Popular endpoint
    r_pop = client.get(f"/v1/popular?type={content_type}&k=10")
    assert r_pop.status_code == 200
    pop_data = r_pop.json()
    pop_items = pop_data.get("items", [])
    pop_ids = [it["item_id"] for it in pop_items]
    assert len(pop_ids) == len(set(pop_ids)), f"Duplicate IDs in popular: {pop_ids}"
    for it in pop_items:
        cats = it.get("categories")
        assert isinstance(cats, list) and len(cats) > 0, (
            f"Popular item {it.get('item_id')} has empty categories: {cats}"
        )

    # 6. Test Cold-Start endpoint
    sample_history = [{"item_id": iid} for iid in item_ids[:3]]
    r_cs = client.post(
        "/v1/recommend/cold-start",
        json={"type": content_type, "history": sample_history, "k": 10},
    )
    assert r_cs.status_code == 200, f"Cold-start failed: {r_cs.text}"
    cs_data = r_cs.json()
    cs_items = cs_data.get("items", [])
    cs_ids = [it["item_id"] for it in cs_items]
    assert len(cs_ids) == len(set(cs_ids)), f"Duplicate IDs in cold-start: {cs_ids}"
    for it in cs_items:
        cats = it.get("categories")
        assert isinstance(cats, list) and len(cats) > 0, (
            f"Cold-start item {it.get('item_id')} has empty categories: {cats}"
        )

    # 7. Test Search endpoint
    sample_title = item_records[0].get("title", "")
    tokens = [w for w in sample_title.split() if len(w) >= 3 and w.isalnum()]
    query_term = tokens[0] if tokens else "a"
    r_search = client.get(f"/v1/search?type={content_type}&query={query_term}&limit=10")
    assert r_search.status_code == 200
    search_data = r_search.json()
    search_items = search_data.get("items", [])
    search_ids = [it["item_id"] for it in search_items]
    assert len(search_ids) == len(set(search_ids)), f"Duplicate IDs in search: {search_ids}"
    for it in search_items:
        cats = it.get("categories")
        assert isinstance(cats, list) and len(cats) > 0, (
            f"Search item {it.get('item_id')} has empty categories: {cats}"
        )
