"""Unit tests for API security, authentication, size limits, and sanitization (Phase 7, P7.8)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.security import verify_api_key_bytes


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# ===========================================================================
# 1. Byte-level API Key Verification Function Tests
# ===========================================================================


def test_verify_api_key_bytes_exact_match() -> None:
    """Verify exact match returns True in constant time."""
    assert verify_api_key_bytes(b"secret_123", "secret_123") is True
    assert verify_api_key_bytes("secret_123", "secret_123") is True


def test_verify_api_key_bytes_mismatch() -> None:
    """Verify mismatched key returns False."""
    assert verify_api_key_bytes(b"wrong_secret", "secret_123") is False
    assert verify_api_key_bytes("wrong_secret", "secret_123") is False


def test_verify_api_key_bytes_none_or_empty() -> None:
    """Verify empty or None values handled safely."""
    # When no expected key configured, open access
    assert verify_api_key_bytes(None, None) is True
    assert verify_api_key_bytes("any", None) is True
    assert verify_api_key_bytes("any", "") is True

    # When expected key configured, None or empty raw header returns False
    assert verify_api_key_bytes(None, "secret_123") is False
    assert verify_api_key_bytes("", "secret_123") is False


def test_verify_api_key_bytes_non_ascii_and_surrogates() -> None:
    """Verify non-ASCII, surrogates, and malformed inputs never raise exceptions."""
    # Non-ASCII unicode string
    assert verify_api_key_bytes("café_🔑", "secret_123") is False

    # Raw non-ASCII bytes
    assert verify_api_key_bytes(b"\xc3\xa9\xff\xfe", "secret_123") is False

    # Lone surrogate string
    assert verify_api_key_bytes("bad_\ud800_surrogate", "secret_123") is False


# ===========================================================================
# 2. HTTP Request Authentication & Non-ASCII 401 Contract Tests
# ===========================================================================


def test_open_access_when_no_api_key_configured(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When RECOMMENDER_API_KEY is not set, endpoints are accessible without headers."""
    monkeypatch.delenv("RECOMMENDER_API_KEY", raising=False)
    resp = api_client.get("/v1/health")
    assert resp.status_code == 200


def test_missing_api_key_returns_401(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When RECOMMENDER_API_KEY is configured, missing X-API-Key returns 401 unauthorized."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "prod_secret_token_456")
    resp = api_client.get("/v1/types")
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "unauthorized"
    assert "Missing API key" in data["error"]["message"]


def test_invalid_api_key_returns_401(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When RECOMMENDER_API_KEY is configured, incorrect key returns 401 unauthorized."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "prod_secret_token_456")
    resp = api_client.get("/v1/types", headers={"X-API-Key": "incorrect_token"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "unauthorized"


def test_valid_api_key_succeeds(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When RECOMMENDER_API_KEY is configured, valid key succeeds with 200."""
    secret = "prod_secret_token_456"
    monkeypatch.setenv("RECOMMENDER_API_KEY", secret)
    resp = api_client.get("/v1/types", headers={"X-API-Key": secret})
    assert resp.status_code == 200


def test_non_ascii_api_key_returns_401_not_500(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance criteria: tests with a non-ASCII key header return 401, not 500."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "ascii_configured_secret")

    # Pass non-ASCII bytes as header value (mimicking raw HTTP transport)
    non_ascii_bytes = "café_🔑_invalid".encode("latin-1", errors="replace")
    resp = api_client.get("/v1/types", headers={"X-API-Key": non_ascii_bytes})

    assert resp.status_code == 401, (
        f"Expected 401 Unauthorized but got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["error"]["code"] == "unauthorized"


def test_exempt_paths_accessible_without_api_key(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify OpenAPI and documentation routes are exempt from API key requirement."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "prod_secret_token_456")
    resp_openapi = api_client.get("/openapi.json")
    assert resp_openapi.status_code == 200

    resp_docs = api_client.get("/docs")
    assert resp_docs.status_code == 200


def test_cors_options_preflight_exempt_from_api_key(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify CORS preflight OPTIONS requests are exempt from API key check."""
    monkeypatch.setenv("RECOMMENDER_API_KEY", "prod_secret_token_456")
    resp = api_client.options("/v1/recommend")
    assert resp.status_code != 401


# ===========================================================================
# 3. Payload Size and Input Length Limit Tests
# ===========================================================================


def test_payload_too_large_via_content_length(api_client: TestClient) -> None:
    """Verify request with Content-Length header > 1MB returns 413 payload_too_large."""
    large_payload = {"type": "movies", "history": [], "k": 10}
    headers = {"Content-Length": "2097152"}  # 2MB header
    resp = api_client.post("/v1/recommend/cold-start", json=large_payload, headers=headers)
    assert resp.status_code == 413
    data = resp.json()
    assert data["error"]["code"] == "payload_too_large"


def test_search_query_length_limits(api_client: TestClient) -> None:
    """Acceptance criteria: search query max 100 characters; longer query returns 422."""
    # 1. Valid 100 character query -> accepted (200)
    query_100 = "a" * 100
    resp_100 = api_client.get(f"/v1/items/search?type=movies&q={query_100}")
    assert resp_100.status_code == 200

    # 2. Invalid 101 character query -> rejected with 422 validation_error
    query_101 = "a" * 101
    resp_101 = api_client.get(f"/v1/items/search?type=movies&q={query_101}")
    assert resp_101.status_code == 422
    assert resp_101.json()["error"]["code"] == "validation_error"


def test_no_debug_stack_trace_on_internal_error(api_client: TestClient) -> None:
    """Acceptance criteria: 500 error responses return generic message without stack traces."""
    with (
        TestClient(api_client.app, raise_server_exceptions=False) as no_raise_client,
        pytest.MonkeyPatch.context() as mp,
    ):

        def broken_resolver(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Sensitive internal database exception at line 42 in /etc/secret.py")

        mp.setattr("api.routes.metadata.resolve_loaded_artifacts", broken_resolver)
        resp = no_raise_client.get("/v1/items/1?type=movies")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "internal_error"
        assert "Sensitive internal database" not in data["error"]["message"]
        assert "traceback" not in data["error"]["message"].lower()
        assert data["error"]["details"] is None
