"""Integration tests for MovieLens chronological splits and R2 leakage invariance (P3.4)."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.adapters.movielens import MovieLensAdapter
from engine.config import load_config
from engine.errors import LeakageError
from engine.evaluation.checks import check_r2_no_leakage
from engine.evaluation.harness import EvaluationHarness

pytestmark = [pytest.mark.integration, pytest.mark.real_data]


def test_movies_100k_chronological_split_leakage_passes() -> None:
    """Verify chronological per-user split on real MovieLens 100K data satisfies R2 no-leakage."""
    spec = load_config("movies", fast=True)
    adapter = MovieLensAdapter(spec)

    if (
        not (adapter.raw_dir / "ml-100k").exists()
        and not (adapter.raw_dir / "ml-100k.zip").exists()
    ):
        pytest.skip("MovieLens 100K dataset not found in data/raw/movielens")

    interactions = adapter.interactions()
    items = adapter.items()

    # 1. Split via adapter
    train_df, valid_df, test_df = adapter.split(interactions)

    # Assert no temporal leakage across splits
    check_r2_no_leakage(train_df, test_df)
    check_r2_no_leakage(train_df, valid_df)
    check_r2_no_leakage(valid_df, test_df)

    assert len(train_df) > len(valid_df)
    assert len(train_df) > len(test_df)

    # 2. Split via EvaluationHarness run
    harness = EvaluationHarness(spec)
    metrics = harness.run(
        interactions=interactions,
        items=items,
        max_test_users=30,
        cold_start_sample_users=10,
    )
    assert metrics["sanity_checks"]["leakage_check_passed"] is True


def test_movies_1m_chronological_split_leakage_passes() -> None:
    """Verify chronological per-user split on real MovieLens 1M data satisfies R2 no-leakage."""
    spec = load_config("movies", fast=False)
    adapter = MovieLensAdapter(spec)

    if not (adapter.raw_dir / "ml-1m").exists() and not (adapter.raw_dir / "ml-1m.zip").exists():
        pytest.skip("MovieLens 1M dataset not found in data/raw/movielens")

    interactions = adapter.interactions()
    train_df, valid_df, test_df = adapter.split(interactions)

    # Assert no temporal leakage across splits
    check_r2_no_leakage(train_df, test_df)
    check_r2_no_leakage(train_df, valid_df)
    check_r2_no_leakage(valid_df, test_df)


def test_movies_split_leakage_detection_on_deliberate_contamination() -> None:
    """Verify check_r2_no_leakage fails when a future interaction is artificially injected into train."""
    spec = load_config("movies", fast=True)
    adapter = MovieLensAdapter(spec)

    if (
        not (adapter.raw_dir / "ml-100k").exists()
        and not (adapter.raw_dir / "ml-100k.zip").exists()
    ):
        pytest.skip("MovieLens 100K dataset not found in data/raw/movielens")

    interactions = adapter.interactions()
    train_df, _, test_df = adapter.split(interactions)

    # Pick a user present in both train and test
    common_users = set(train_df["user_id"]).intersection(set(test_df["user_id"]))
    target_user = next(iter(common_users))

    test_user_row = test_df[test_df["user_id"] == target_user].iloc[0]
    future_timestamp = int(test_user_row["timestamp"]) + 1000

    # Inject future interaction into training set
    contaminated_row = pd.DataFrame(
        [
            {
                "user_id": target_user,
                "item_id": "99999",
                "signal": 5.0,
                "timestamp": future_timestamp,
                "positive": True,
            }
        ]
    )
    contaminated_train = pd.concat([train_df, contaminated_row], ignore_index=True)

    with pytest.raises(LeakageError, match=r"Leakage detected"):
        check_r2_no_leakage(contaminated_train, test_df)
