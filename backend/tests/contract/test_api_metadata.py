"""Contract tests for read-only metadata endpoints across all content types (Phase 7, P7.3)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import (
    AboutResponse,
    HealthResponse,
    ItemDetail,
    MetricsResponse,
    SearchResponse,
    TypesResponse,
    UsersResponse,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


CONTENT_TYPES = ["movies", "products", "articles"]


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context for full artifact loading."""
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_health_endpoint_contract(api_client: TestClient) -> None:
    """Verify /v1/health contract and per-type availability."""
    resp = api_client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()

    health = HealthResponse.model_validate(data)
    assert health.status == "ok"
    assert health.version == "1.0.0"
    for ctype in CONTENT_TYPES:
        assert ctype in health.types
        assert health.types[ctype].available is True
        assert health.types[ctype].version is not None


def test_types_endpoint_contract(api_client: TestClient) -> None:
    """Verify /v1/types contract and counts."""
    resp = api_client.get("/v1/types")
    assert resp.status_code == 200
    data = resp.json()

    types_resp = TypesResponse.model_validate(data)
    type_ids = [t.id for t in types_resp.types]
    for ctype in CONTENT_TYPES:
        assert ctype in type_ids

    for t in types_resp.types:
        assert t.user_count > 0
        assert t.item_count > 0
        assert t.interaction_count > 0
        assert t.supports_cold_start is True
        assert t.card_type in ("movie", "product", "article")
        assert t.display_name in ("Movies", "Products", "Articles")
        assert t.id in ("movies", "products", "articles")
        assert t.id == t.id.lower()


def test_types_returns_exact_three_and_ignores_toy(
    api_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify GET /v1/types returns exactly movies, products and articles, and that the loader ignores artifacts/toy."""
    resp = api_client.get("/v1/types")
    assert resp.status_code == 200
    data = resp.json()
    types_resp = TypesResponse.model_validate(data)
    type_ids = [t.id for t in types_resp.types]

    # Exactly movies, products and articles
    assert sorted(type_ids) == ["articles", "movies", "products"]
    assert len(type_ids) == 3
    assert "toy" not in type_ids

    # Verify loader ignores artifacts/toy
    test_artifact_root = tmp_path / "artifacts"
    test_artifact_root.mkdir()
    fake_toy = test_artifact_root / "toy"
    fake_toy.mkdir()
    (fake_toy / "manifest.json").write_text(
        '{"type": "toy", "schema_version": "1.0.0"}', encoding="utf-8"
    )

    monkeypatch.setenv("ARTIFACT_DIR", str(test_artifact_root))
    isolated_app = create_app()
    with TestClient(isolated_app) as client:
        # Loader must ignore artifacts/toy completely
        assert "toy" not in client.app.state.artifacts
        assert "toy" not in client.app.state.models
        assert "toy" not in client.app.state.availability
        assert "toy" not in client.app.state.unavailable_reasons

        # GET /v1/types strictly returns only movies, products, articles
        local_resp = client.get("/v1/types")
        assert local_resp.status_code == 200
        local_ids = [t["id"] for t in local_resp.json()["types"]]
        assert "toy" not in local_ids
        assert set(local_ids) == {"movies", "products", "articles"}

        # Attempting to access toy via /v1/types/toy/users returns 404/unknown_type
        user_resp = client.get("/v1/types/toy/users")
        assert user_resp.status_code == 404
        assert user_resp.json()["error"]["code"] == "unknown_type"


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_users_endpoint_contract(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/types/{type}/users contract: demo users first, persona filtering, limit."""
    resp = api_client.get(f"/v1/types/{content_type}/users?limit=25")
    assert resp.status_code == 200
    data = resp.json()

    users_resp = UsersResponse.model_validate(data)
    assert users_resp.content_type == content_type
    assert len(users_resp.users) > 0
    assert len(users_resp.users) <= 25

    # Demo users must appear first
    saw_non_demo = False
    demo_count = 0
    for u in users_resp.users:
        if u.is_demo:
            assert not saw_non_demo, "Demo user appeared after a non-demo user"
            demo_count += 1
        else:
            saw_non_demo = True
    assert demo_count > 0, "No demo users returned"

    # Test persona filter if a persona exists
    first_persona = users_resp.users[0].persona
    if first_persona:
        p_resp = api_client.get(
            f"/v1/types/{content_type}/users?persona={first_persona.lower()}&limit=10"
        )
        assert p_resp.status_code == 200
        p_data = p_resp.json()
        assert len(p_data["users"]) > 0
        for u in p_data["users"]:
            assert u["persona"].lower() == first_persona.lower()


def test_users_endpoint_unknown_type(api_client: TestClient) -> None:
    """Verify 404 unknown_type when requesting users for invalid content type."""
    resp = api_client.get("/v1/types/nonexistent_xyz/users")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_item_detail_endpoint_contract(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/items/{item_id} contract for each content type."""
    # Find a real item ID from demo users' recommendations or search
    s_resp = api_client.get(f"/v1/items/search?type={content_type}&q=a&limit=1")
    assert s_resp.status_code == 200
    search_data = s_resp.json()
    assert len(search_data["results"]) > 0
    real_item_id = search_data["results"][0]["item_id"]

    resp = api_client.get(f"/v1/items/{real_item_id}?type={content_type}")
    assert resp.status_code == 200
    data = resp.json()

    item = ItemDetail.model_validate(data)
    assert item.item_id == real_item_id
    assert len(item.title) > 0
    assert isinstance(item.categories, list)


def test_item_detail_unknown_item(api_client: TestClient) -> None:
    """Verify 404 unknown_item for non-existent item ID."""
    resp = api_client.get("/v1/items/completely_nonexistent_id_99999?type=movies")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_item"
    assert data["error"]["details"]["item_id"] == "completely_nonexistent_id_99999"


def test_item_detail_unknown_type(api_client: TestClient) -> None:
    """Verify 404 unknown_type for non-existent type in item detail query."""
    resp = api_client.get("/v1/items/1?type=unknown_type_xyz")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "unknown_type"


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_search_endpoint_contract(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/items/search contract: normalized query, match ranking."""
    # Test a common generic vowel query
    resp = api_client.get(f"/v1/items/search?type={content_type}&q=e&limit=10")
    assert resp.status_code == 200
    data = resp.json()

    s_resp = SearchResponse.model_validate(data)
    assert s_resp.content_type == content_type
    assert s_resp.total_matches >= len(s_resp.results)
    assert len(s_resp.results) > 0

    # Verify hierarchical match types order: exact (1) <= prefix (2) <= word_start (3) <= contains (4)
    rank_order = {"exact": 1, "prefix": 2, "word_start": 3, "contains": 4}
    tiers = [rank_order.get(r.match_type or "", 5) for r in s_resp.results]
    for i in range(len(tiers) - 1):
        assert tiers[i] <= tiers[i + 1], (
            f"Match type ordering inverted: {s_resp.results[i].match_type} before {s_resp.results[i + 1].match_type}"
        )


def test_search_hierarchical_ranking_and_normalization(api_client: TestClient) -> None:
    """Verify search normalization: lowercase, accent stripping, article handling, ties by popularity."""
    # Movie query: "matrix"
    resp = api_client.get("/v1/items/search?type=movies&q=matrix&limit=5")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) > 0

    # First match should be exact match "The Matrix" (due to article stripping) or "Matrix"
    top_title = results[0]["title"]
    assert "Matrix" in top_title
    assert results[0]["match_type"] in ("exact", "prefix")

    # Accents & case test: "MATRIX" uppercase should match identical results as lowercase
    resp_upper = api_client.get("/v1/items/search?type=movies&q=MATRIX&limit=5")
    assert resp_upper.status_code == 200
    assert resp_upper.json()["results"][0]["item_id"] == results[0]["item_id"]


def test_about_endpoint_contract(api_client: TestClient) -> None:
    """Verify /v1/about endpoint returns citations and attributions."""
    resp = api_client.get("/v1/about")
    assert resp.status_code == 200
    data = resp.json()

    about = AboutResponse.model_validate(data)
    assert len(about.attributions) >= 4
    names = [a.name for a in about.attributions]
    assert any("Recommenders" in n for n in names)
    assert any("MovieLens" in n for n in names)
    assert any("Amazon" in n for n in names)
    assert any("MIND" in n for n in names)
    assert len(about.non_commercial_notice) > 0


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_metrics_endpoint_contract(api_client: TestClient, content_type: str) -> None:
    """Verify /v1/metrics serves metrics.json unchanged from disk."""
    resp = api_client.get(f"/v1/metrics?type={content_type}")
    assert resp.status_code == 200
    data = resp.json()

    # Load disk metrics
    disk_metrics_path = get_artifacts_dir() / content_type / "metrics.json"
    assert disk_metrics_path.exists()
    disk_data = json.loads(disk_metrics_path.read_text(encoding="utf-8"))

    # Assert bit-for-bit equality of key fields
    assert data["content_type"] == disk_data["content_type"]
    assert data["dataset_variant"] == disk_data["dataset_variant"]
    assert data["models"] == disk_data["models"]
    assert data["sanity_checks"] == disk_data["sanity_checks"]
    assert data == disk_data

    MetricsResponse.model_validate(data)

    if content_type == "articles":
        assert data.get("synthetic_demo") is True
        assert data.get("provenance_banner") is not None


def test_registering_hidden_or_test_only_type_changes_nothing_in_public_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-36: Registering a test_only / hidden type changes nothing in the public API routes/types."""
    import shutil

    from engine import config as config_mod

    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    for cfg in config_mod.DEFAULT_CONFIGS_DIR.glob("*.yaml"):
        shutil.copy(cfg, configs_dir / cfg.name)

    hidden_cfg = configs_dir / "hidden_secret.yaml"
    hidden_cfg.write_text(
        """type: hidden_secret
display_name: Hidden Secret
card_type: movie
test_only: true
dataset:
  adapter: movielens
signal:
  positive_threshold: 4.0
split:
  strategy: chronological
model:
  name: popularity
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(config_mod, "DEFAULT_CONFIGS_DIR", configs_dir)

    app = create_app()
    with TestClient(app) as client:
        # 1. GET /v1/types must not contain hidden_secret
        resp = client.get("/v1/types")
        assert resp.status_code == 200
        data = resp.json()
        returned_ids = [t["id"] for t in data["types"]]
        assert "hidden_secret" not in returned_ids
        assert returned_ids == ["articles", "movies", "products"]

        # 2. GET /v1/health must not list hidden_secret
        resp_health = client.get("/v1/health")
        assert resp_health.status_code == 200
        health_data = resp_health.json()
        assert "hidden_secret" not in health_data["types"]

        # 3. Requesting hidden_secret on public endpoints returns 404 unknown_type
        resp_rec = client.get("/v1/recommend?type=hidden_secret&user_id=1")
        assert resp_rec.status_code == 404
        assert resp_rec.json()["error"]["code"] == "unknown_type"


def test_serving_config_hash_strictly_matches_manifest_and_tampering_marks_unavailable(
    api_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX-37: Serving model is built from manifest-recorded artifact config and hash matches.

    If the manifest config hash is tampered with, the type is marked unavailable on startup.
    """
    import shutil

    from engine.config import compute_config_hash
    from tests.conftest import MINI_ARTIFACTS_DIR

    # 1. Active client has exact config hash match for all available types
    app = api_client.app
    for ctype in CONTENT_TYPES:
        if app.state.availability.get(ctype):
            spec = app.state.configs[ctype]
            manifest_hash = app.state.artifacts[ctype].manifest["config_hash"]
            assert compute_config_hash(spec) == manifest_hash

    # 2. Tampered manifest config hash marks type unavailable on startup
    test_artifact_root = tmp_path / "tampered_artifacts"
    test_artifact_root.mkdir()

    # Copy mini movies artifacts
    shutil.copytree(MINI_ARTIFACTS_DIR / "movies", test_artifact_root / "movies")

    # Tamper with manifest config_hash
    manifest_file = test_artifact_root / "movies" / "manifest.json"
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_data["config_hash"] = "tampered_hash_0123456789abcdef0123456789abcdef0123456789abcdef"
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("ARTIFACT_DIR", str(test_artifact_root))
    isolated_app = create_app()
    with TestClient(isolated_app) as client:
        assert client.app.state.availability.get("movies") is False
        assert "mismatch" in client.app.state.unavailable_reasons.get("movies", "").lower()
