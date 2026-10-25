"""Property-based fuzz testing of Discovery Engine API endpoints (Phase 7, P7.10).

Fuzzes query parameters, path variables, and JSON request bodies using Hypothesis
to verify that every endpoint adheres to core R3 invariants and NEVER returns an
unhandled 500 Internal Server Error.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from api.main import create_app
from api.schemas import ColdStartResponse, PopularResponse, RecommendResponse, SimilarResponse
from engine import registry

CONTENT_TYPES = registry.types()

# Safe text strategy excluding lone surrogate characters (which are invalid in UTF-8)
text_strat = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=30)
type_strat = st.sampled_from(CONTENT_TYPES) | text_strat


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===========================================================================
# 1. Fuzz GET /v1/recommend
# ===========================================================================


@settings(max_examples=30, deadline=None)
@given(
    content_type=type_strat,
    user_id=text_strat,
    k=st.integers(min_value=-10, max_value=150),
    exclude_items=st.lists(text_strat, max_size=10),
)
def test_fuzz_recommend_endpoint(
    api_client: TestClient,
    content_type: str,
    user_id: str,
    k: int,
    exclude_items: list[str],
) -> None:
    """Fuzz /v1/recommend ensuring zero 500 responses and R3 invariants when 200."""
    params = {
        "type": content_type,
        "user_id": user_id,
        "k": k,
        "exclude": ",".join(exclude_items),
    }
    resp = api_client.get("/v1/recommend", params=params)

    # Acceptance invariant: ZERO 500 errors
    assert resp.status_code != 500, f"500 Internal Server Error on recommend: {resp.text}"

    if resp.status_code == 200:
        recs = RecommendResponse.model_validate(resp.json())
        assert recs.content_type == content_type
        assert recs.k <= max(0, k)
        assert len(recs.results) == recs.k

        seen: set[str] = set()
        prev_score = float("inf")
        excluded_set = set(exclude_items)
        for item in recs.results:
            assert item.item_id not in seen
            seen.add(item.item_id)
            assert item.item_id not in excluded_set
            assert item.score <= prev_score + 1e-6
            prev_score = item.score
            assert 0.0 <= item.display_score <= 1.0


# ===========================================================================
# 2. Fuzz POST /v1/recommend/cold-start
# ===========================================================================


@settings(max_examples=30, deadline=None)
@given(
    content_type=type_strat,
    k=st.integers(min_value=-5, max_value=120),
    history=st.lists(
        st.fixed_dictionaries(
            {
                "item_id": text_strat,
                "signal": st.one_of(
                    st.none(),
                    st.floats(min_value=-10.0, max_value=20.0, allow_nan=False),
                ),
            }
        ),
        max_size=30,
    ),
    exclude=st.lists(text_strat, max_size=10),
)
def test_fuzz_cold_start_endpoint(
    api_client: TestClient,
    content_type: str,
    k: int,
    history: list[dict[str, Any]],
    exclude: list[str],
) -> None:
    """Fuzz /v1/recommend/cold-start ensuring zero 500 errors."""
    payload = {
        "type": content_type,
        "k": k,
        "history": history,
        "exclude": exclude,
    }
    resp = api_client.post("/v1/recommend/cold-start", json=payload)

    # Acceptance invariant: ZERO 500 errors
    assert resp.status_code != 500, f"500 Internal Server Error on cold-start: {resp.text}"

    if resp.status_code == 200:
        cs = ColdStartResponse.model_validate(resp.json())
        assert cs.content_type == content_type
        assert cs.k <= max(0, k)
        assert len(cs.results) == cs.k

        seen: set[str] = set()
        prev_score = float("inf")
        history_ids = {str(h["item_id"]) for h in history}
        for item in cs.results:
            assert item.item_id not in seen
            seen.add(item.item_id)
            assert item.item_id not in history_ids
            assert item.score <= prev_score + 1e-6
            prev_score = item.score
            assert 0.0 <= item.display_score <= 1.0


# ===========================================================================
# 3. Fuzz GET /v1/items/search
# ===========================================================================


@settings(max_examples=30, deadline=None)
@given(
    content_type=type_strat,
    q=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=120),
    limit=st.integers(min_value=-5, max_value=120),
)
def test_fuzz_search_endpoint(
    api_client: TestClient,
    content_type: str,
    q: str,
    limit: int,
) -> None:
    """Fuzz search endpoint with random queries and unicode text."""
    params = {"type": content_type, "q": q, "limit": limit}
    resp = api_client.get("/v1/items/search", params=params)

    # Acceptance invariant: ZERO 500 errors
    assert resp.status_code != 500, f"500 Internal Server Error on search: {resp.text}"


# ===========================================================================
# 4. Fuzz GET /v1/popular and GET /v1/similar
# ===========================================================================


@settings(max_examples=25, deadline=None)
@given(
    content_type=type_strat,
    k=st.integers(min_value=-5, max_value=120),
)
def test_fuzz_popular_endpoint(
    api_client: TestClient,
    content_type: str,
    k: int,
) -> None:
    """Fuzz /v1/popular ensuring zero 500 errors."""
    params = {"type": content_type, "k": k}
    resp = api_client.get("/v1/popular", params=params)
    assert resp.status_code != 500

    if resp.status_code == 200:
        pop = PopularResponse.model_validate(resp.json())
        assert pop.content_type == content_type
        assert 0 < pop.k <= max(0, k)


@settings(max_examples=25, deadline=None)
@given(
    content_type=type_strat,
    item_id=text_strat,
    k=st.integers(min_value=-5, max_value=120),
)
def test_fuzz_similar_endpoint(
    api_client: TestClient,
    content_type: str,
    item_id: str,
    k: int,
) -> None:
    """Fuzz /v1/similar ensuring zero 500 errors and query item never returned."""
    params = {"type": content_type, "item_id": item_id, "k": k}
    resp = api_client.get("/v1/similar", params=params)
    assert resp.status_code != 500

    if resp.status_code == 200:
        sim = SimilarResponse.model_validate(resp.json())
        assert sim.content_type == content_type
        assert sim.query_item_id == item_id
        for it in sim.results:
            assert it.item_id != item_id


# ===========================================================================
# 5. Fuzz GET /v1/users/{user_id}/profile
# ===========================================================================


@settings(max_examples=25, deadline=None)
@given(
    content_type=type_strat,
    user_id=text_strat,
)
def test_fuzz_user_profile_endpoint(
    api_client: TestClient,
    content_type: str,
    user_id: str,
) -> None:
    """Fuzz /v1/users/{user_id}/profile ensuring zero 500 errors."""
    encoded_uid = quote(user_id, safe="")
    resp = api_client.get(f"/v1/users/{encoded_uid}/profile", params={"type": content_type})
    assert resp.status_code != 500
