"""Unit tests for standardized API error handling and schemas (Phase 7, P7.2)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from api.errors import (
    DuplicateIDsError,
    register_error_handlers,
)
from api.schemas import (
    ErrorResponse,
    HealthResponse,
    RecommendResponse,
    TypesResponse,
)
from engine.errors import (
    ColdStartUnsupported,
    UnknownItem,
    UnknownType,
    UnknownUser,
)


class DummyBody(BaseModel):
    number: int = Field(..., ge=1, le=10)


def create_test_error_app() -> FastAPI:
    """Create a minimal FastAPI app with registered error handlers for isolated testing."""
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/trigger-unknown-type")
    def trigger_unknown_type() -> Any:
        raise UnknownType("books", available=["movies", "products", "articles"])

    @test_app.get("/trigger-unknown-user")
    def trigger_unknown_user() -> Any:
        raise UnknownUser("user_xyz", content_type="movies")

    @test_app.get("/trigger-unknown-item")
    def trigger_unknown_item() -> Any:
        raise UnknownItem("item_999", content_type="products")

    @test_app.get("/trigger-cold-start-unsupported")
    def trigger_cold_start_unsupported() -> Any:
        raise ColdStartUnsupported("MockModel")

    @test_app.get("/trigger-duplicate-ids")
    def trigger_duplicate_ids() -> Any:
        raise DuplicateIDsError(duplicates=["item_1", "item_2"])

    @test_app.post("/trigger-validation")
    def trigger_validation(body: DummyBody) -> Any:
        return {"received": body.number}

    @test_app.get("/trigger-unhandled")
    def trigger_unhandled() -> Any:
        # Deliberately raise unhandled RuntimeError containing sensitive internal detail
        raise RuntimeError("Database password in plaintext: secret123")

    return test_app


def test_unknown_type_error_shape() -> None:
    """Verify that UnknownType raises 404 with code unknown_type and standard payload."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-unknown-type")

    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "unknown_type"
    assert "books" in data["error"]["message"]
    assert data["error"]["details"]["content_type"] == "books"
    assert "movies" in data["error"]["details"]["available"]

    # Validate against Pydantic ErrorResponse schema
    ErrorResponse.model_validate(data)


def test_unknown_user_error_shape() -> None:
    """Verify that UnknownUser raises 404 with code unknown_user and standard payload."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-unknown-user")

    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "unknown_user"
    assert "user_xyz" in data["error"]["message"]
    assert data["error"]["details"]["user_id"] == "user_xyz"
    assert data["error"]["details"]["content_type"] == "movies"

    ErrorResponse.model_validate(data)


def test_unknown_item_error_shape() -> None:
    """Verify that UnknownItem raises 404 with code unknown_item and standard payload."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-unknown-item")

    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "unknown_item"
    assert "item_999" in data["error"]["message"]
    assert data["error"]["details"]["item_id"] == "item_999"
    assert data["error"]["details"]["content_type"] == "products"

    ErrorResponse.model_validate(data)


def test_cold_start_unsupported_error_shape() -> None:
    """Verify that ColdStartUnsupported raises 409 with code cold_start_unsupported."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-cold-start-unsupported")

    assert resp.status_code == 409
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "cold_start_unsupported"
    assert "MockModel" in data["error"]["message"]
    assert data["error"]["details"]["model_name"] == "MockModel"

    ErrorResponse.model_validate(data)


def test_duplicate_ids_error_shape() -> None:
    """Verify that DuplicateIDsError raises 422 with code duplicate_ids."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-duplicate-ids")

    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "duplicate_ids"
    assert data["error"]["details"]["duplicates"] == ["item_1", "item_2"]

    ErrorResponse.model_validate(data)


def test_validation_error_shape() -> None:
    """Verify that FastAPI validation error returns 422 with code validation_error."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    # Pass invalid number out of bounds
    resp = client.post("/trigger-validation", json={"number": 999})

    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert isinstance(data["error"]["details"], list)
    assert len(data["error"]["details"]) > 0

    ErrorResponse.model_validate(data)


def test_http_not_found_standard_shape() -> None:
    """Verify that hitting a nonexistent endpoint returns standard error shape."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/nonexistent-endpoint-xyz")

    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"

    ErrorResponse.model_validate(data)


def test_catch_all_500_hides_stack_trace_and_secrets() -> None:
    """Verify that an unhandled 500 error hides stack traces and returns generic message."""
    app = create_test_error_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/trigger-unhandled")

    assert resp.status_code == 500
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "internal_error"
    assert data["error"]["message"] == "An internal server error occurred."
    assert data["error"]["details"] is None
    # Crucial security check: internal secret must NOT leak in response payload
    assert "secret123" not in resp.text
    assert "Traceback" not in resp.text

    ErrorResponse.model_validate(data)


def test_schema_models_instantiation() -> None:
    """Verify that key response models instantiate and validate without errors."""
    health = HealthResponse(status="ok", types={}, version="1.0.0")
    assert health.status == "ok"

    types = TypesResponse(types=[])
    assert types.types == []

    recs = RecommendResponse(content_type="movies", mode="personalized", k=0, results=[])
    assert recs.content_type == "movies"
