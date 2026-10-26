"""Integration tests for Amazon Products chronological splits and R2 leakage invariance (P4.3)."""

from __future__ import annotations

import pytest

from engine.adapters.amazon import AmazonProductsAdapter
from engine.config import load_config
from engine.errors import LeakageError
from engine.evaluation.checks import check_r1_data_validity, check_r2_no_leakage
from engine.evaluation.harness import EvaluationHarness

pytestmark = [pytest.mark.integration, pytest.mark.real_data]


@pytest.mark.integration
def test_products_instruments_validation_report_and_leakage_passes() -> None:
    """Verify validation report (R1) and chronological split (R2) on real Amazon Instruments data."""
    spec = load_config("products", fast=True)
    adapter = AmazonProductsAdapter(spec)

    try:
        rev_path, meta_path = adapter._find_data_files(adapter.raw_dir)
        if not (rev_path.exists() and meta_path.exists()):
            pytest.skip("Amazon instruments dataset files not found on disk")
    except FileNotFoundError:
        pytest.skip("Amazon instruments dataset not found in data/raw/amazon")

    interactions = adapter.interactions()
    items = adapter.items()

    # 1. R1 Data report validation
    report = adapter.validate()
    assert report.total_interactions == len(interactions)
    assert report.unique_items == len(items)
    assert report.sparsity > 0.95
    assert report.min_timestamp is not None and report.max_timestamp is not None
    assert report.min_timestamp <= report.max_timestamp
    check_r1_data_validity(interactions, items)

    # 2. Chronological split without leakage (R2)
    train_df, valid_df, test_df = adapter.split(interactions)

    check_r2_no_leakage(train_df, test_df)
    check_r2_no_leakage(train_df, valid_df)
    check_r2_no_leakage(valid_df, test_df)

    assert len(train_df) > len(valid_df)
    assert len(train_df) > len(test_df)

    # 3. Split verification via harness
    harness = EvaluationHarness(spec)
    metrics = harness.run(
        interactions=interactions,
        items=items,
        max_test_users=30,
        cold_start_sample_users=10,
    )
    assert metrics["sanity_checks"]["leakage_check_passed"] is True


@pytest.mark.integration
def test_products_deliberate_leakage_detected() -> None:
    """Verify check_r2_no_leakage raises LeakageError when deliberate temporal inversion occurs."""
    spec = load_config("products", fast=True)
    adapter = AmazonProductsAdapter(spec)

    try:
        adapter._find_data_files(adapter.raw_dir)
    except FileNotFoundError:
        pytest.skip("Amazon dataset not found on disk")

    interactions = adapter.interactions()
    train_df, _, test_df = adapter.split(interactions)

    # Find common users between train and test
    common_users = list(set(train_df["user_id"]).intersection(set(test_df["user_id"])))
    if not common_users:
        pytest.skip("No common users in split")

    target_user = common_users[0]
    user_test_max = test_df[test_df["user_id"] == target_user]["timestamp"].max()

    # Corrupt train split by injecting a timestamp strictly after test_max
    leaked_train = train_df.copy()
    mask = leaked_train["user_id"] == target_user
    leaked_train.loc[mask, "timestamp"] = user_test_max + 100_000

    with pytest.raises(LeakageError):
        check_r2_no_leakage(leaked_train, test_df)
