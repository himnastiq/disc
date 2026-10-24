"""Unit and corruption tests for artifact persistence and verification (P2.10)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    load_artifacts,
    save_artifacts,
    verify_artifacts,
)
from engine.config import load_config
from engine.errors import ArtifactCorruptError, ArtifactError
from engine.schema import ContentTypeSpec


@pytest.fixture
def spec() -> ContentTypeSpec:
    return load_config("movies", fast=True)


@pytest.fixture
def sample_artifact_bundle(tmp_path: Path, spec: ContentTypeSpec) -> tuple[Path, ContentTypeSpec]:
    bundle_dir = tmp_path / "artifacts" / "movies"

    items_df = pd.DataFrame(
        [
            {"item_id": "i1", "title": "Movie 1", "categories": ["Action"]},
            {"item_id": "i2", "title": "Movie 2", "categories": ["Drama"]},
        ]
    )
    interactions_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "signal": 5.0, "timestamp": 100, "positive": True},
            {"user_id": "u2", "item_id": "i2", "signal": 4.0, "timestamp": 200, "positive": True},
        ]
    )
    users_df = pd.DataFrame(
        [
            {"user_id": "u1", "interaction_count": 1, "persona": "mainstream"},
            {"user_id": "u2", "interaction_count": 1, "persona": "niche"},
        ]
    )
    metrics_data = {"test_metric": 0.85, "k": 10}
    demo_users_data = [{"user_id": "u1", "persona": "mainstream"}]
    topn_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i2", "score": 0.9, "rank": 1},
        ]
    )

    save_artifacts(
        artifact_dir=bundle_dir,
        spec=spec,
        items=items_df,
        interactions=interactions_df,
        users=users_df,
        metrics=metrics_data,
        demo_users=demo_users_data,
        topn=topn_df,
    )
    return bundle_dir, spec


def test_save_and_load_roundtrip_success(
    sample_artifact_bundle: tuple[Path, ContentTypeSpec],
) -> None:
    bundle_dir, _ = sample_artifact_bundle

    # Verify manifest
    manifest = verify_artifacts(bundle_dir)
    assert manifest["artifact_schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert manifest["content_type"] == "movies"
    assert "items.parquet" in manifest["files"]
    assert "interactions.parquet" in manifest["files"]
    assert "users.parquet" in manifest["files"]
    assert "metrics.json" in manifest["files"]
    assert "demo_users.json" in manifest["files"]
    assert "topn.parquet" in manifest["files"]

    # Load artifacts
    loaded = load_artifacts(bundle_dir, verify=True)
    assert len(loaded.items) == 2
    assert len(loaded.interactions) == 2
    assert len(loaded.users) == 2
    assert loaded.topn is not None
    assert len(loaded.topn) == 1
    assert loaded.metrics["test_metric"] == 0.85
    assert loaded.demo_users[0]["user_id"] == "u1"


def test_missing_manifest_raises_artifact_error(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_bundle"
    empty_dir.mkdir()

    with pytest.raises(ArtifactError, match=r"Missing manifest\.json"):
        verify_artifacts(empty_dir)


def test_schema_version_mismatch_raises_artifact_corrupt_error(
    sample_artifact_bundle: tuple[Path, ContentTypeSpec],
) -> None:
    bundle_dir, _ = sample_artifact_bundle
    manifest_p = bundle_dir / "manifest.json"

    # Modify schema version in manifest
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    manifest["artifact_schema_version"] = "999.0.0"
    manifest_p.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArtifactCorruptError) as exc_info:
        verify_artifacts(bundle_dir)

    assert "version mismatch" in exc_info.value.reason.lower()
    assert "999.0.0" in exc_info.value.reason


def test_missing_file_raises_artifact_corrupt_error(
    sample_artifact_bundle: tuple[Path, ContentTypeSpec],
) -> None:
    bundle_dir, _ = sample_artifact_bundle
    items_p = bundle_dir / "items.parquet"
    assert items_p.exists()
    items_p.unlink()  # Delete recorded file

    with pytest.raises(ArtifactCorruptError) as exc_info:
        verify_artifacts(bundle_dir)

    assert "missing from disk" in exc_info.value.reason.lower()
    assert "items.parquet" in exc_info.value.reason


def test_bit_flip_corruption_raises_artifact_corrupt_error(
    sample_artifact_bundle: tuple[Path, ContentTypeSpec],
) -> None:
    bundle_dir, _ = sample_artifact_bundle
    metrics_p = bundle_dir / "metrics.json"

    # Corrupt by flipping one byte in metrics.json
    content = metrics_p.read_bytes()
    corrupted = bytearray(content)
    corrupted[10] ^= 0xFF
    metrics_p.write_bytes(corrupted)

    with pytest.raises(ArtifactCorruptError) as exc_info:
        verify_artifacts(bundle_dir)

    assert "checksum mismatch" in exc_info.value.reason.lower()
    assert "metrics.json" in exc_info.value.reason
