"""Integration tests for MIND Articles impression-time split and R2 leakage invariance (P5.3)."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.adapters.mind import MindArticlesAdapter
from engine.config import load_config
from engine.errors import LeakageError
from engine.evaluation.checks import check_r1_data_validity, check_r2_no_leakage

pytestmark = [pytest.mark.integration, pytest.mark.real_data]


def test_articles_mind_validation_report_and_leakage_passes() -> None:
    """Verify validation report (R1) and impression time split (R2) on MIND data."""
    spec = load_config("articles", fast=True)
    adapter = MindArticlesAdapter(spec)

    interactions = adapter.interactions()
    items = adapter.items()

    assert not interactions.empty
    assert not items.empty

    # 1. R1 Data report validation
    report = adapter.validate()
    assert report.total_interactions == len(interactions)
    assert report.unique_items == len(items)
    assert report.min_timestamp is not None and report.max_timestamp is not None
    assert report.min_timestamp <= report.max_timestamp
    assert "min_date" in report.details
    assert "max_date" in report.details
    assert report.details["min_date"] != ""
    assert report.details["max_date"] != ""
    check_r1_data_validity(interactions, items)

    # 2. Impression time split without leakage (R2)
    train_df, valid_df, test_df = adapter.split(interactions)

    assert not train_df.empty
    assert not test_df.empty

    check_r2_no_leakage(train_df, test_df)
    if not valid_df.empty:
        check_r2_no_leakage(train_df, valid_df)
        check_r2_no_leakage(valid_df, test_df)

    # 3. Explicit protocol check: No test impression clicked item used as training positive for that user
    common_users = set(train_df["user_id"]).intersection(set(test_df["user_id"]))
    for uid in common_users:
        u_train_items = set(train_df[train_df["user_id"] == uid]["item_id"])
        u_test_items = set(test_df[test_df["user_id"] == uid]["item_id"])
        assert u_train_items.isdisjoint(u_test_items), (
            f"Leakage detected: User {uid} has test clicked items appearing in training: "
            f"{u_train_items.intersection(u_test_items)}"
        )


@pytest.mark.integration
def test_articles_deliberate_leakage_detected() -> None:
    """Verify check_r2_no_leakage raises LeakageError when temporal boundary is violated."""
    spec = load_config("articles", fast=True)
    adapter = MindArticlesAdapter(spec)

    interactions = adapter.interactions()
    train_df, _, test_df = adapter.split(interactions)

    common_users = list(set(train_df["user_id"]).intersection(set(test_df["user_id"])))
    if not common_users:
        # If no common user, inject a common user with conflicting timestamp
        target_user = "U_LEAK"
        max_test_ts = int(test_df["timestamp"].max())
        corrupt_train = train_df.copy()
        corrupt_train = pd.concat(
            [
                corrupt_train,
                pd.DataFrame(
                    [
                        {
                            "user_id": target_user,
                            "item_id": "N1",
                            "signal": 1.0,
                            "timestamp": max_test_ts + 1000,
                            "positive": True,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        corrupt_test = test_df.copy()
        corrupt_test = pd.concat(
            [
                corrupt_test,
                pd.DataFrame(
                    [
                        {
                            "user_id": target_user,
                            "item_id": "N2",
                            "signal": 1.0,
                            "timestamp": max_test_ts,
                            "positive": True,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        with pytest.raises(LeakageError):
            check_r2_no_leakage(corrupt_train, corrupt_test)
        return

    target_user = common_users[0]
    user_test_max = test_df[test_df["user_id"] == target_user]["timestamp"].max()

    # Invert timestamps: make train interaction strictly after test
    leaked_train = train_df.copy()
    mask = leaked_train["user_id"] == target_user
    leaked_train.loc[mask, "timestamp"] = user_test_max + 100_000

    with pytest.raises(LeakageError):
        check_r2_no_leakage(leaked_train, test_df)
