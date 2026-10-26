"""Discovery Engine - Artifact persistence, manifest generation, and integrity verification (P2.10)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.config import compute_config_hash
from engine.errors import ArtifactCorruptError, ArtifactError


def get_git_sha() -> str:
    """Retrieve current git commit SHA, or 'unknown' if git is unavailable."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


if TYPE_CHECKING:
    from engine.schema import ContentTypeSpec

ARTIFACT_SCHEMA_VERSION = "1.0.0"
TEXT_EXTENSIONS = {".json", ".md", ".txt", ".csv", ".yaml", ".yml"}


def write_text_file(path: Path, content: str) -> None:
    """Write text content to file ensuring LF (\\n) line endings across all platforms."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    path.write_bytes(normalized.encode("utf-8"))


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a file.

    For text files (.json, .md, .txt, .csv, .yaml, .yml), line endings are normalized
    (b'\\r\\n' -> b'\\n') prior to hashing so checksums are invariant to CRLF/LF conversions.
    Binary files (.parquet, .npz, .npy, etc.) are hashed as raw bytes.
    """
    hasher = hashlib.sha256()
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        raw = file_path.read_bytes()
        hasher.update(raw.replace(b"\r\n", b"\n"))
    else:
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
    # Atomic write pattern: Stage into a temporary sibling directory, then swap (F-011)
    artifact_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_id = uuid.uuid4().hex[:8]
    stage_dir = artifact_dir.parent / f".tmp_{artifact_dir.name}_{stage_id}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Pre-populate staging directory with existing auxiliary artifacts (e.g. model/ or extra files)
        if artifact_dir.exists():
            for child in artifact_dir.iterdir():
                if child.name in (
                    "items.parquet",
                    "interactions.parquet",
                    "users.parquet",
                    "topn.parquet",
                    "metrics.json",
                    "demo_users.json",
                    "manifest.json",
                ):
                    continue
                if child.is_dir():
                    shutil.copytree(child, stage_dir / child.name, dirs_exist_ok=True)
                elif child.is_file():
                    shutil.copy2(child, stage_dir / child.name)

        # 1. Write core Parquet tables into staging directory
        items.to_parquet(stage_dir / "items.parquet", index=False)
        interactions.to_parquet(stage_dir / "interactions.parquet", index=False)
        users.to_parquet(stage_dir / "users.parquet", index=False)

        if topn is not None and not topn.empty:
            topn.to_parquet(stage_dir / "topn.parquet", index=False)

        # 2. Write JSON metadata
        write_text_file(stage_dir / "metrics.json", json.dumps(metrics, indent=2))
        write_text_file(stage_dir / "demo_users.json", json.dumps(demo_users, indent=2))

        # 3. Write extra files if specified
        if extra_files:
            for rel_name, content in extra_files.items():
                out_p = stage_dir / rel_name
                out_p.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, (dict, list)):
                    write_text_file(out_p, json.dumps(content, indent=2))
                elif isinstance(content, bytes):
                    out_p.write_bytes(content)
                else:
                    s_val = str(content)
                    if out_p.suffix.lower() in TEXT_EXTENSIONS:
                        write_text_file(out_p, s_val)
                    else:
                        out_p.write_text(s_val, encoding="utf-8")

        # 4. Compute file checksums across all files in staging directory (excluding manifest.json itself)
        file_checksums: dict[str, str] = {}
        for p in sorted(stage_dir.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                rel_path = p.relative_to(stage_dir).as_posix()
                file_checksums[rel_path] = compute_file_sha256(p)

        # Derive dataset_name and section_heading
        dataset_name = spec.dataset.variant
        if spec.type == "movies":
            dataset_name = (
                "MovieLens 1M"
                if spec.dataset.variant == "1m"
                else f"MovieLens {spec.dataset.variant}"
            )
        elif spec.type == "products":
            variant_title = spec.dataset.variant.replace("_", " ").title()
            dataset_name = f"Amazon {variant_title}"
        elif spec.type == "articles":
            dataset_name = (
                spec.dataset.variant if "SYNTHETIC" in spec.dataset.variant.upper() else "MIND"
            )

        model_display = spec.model.name.upper()
        if spec.model.name == "tfidf_profile":
            model_display = "TF-IDF Content Model"
        elif spec.model.name == "sar":
            model_display = "SAR"

        section_heading = f"{spec.display_name} ({dataset_name} + {model_display})"

        # 5. Build and write manifest.json
        manifest_data: dict[str, Any] = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "content_type": spec.type,
            "model_name": spec.model.name,
            "config_hash": compute_config_hash(spec),
            "git_sha": get_git_sha(),
            "dataset_variant": spec.dataset.variant,
            "dataset_name": dataset_name,
            "section_heading": section_heading,
            "created_at": datetime.now(UTC).isoformat(),
            "files": file_checksums,
        }

        manifest_path = stage_dir / "manifest.json"
        write_text_file(manifest_path, json.dumps(manifest_data, indent=2))

        # 6. Atomic swap into place (F-011)
        backup_dir: Path | None = None
        try:
            if artifact_dir.exists():
                backup_dir = artifact_dir.parent / f".bak_{artifact_dir.name}_{stage_id}"
                artifact_dir.rename(backup_dir)
            stage_dir.rename(artifact_dir)
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
        except Exception:
            if backup_dir and backup_dir.exists() and not artifact_dir.exists():
                backup_dir.rename(artifact_dir)
            raise

    except Exception:
        # On failure, clean up staging directory and leave artifact_dir untouched
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    return artifact_dir / "manifest.json"


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

    canonical_artifact_dir = artifact_dir.resolve()
    for rel_path, expected_checksum in files_dict.items():
        # Validate path containment (F-018)
        p = Path(rel_path)
        if p.is_absolute() or ".." in p.parts:
            raise ArtifactCorruptError(
                str(manifest_path),
                f"Path traversal or containment violation: '{rel_path}' is absolute or traverses parent directories.",
            )
        file_path = (artifact_dir / rel_path).resolve()
        if not file_path.is_relative_to(canonical_artifact_dir):
            raise ArtifactCorruptError(
                str(manifest_path),
                f"Path traversal or containment violation: '{rel_path}' resolves outside artifact directory.",
            )

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


def as_str_list(val: Any) -> list[str]:
    """Convert list, tuple, ndarray or scalar into a clean list of strings."""
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val if x is not None and str(x).strip()]
    if hasattr(val, "tolist"):
        return [str(x) for x in val.tolist() if x is not None and str(x).strip()]
    s = str(val).strip()
    return [s] if s else []


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
    if "categories" in items_df.columns:
        items_df["categories"] = items_df["categories"].apply(as_str_list)
    interactions_df = pd.read_parquet(artifact_dir / "interactions.parquet")
    users_df = pd.read_parquet(artifact_dir / "users.parquet")
    if "top_categories" in users_df.columns:
        users_df["top_categories"] = users_df["top_categories"].apply(as_str_list)
    metrics_data = json.loads((artifact_dir / "metrics.json").read_text(encoding="utf-8"))
    demo_users_data = json.loads((artifact_dir / "demo_users.json").read_text(encoding="utf-8"))
    for d in demo_users_data:
        if "top_categories" in d:
            d["top_categories"] = as_str_list(d["top_categories"])

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
