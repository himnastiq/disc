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


def test_train_pipeline_aligns_interactions_with_split_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_pipeline filters interactions to all_split_items when an adapter prunes items during split."""
    import pandas as pd

    from engine.adapters.toy import ToyAdapter
    from engine.registry import _ADAPTER_REGISTRY

    class PruningToyAdapter(ToyAdapter):
        def split(
            self,
            interactions: pd.DataFrame | None = None,
        ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            train_df, valid_df, test_df = super().split(interactions)
            # Prune out item 'toy_item_0' from all splits to simulate popularity cap pruning
            train_df = train_df[train_df["item_id"] != "toy_item_0"].reset_index(drop=True)
            valid_df = valid_df[valid_df["item_id"] != "toy_item_0"].reset_index(drop=True)
            test_df = test_df[test_df["item_id"] != "toy_item_0"].reset_index(drop=True)
            return train_df, valid_df, test_df

    monkeypatch.setitem(_ADAPTER_REGISTRY, "toy", PruningToyAdapter)

    artifacts_dir = tmp_path / "pruned_toy_artifacts"
    metrics = run_pipeline(
        content_type="toy",
        fast=True,
        seed=42,
        artifacts_dir=artifacts_dir,
    )
    assert metrics is not None

    saved_inter = pd.read_parquet(artifacts_dir / "interactions.parquet")
    saved_items = pd.read_parquet(artifacts_dir / "items.parquet")
    assert "toy_item_0" not in set(saved_inter["item_id"])
    assert set(saved_inter["item_id"]).issubset(set(saved_items["item_id"]))
