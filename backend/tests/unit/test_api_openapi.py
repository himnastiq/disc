"""Unit tests for OpenAPI export and schema stability check (Phase 7, P7.9)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from scripts.export_openapi import DEFAULT_OUTPUT_PATH, export_openapi, get_openapi_schema

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_PATHS = {
    "/v1/about",
    "/v1/health",
    "/v1/items/search",
    "/v1/items/{item_id}",
    "/v1/metrics",
    "/v1/popular",
    "/v1/recommend",
    "/v1/recommend/cold-start",
    "/v1/similar",
    "/v1/types",
    "/v1/types/{type}/users",
    "/v1/users/{user_id}/profile",
}


def test_committed_openapi_matches_generated_schema() -> None:
    """Acceptance test: committed openapi.json is identical to generated OpenAPI schema."""
    assert DEFAULT_OUTPUT_PATH.exists(), f"Missing committed OpenAPI schema at: {DEFAULT_OUTPUT_PATH}"
    result = export_openapi(DEFAULT_OUTPUT_PATH, check_only=True)
    assert result == 0, "Committed openapi.json drifts from generated FastAPI schema."


def test_openapi_contains_all_endpoints() -> None:
    """Verify that all 12 discovery engine endpoints are registered in OpenAPI schema."""
    schema = get_openapi_schema()
    registered_paths = set(schema.get("paths", {}).keys())

    assert EXPECTED_PATHS.issubset(registered_paths), (
        f"Missing expected paths in OpenAPI schema: {EXPECTED_PATHS - registered_paths}"
    )


def test_openapi_metadata_and_structure() -> None:
    """Verify OpenAPI info metadata and valid JSON structure."""
    schema = get_openapi_schema()
    assert schema.get("openapi", "").startswith("3.")
    info = schema.get("info", {})
    assert info.get("title") == "Discovery Engine"
    assert info.get("version") == "1.0.0"


def test_divergence_detection_in_check_mode(tmp_path: Path) -> None:
    """Verify export_openapi with check_only=True returns 1 when schema diverges."""
    dummy_file = tmp_path / "divergent_openapi.json"
    dummy_file.write_text(json.dumps({"openapi": "3.1.0", "paths": {}}), encoding="utf-8")

    res = export_openapi(output_path=dummy_file, check_only=True)
    assert res == 1
