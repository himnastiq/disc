"""Tests for the train CLI and logging utilities (P2.12)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from engine.artifacts import verify_artifacts
from engine.logging_utils import configure_logging, get_logger, log_event
from engine.train import run_pipeline

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_logging_utils(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify configure_logging and log_event work with structured format."""
    configure_logging(level=logging.INFO)
    logger = get_logger("test_module")

    log_event(logger, "test_event", key1="val1", key2=42)

    captured = capsys.readouterr().out
    assert "test_event" in captured
    assert "key1=val1" in captured
    assert "key2=42" in captured


def test_train_pipeline_toy(tmp_path: Path) -> None:
    """Verify run_pipeline executes end to end on synthetic toy adapter."""
    artifacts_dir = tmp_path / "toy_artifacts"
    metrics = run_pipeline(
        content_type="toy",
        fast=True,
        seed=123,
        artifacts_dir=artifacts_dir,
    )

    # Check metrics output
    assert "models" in metrics
    assert "popularity" in metrics["models"]
    assert "protocol" in metrics
    assert "sanity_checks" in metrics

    # Verify saved artifacts with cryptographic manifest
    manifest = verify_artifacts(artifacts_dir)
    assert manifest["artifact_schema_version"] == "1.0.0"
    assert "files" in manifest
    assert (artifacts_dir / "manifest.json").exists()
    assert (artifacts_dir / "items.parquet").exists()
    assert (artifacts_dir / "interactions.parquet").exists()
    assert (artifacts_dir / "users.parquet").exists()
    assert (artifacts_dir / "topn.parquet").exists()
    assert (artifacts_dir / "metrics.json").exists()
