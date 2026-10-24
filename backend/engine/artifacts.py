"""Discovery Engine - Artifact persistence, manifest generation, and integrity verification (P2.10)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.config import compute_config_hash
from engine.errors import ArtifactCorruptError, ArtifactError
from engine.evaluation.harness import get_git_sha

if TYPE_CHECKING:
    from pathlib import Path

    from engine.schema import ContentTypeSpec

ARTIFACT_SCHEMA_VERSION = "1.0.0"


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hex digest of a file reading in 64KB blocks."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class LoadedArtifacts:
    """Container for verified, loaded artifacts ready for API serving."""

    manifest: dict[str, Any]
    items: pd.DataFrame
    interactions: pd.DataFrame
    users: pd.DataFrame
    metrics: dict[str, Any]
    demo_users: list[dict[str, Any]]
    model_dir: Path
    topn: pd.DataFrame | None = None


def save_artifacts(
    artifact_dir: Path,
    spec: ContentTypeSpec,
    items: pd.DataFrame,
    interactions: pd.DataFrame,
    users: pd.DataFrame,
    metrics: dict[str, Any],
    demo_users: list[dict[str, Any]],
    topn: pd.DataFrame | None = None,
    extra_files: dict[str, Any] | None = None,
) -> Path:
    """Save pipeline outputs and build a cryptographically signed manifest with SHA-256 checksums.

    Args:
        artifact_dir: Target directory (e.g. artifacts/movies).
        spec: Validated ContentTypeSpec.
        items: Canonical items catalogue.
        interactions: Canonical interactions (flagged with train/test).
        users: Precomputed user statistics and persona labels.
        metrics: Output from evaluation harness.
        demo_users: Selected diverse demo users list.
        topn: Optional precomputed top-N recommendations per known user.
        extra_files: Optional additional files to write before manifest hashing.

    Returns:
        Path: Path to the generated manifest.json file.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write core Parquet tables
    items.to_parquet(artifact_dir / "items.parquet", index=False)
    interactions.to_parquet(artifact_dir / "interactions.parquet", index=False)
    users.to_parquet(artifact_dir / "users.parquet", index=False)

    if topn is not None and not topn.empty:
        topn.to_parquet(artifact_dir / "topn.parquet", index=False)

    # 2. Write JSON metadata
    (artifact_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (artifact_dir / "demo_users.json").write_text(
        json.dumps(demo_users, indent=2), encoding="utf-8"
    )

    # 3. Write extra files if specified
    if extra_files:
        for rel_name, content in extra_files.items():
            out_p = artifact_dir / rel_name
            out_p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (dict, list)):
                out_p.write_text(json.dumps(content, indent=2), encoding="utf-8")
            elif isinstance(content, bytes):
                out_p.write_bytes(content)
            else:
                out_p.write_text(str(content), encoding="utf-8")

    # 4. Compute file checksums across all files (excluding manifest.json itself)
    file_checksums: dict[str, str] = {}
    for p in sorted(artifact_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel_path = p.relative_to(artifact_dir).as_posix()
            file_checksums[rel_path] = compute_file_sha256(p)

    # 5. Build and write manifest.json
    manifest_data: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "content_type": spec.type,
        "model_name": spec.model.name,
        "config_hash": compute_config_hash(spec),
        "git_sha": get_git_sha(),
        "dataset_variant": spec.dataset.variant,
        "created_at": datetime.now(UTC).isoformat(),
        "files": file_checksums,
    }

    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return manifest_path


def verify_artifacts(
    artifact_dir: Path,
    expected_version: str = ARTIFACT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Verify presence, schema version, and cryptographic checksums of artifact directory.

    Args:
        artifact_dir: Path to content type artifact directory.
        expected_version: Required artifact schema version string.

    Returns:
        dict[str, Any]: Validated manifest dictionary.

    Raises:
        ArtifactError: If manifest is missing or cannot be read.
        ArtifactCorruptError: If schema version mismatches, files are missing, or checksum fails.
    """
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        raise ArtifactError(f"Artifact directory does not exist: '{artifact_dir}'")

    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactError(
            f"Missing manifest.json in artifact directory '{artifact_dir}'. Pipeline may have failed or not run."
        )

    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ArtifactCorruptError(str(manifest_path), f"Failed to parse manifest.json: {e}") from e

    found_version = manifest.get("artifact_schema_version")
    if found_version != expected_version:
        raise ArtifactCorruptError(
            str(manifest_path),
            f"Artifact schema version mismatch: expected '{expected_version}', found '{found_version}'. Please retrain pipeline.",
        )

    files_dict: dict[str, str] = manifest.get("files", {})
    if not files_dict:
        raise ArtifactCorruptError(str(manifest_path), "Manifest contains no registered files.")

    for rel_path, expected_checksum in files_dict.items():
        file_path = artifact_dir / rel_path
        if not file_path.exists():
            raise ArtifactCorruptError(
                str(file_path),
                f"Required artifact file '{rel_path}' recorded in manifest is missing from disk.",
            )

        actual_checksum = compute_file_sha256(file_path)
        if actual_checksum != expected_checksum:
            raise ArtifactCorruptError(
                str(file_path),
                f"Checksum mismatch for '{rel_path}'. Expected '{expected_checksum}', but calculated '{actual_checksum}'. File is corrupt or modified.",
            )

    return manifest


def load_artifacts(
    artifact_dir: Path,
    verify: bool = True,
    expected_version: str = ARTIFACT_SCHEMA_VERSION,
) -> LoadedArtifacts:
    """Verify and load full artifact bundle for API serving.

    Args:
        artifact_dir: Directory containing artifacts and manifest.json.
        verify: Whether to verify cryptographic checksums and schema version before loading.
        expected_version: Required schema version string.

    Returns:
        LoadedArtifacts container.

    Raises:
        ArtifactError / ArtifactCorruptError on integrity or presence failure.
    """
    manifest = (
        verify_artifacts(artifact_dir, expected_version=expected_version)
        if verify
        else json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    )

    items_df = pd.read_parquet(artifact_dir / "items.parquet")
    interactions_df = pd.read_parquet(artifact_dir / "interactions.parquet")
    users_df = pd.read_parquet(artifact_dir / "users.parquet")
    metrics_data = json.loads((artifact_dir / "metrics.json").read_text(encoding="utf-8"))
    demo_users_data = json.loads((artifact_dir / "demo_users.json").read_text(encoding="utf-8"))

    topn_p = artifact_dir / "topn.parquet"
    topn_df = pd.read_parquet(topn_p) if topn_p.exists() else None

    model_dir = artifact_dir / "model"

    return LoadedArtifacts(
        manifest=manifest,
        items=items_df,
        interactions=interactions_df,
        users=users_df,
        metrics=metrics_data,
        demo_users=demo_users_data,
        model_dir=model_dir,
        topn=topn_df,
    )
