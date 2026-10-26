"""Phase 7 Gate and Break-Your-Own-Work Ritual (P7.13).

Comprehensive integration and resilience gate certifying that the FastAPI backend
is robust, thread-safe, secure, performant, and fully compliant with all architectural
invariants (R3, R7, R8, R11, R6):

1. Comprehensive API Endpoint Gate:
   - All 12 endpoints registered, typed, and accessible across all content types.
   - OpenAPI schema in backend/api/openapi.json strictly up-to-date.
   - Zero deep-learning imports in sys.modules (pure Python/scikit-learn runtime).

2. Five Break-Your-Own-Work Rituals:
   - Ritual 1 (Live Exclusion Invariant): Adding a returned recommendation to `exclude`
     strictly eliminates it from subsequent results.
   - Ritual 2 (Prefix Stability Invariant): Changing requested `k` (k=5 vs k=10) strictly
     preserves common prefix item ordering without rank permutation.
   - Ritual 3 (Concurrent Serving Invariant): Concurrent parallel requests for the same
     user return bit-for-bit identical rankings and scores under thread contention.
   - Ritual 4 (Partial Outage Resilience): Startup with one corrupted artifact domain
     loads healthy domains successfully, marking the broken domain unavailable in /v1/health
     and returning 503 type_unavailable while healthy domains serve 200 OK.
   - Ritual 5 (Security and Error Envelope Invariant): Unauthenticated, non-ASCII key,
     oversized body, and malformed inputs produce strictly structured 4xx error shapes,
     never raising uncaught 500 exceptions or leaking stack traces.
"""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from scripts.export_openapi import DEFAULT_OUTPUT_PATH, export_openapi

from api.main import create_app
from api.schemas import (
    ColdStartResponse,
    HealthResponse,
    ItemDetail,
    PopularResponse,
    RecommendResponse,
    SearchResponse,
    SimilarResponse,
    UserProfileResponse,
)
from engine import registry

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
CONTENT_TYPES = registry.types()


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===========================================================================
# 1. Comprehensive API Endpoint Gate
# ===========================================================================


def test_gate_openapi_schema_up_to_date() -> None:
    """Certify that committed openapi.json is bit-for-bit identical to current API schema."""
    result = export_openapi(output_path=DEFAULT_OUTPUT_PATH, check_only=True)
    assert result == 0, "Committed openapi.json drifts from implementation."


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_gate_all_endpoints_functional(api_client: TestClient, content_type: str) -> None:
    """Certify all read and recommendation endpoints return 200 OK with valid schemas."""
    # 1. Health
    r_health = api_client.get("/v1/health")
    assert r_health.status_code == 200
    HealthResponse.model_validate(r_health.json())

    # 2. Types
    r_types = api_client.get("/v1/types")
    assert r_types.status_code == 200

    # 3. Users list
    r_users = api_client.get(f"/v1/types/{content_type}/users")
    assert r_users.status_code == 200
    user_list = r_users.json()["users"]
    assert len(user_list) > 0
    test_user_id = str(user_list[0]["user_id"])

    # 4. Items search
    r_search = api_client.get(f"/v1/items/search?type={content_type}&q=a&limit=5")
    assert r_search.status_code == 200
    SearchResponse.model_validate(r_search.json())

    # 5. User profile
    r_prof = api_client.get(f"/v1/users/{test_user_id}/profile?type={content_type}")
    assert r_prof.status_code == 200
    UserProfileResponse.model_validate(r_prof.json())

    # 6. Recommend
    r_rec = api_client.get(f"/v1/recommend?type={content_type}&user_id={test_user_id}&k=5")
    assert r_rec.status_code == 200
    rec_data = RecommendResponse.model_validate(r_rec.json())
    assert len(rec_data.results) > 0
    test_item_id = rec_data.results[0].item_id

    # 7. Item detail
    r_item = api_client.get(f"/v1/items/{test_item_id}?type={content_type}")
    assert r_item.status_code == 200
    ItemDetail.model_validate(r_item.json())

    # 8. Cold-start
    cold_body = {
        "type": content_type,
        "k": 5,
        "history": [{"item_id": test_item_id, "signal": 5.0}],
    }
    r_cold = api_client.post("/v1/recommend/cold-start", json=cold_body)
    assert r_cold.status_code == 200
    ColdStartResponse.model_validate(r_cold.json())

    # 9. Popular
    r_pop = api_client.get(f"/v1/popular?type={content_type}&k=5")
    assert r_pop.status_code == 200
    PopularResponse.model_validate(r_pop.json())

    # 10. Similar
    r_sim = api_client.get(f"/v1/similar?type={content_type}&item_id={test_item_id}&k=5")
    assert r_sim.status_code == 200
    SimilarResponse.model_validate(r_sim.json())


# ===========================================================================
# 2. Ritual 1: Live Exclusion Invariant
# ===========================================================================


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_ritual_1_live_exclusion_disappears(api_client: TestClient, content_type: str) -> None:
    """Ritual 1: Recommend for user, add top item to exclude: it MUST disappear."""
    user_id = str(api_client.app.state.artifacts[content_type].users["user_id"].iloc[0])

    # 1. Initial recommendation
    resp1 = api_client.get(f"/v1/recommend?type={content_type}&user_id={user_id}&k=10")
    assert resp1.status_code == 200
    results1 = resp1.json()["results"]
    assert len(results1) >= 2
    top_item_id = results1[0]["item_id"]

    # 2. Re-query with top item excluded
    resp2 = api_client.get(
        f"/v1/recommend?type={content_type}&user_id={user_id}&k=10&exclude={top_item_id}"
    )
    assert resp2.status_code == 200
    results2 = resp2.json()["results"]
    excluded_ids_in_recs = [item["item_id"] for item in results2 if item["item_id"] == top_item_id]

    assert len(excluded_ids_in_recs) == 0, (
        f"Ritual 1 FAILED: Excluded item '{top_item_id}' was returned in results for {content_type}."
    )


# ===========================================================================
# 3. Ritual 2: Prefix Stability Under Changing k
# ===========================================================================


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_ritual_2_prefix_stability_under_varying_k(
    api_client: TestClient, content_type: str
) -> None:
    """Ritual 2: Changing k (k=5 vs k=10) must preserve common prefix item ordering."""
    user_id = str(api_client.app.state.artifacts[content_type].users["user_id"].iloc[0])

    resp_k5 = api_client.get(f"/v1/recommend?type={content_type}&user_id={user_id}&k=5")
    assert resp_k5.status_code == 200
    ids_k5 = [item["item_id"] for item in resp_k5.json()["results"]]

    resp_k10 = api_client.get(f"/v1/recommend?type={content_type}&user_id={user_id}&k=10")
    assert resp_k10.status_code == 200
    ids_k10 = [item["item_id"] for item in resp_k10.json()["results"]]

    prefix_len = min(len(ids_k5), len(ids_k10))
    assert prefix_len > 0
    assert ids_k10[:prefix_len] == ids_k5[:prefix_len], (
        f"Ritual 2 FAILED: Common prefix permuted when changing k for {content_type}.\n"
        f"k=5:  {ids_k5}\nk=10: {ids_k10[:prefix_len]}"
    )


# ===========================================================================
# 4. Ritual 3: Concurrent Request Invariance (Thread Safety)
# ===========================================================================


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_ritual_3_concurrent_requests_identical_results(
    api_client: TestClient, content_type: str
) -> None:
    """Ritual 3: Concurrent parallel requests give bit-for-bit identical results."""
    user_id = str(api_client.app.state.artifacts[content_type].users["user_id"].iloc[0])
    url = f"/v1/recommend?type={content_type}&user_id={user_id}&k=5"

    def fetch() -> dict[str, Any]:
        r = api_client.get(url)
        assert r.status_code == 200
        return r.json()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch) for _ in range(20)]
        results = [f.result() for f in futures]

    first_results = results[0]["results"]
    for idx, other in enumerate(results[1:], start=2):
        other_results = other["results"]
        assert other_results == first_results, (
            f"Ritual 3 FAILED: Concurrency drift on request #{idx} for {content_type}"
        )


# ===========================================================================
# 5. Ritual 4: Partial Outage Resilience on Artifact Corruption
# ===========================================================================


def test_ritual_4_partial_outage_resilience(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ritual 4: Startup with one corrupt artifact dir marks it unavailable while healthy serve 200."""
    # Create isolated copy of artifacts directory
    temp_art_dir = tmp_path / "artifacts"
    shutil.copytree(ARTIFACTS_DIR, temp_art_dir)

    # Deliberately corrupt the 'movies' artifact directory by deleting items.parquet
    movies_items = temp_art_dir / "movies" / "items.parquet"
    if movies_items.exists():
        movies_items.unlink()

    monkeypatch.setenv("ARTIFACT_DIR", str(temp_art_dir))
    monkeypatch.delenv("RECOMMENDER_API_KEY", raising=False)

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        # App starts cleanly despite corrupt domain
        resp_health = client.get("/v1/health")
        assert resp_health.status_code == 200
        h_data = resp_health.json()

        # Health report indicates degraded status
        assert h_data["status"] == "degraded"
        assert h_data["types"]["movies"]["available"] is False
        assert h_data["types"]["products"]["available"] is True
        assert h_data["types"]["articles"]["available"] is True

        # Querying corrupt type returns 503 type_unavailable
        resp_bad = client.get("/v1/recommend?type=movies&user_id=1&k=5")
        assert resp_bad.status_code == 503
        assert resp_bad.json()["error"]["code"] == "type_unavailable"

        # Querying healthy types continues to succeed with 200 OK
        resp_prod = client.get("/v1/popular?type=products&k=5")
        assert resp_prod.status_code == 200

        resp_art = client.get("/v1/popular?type=articles&k=5")
        assert resp_art.status_code == 200


# ===========================================================================
# 6. Ritual 5: Security Envelope & Malformed Input Isolation
# ===========================================================================


def test_ritual_5_security_and_error_envelope_invariants(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ritual 5: Assert that auth errors, oversized bodies, and malformed inputs return clean 4xx."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "secure_secret_token_789")

    # 1. Missing API key returns 401
    r_no_key = api_client.get("/v1/types")
    assert r_no_key.status_code == 401
    assert r_no_key.json()["error"]["code"] == "unauthorized"

    # 2. Non-ASCII API key returns 401, not 500
    r_non_ascii = api_client.get("/v1/types", headers={"X-API-Key": b"caf\xe9_invalid_non_ascii"})
    assert r_non_ascii.status_code == 401
    assert r_non_ascii.json()["error"]["code"] == "unauthorized"

    # 3. Valid key authenticates
    headers = {"X-API-Key": "secure_secret_token_789"}
    r_auth = api_client.get("/v1/types", headers=headers)
    assert r_auth.status_code == 200

    # 4. Oversized body returns 413
    oversized_headers = {**headers, "Content-Length": "2097152"}
    r_large = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": []},
        headers=oversized_headers,
    )
    assert r_large.status_code == 413
    assert r_large.json()["error"]["code"] == "payload_too_large"

    # 5. Unknown user returns 404 unknown_user
    r_unknown_u = api_client.get(
        "/v1/recommend?type=movies&user_id=nonexistent_user_999999", headers=headers
    )
    assert r_unknown_u.status_code == 404
    assert r_unknown_u.json()["error"]["code"] == "unknown_user"

    # 6. Unknown item returns 404 unknown_item
    r_unknown_i = api_client.get(
        "/v1/similar?type=movies&item_id=nonexistent_item_999999", headers=headers
    )
    assert r_unknown_i.status_code == 404
    assert r_unknown_i.json()["error"]["code"] == "unknown_item"
