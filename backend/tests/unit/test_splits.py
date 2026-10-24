"""Tests for dataset splitters and R2 leakage verification (P2.6)."""

import pandas as pd
import pytest

from engine.errors import LeakageError
from engine.evaluation.splits import (
    check_leakage,
    split_interactions,
)


@pytest.fixture
def sample_interactions() -> pd.DataFrame:
    rows = []
    # 5 users, each with 10 interactions at strictly increasing timestamps
    for u in range(1, 6):
        user_id = f"user_{u}"
        for i in range(1, 11):
            rows.append(
                {
                    "user_id": user_id,
                    "item_id": f"item_{u}_{i}",
                    "signal": 4.0,
                    "timestamp": u * 1000 + i * 10,
                    "positive": True,
                }
            )
    return pd.DataFrame(rows)


def test_chronological_split_success_and_no_leakage(
    sample_interactions: pd.DataFrame,
) -> None:
    train, valid, test = split_interactions(
        sample_interactions, strategy="chronological", ratios=(0.7, 0.15, 0.15)
    )

    assert not train.empty
    assert not valid.empty
    assert not test.empty
    assert len(train) + len(valid) + len(test) == len(sample_interactions)

    # R2 Invariant: No leakage per user
    check_leakage(train, test, valid_df=valid, strategy="chronological")


def test_leave_last_n_split_success_and_no_leakage(
    sample_interactions: pd.DataFrame,
) -> None:
    train, valid, test = split_interactions(
        sample_interactions, strategy="leave_last_n", n_test=2, n_valid=2
    )

    # For each user with 10 interactions: 6 train, 2 valid, 2 test
    for _, group in test.groupby("user_id"):
        assert len(group) == 2
    for _, group in valid.groupby("user_id"):
        assert len(group) == 2
    for _, group in train.groupby("user_id"):
        assert len(group) == 6

    # R2 Invariant: No leakage per user
    check_leakage(train, test, valid_df=valid, strategy="leave_last_n")


def test_impression_time_split_success_and_no_leakage(
    sample_interactions: pd.DataFrame,
) -> None:
    train, valid, test = split_interactions(
        sample_interactions, strategy="impression_time", ratios=(0.6, 0.2, 0.2)
    )

    assert not train.empty
    assert not valid.empty
    assert not test.empty
    assert len(train) + len(valid) + len(test) == len(sample_interactions)

    # R2 Invariant: Global chronological ordering
    check_leakage(train, test, valid_df=valid, strategy="impression_time")


def test_deliberate_leakage_detected_chronological() -> None:
    # Train has future timestamp for user_1
    train = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_1", "timestamp": 500},
            {"user_id": "user_1", "item_id": "item_2", "timestamp": 1200},  # LEAK!
        ]
    )
    test = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_3", "timestamp": 1000},
        ]
    )

    with pytest.raises(LeakageError) as exc_info:
        check_leakage(train, test, strategy="chronological")

    assert "user_1" in exc_info.value.leaked_users


def test_deliberate_leakage_detected_valid_split() -> None:
    # Valid timestamp is before train timestamp
    train = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_1", "timestamp": 800},
        ]
    )
    valid = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_2", "timestamp": 700},  # LEAK!
        ]
    )
    test = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_3", "timestamp": 1000},
        ]
    )

    with pytest.raises(LeakageError) as exc_info:
        check_leakage(train, test, valid_df=valid, strategy="chronological")

    assert "user_1" in exc_info.value.leaked_users


def test_deliberate_leakage_detected_impression_time() -> None:
    train = pd.DataFrame(
        [
            {"user_id": "user_1", "item_id": "item_1", "timestamp": 1500},
        ]
    )
    test = pd.DataFrame(
        [
            {"user_id": "user_2", "item_id": "item_2", "timestamp": 1200},
        ]
    )

    with pytest.raises(LeakageError, match="global train max timestamp"):
        check_leakage(train, test, strategy="impression_time")


def test_invalid_strategy_raises_error(sample_interactions: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="Unknown split strategy"):
        split_interactions(sample_interactions, strategy="non_existent_strategy")
