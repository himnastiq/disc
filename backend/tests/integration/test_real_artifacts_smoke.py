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
from api.schemas import (
    ColdStartResponse,
    HealthResponse,
    ItemDetail,
    PopularResponse,
    RecommendResponse,
    SearchResponse,
    SimilarResponse,
    TypesResponse,
    UserProfileResponse,
    UsersResponse,
)

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

    # 1. Health and Root aliases
    r_health = client.get("/v1/health")
    assert r_health.status_code == 200, f"/v1/health returned {r_health.status_code}"
    health_data = HealthResponse.model_validate(r_health.json())
    assert health_data.status == "ok"
    assert health_data.types.get(content_type) is not None
    assert health_data.types[content_type].available is True

    r_root_health = client.get("/health")
    assert r_root_health.status_code == 200

    # 2. Types list
    r_types = client.get("/v1/types")
    assert r_types.status_code == 200
    types_data = TypesResponse.model_validate(r_types.json())
    type_ids = [t.id for t in types_data.types]
    assert content_type in type_ids

    # 3. About attribution
    r_about = client.get("/v1/about")
    assert r_about.status_code == 200

    # 4. Metrics endpoint
    r_metrics = client.get(f"/v1/metrics?type={content_type}")
    assert r_metrics.status_code == 200
    metrics_data = r_metrics.json()
    assert metrics_data["content_type"] == content_type

    # 5. Users exploration endpoint: fetch 20 users
    r_users = client.get(f"/v1/types/{content_type}/users?limit=25")
    assert r_users.status_code == 200
    users_data = UsersResponse.model_validate(r_users.json())
    assert len(users_data.users) >= 20, f"Expected at least 20 users, got {len(users_data.users)}"
    user_ids = [u.user_id for u in users_data.users[:20]]

    # 6. Items via search: fetch 30 items
    r_search_init = client.get(f"/v1/items/search?type={content_type}&q=a&limit=50")
    assert r_search_init.status_code == 200
    search_init_data = SearchResponse.model_validate(r_search_init.json())
    assert len(search_init_data.results) >= 30, (
        f"Expected at least 30 items from search, got {len(search_init_data.results)}"
    )
    items_sample = search_init_data.results[:30]
    item_ids = [it.item_id for it in items_sample]

    # Invariant: non-empty categories on initial items
    for it in items_sample:
        assert isinstance(it.categories, list) and len(it.categories) > 0, (
            f"Item {it.item_id} has empty categories: {it.categories}"
        )

    # 7. Test 20 users across /v1/users/{user_id}/profile and /v1/recommend
    for uid in user_ids:
        # User profile
        r_prof = client.get(f"/v1/users/{uid}/profile?type={content_type}")
        assert r_prof.status_code == 200, f"/v1/users/{uid}/profile returned {r_prof.status_code}"
        prof_data = UserProfileResponse.model_validate(r_prof.json())
        assert prof_data.user_id == uid

        # Recommend
        r_rec = client.get(f"/v1/recommend?type={content_type}&user_id={uid}&k=10")
        assert r_rec.status_code == 200, f"/v1/recommend for {uid} returned {r_rec.status_code}"
        rec_data = RecommendResponse.model_validate(r_rec.json())
        rec_ids = [it.item_id for it in rec_data.results]

        # Invariant: No duplicate IDs
        assert len(rec_ids) == len(set(rec_ids)), (
            f"Duplicate IDs in recommend for user {uid}: {rec_ids}"
        )

        # Invariant: Non-empty categories
        for it in rec_data.results:
            assert isinstance(it.categories, list) and len(it.categories) > 0, (
                f"Recommended item {it.item_id} has empty categories: {it.categories}"
            )

    # 8. Test 30 items across /v1/items/{item_id} and /v1/similar
    for iid in item_ids:
        # Item detail
        r_detail = client.get(f"/v1/items/{iid}?type={content_type}")
        assert r_detail.status_code == 200, f"/v1/items/{iid} returned {r_detail.status_code}"
        detail_data = ItemDetail.model_validate(r_detail.json())
        assert detail_data.item_id == iid
        assert isinstance(detail_data.categories, list) and len(detail_data.categories) > 0, (
            f"Item detail for {iid} has empty categories: {detail_data.categories}"
        )

        # Similar items
        r_sim = client.get(f"/v1/similar?type={content_type}&item_id={iid}&k=10")
        assert r_sim.status_code in (200, 404), (
            f"/v1/similar for {iid} returned unexpected status {r_sim.status_code}"
        )

        if r_sim.status_code == 200:
            sim_data = SimilarResponse.model_validate(r_sim.json())
            sim_ids = [it.item_id for it in sim_data.results]

            # Invariant: No duplicate IDs
            assert len(sim_ids) == len(set(sim_ids)), (
                f"Duplicate IDs in similar for item {iid}: {sim_ids}"
            )

            # Invariant: Non-empty categories
            for it in sim_data.results:
                assert isinstance(it.categories, list) and len(it.categories) > 0, (
                    f"Similar item {it.item_id} has empty categories: {it.categories}"
                )

    # 9. Popular endpoint
    r_pop = client.get(f"/v1/popular?type={content_type}&k=10")
    assert r_pop.status_code == 200
    pop_data = PopularResponse.model_validate(r_pop.json())
    pop_ids = [it.item_id for it in pop_data.results]
    assert len(pop_ids) == len(set(pop_ids)), f"Duplicate IDs in popular: {pop_ids}"
    for it in pop_data.results:
        assert isinstance(it.categories, list) and len(it.categories) > 0, (
            f"Popular item {it.item_id} has empty categories: {it.categories}"
        )

    # 10. Cold-start endpoint
    cold_history = [{"item_id": iid} for iid in item_ids[:3]]
    r_cs = client.post(
        "/v1/recommend/cold-start",
        json={"type": content_type, "history": cold_history, "k": 10},
    )
    assert r_cs.status_code == 200, f"Cold-start failed: {r_cs.text}"
    cs_data = ColdStartResponse.model_validate(r_cs.json())
    cs_ids = [it.item_id for it in cs_data.results]
    assert len(cs_ids) == len(set(cs_ids)), f"Duplicate IDs in cold-start: {cs_ids}"
    for it in cs_data.results:
        assert isinstance(it.categories, list) and len(it.categories) > 0, (
            f"Cold-start item {it.item_id} has empty categories: {it.categories}"
        )

    # 11. Search endpoint
    sample_item = items_sample[0]
    words = [w for w in sample_item.title.split() if len(w) >= 3 and w.isalnum()]
    q_term = words[0] if words else "a"
    r_search = client.get(f"/v1/items/search?type={content_type}&q={q_term}&limit=10")
    assert r_search.status_code == 200
    search_res = SearchResponse.model_validate(r_search.json())
    search_ids = [it.item_id for it in search_res.results]
    assert len(search_ids) == len(set(search_ids)), f"Duplicate IDs in search: {search_ids}"
    for it in search_res.results:
        assert isinstance(it.categories, list) and len(it.categories) > 0, (
            f"Search item {it.item_id} has empty categories: {it.categories}"
        )
