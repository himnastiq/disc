"""Unit tests for reusable invariant checkers (R1 to R5) (P2.9)."""

import pandas as pd
import pytest

from engine.errors import DataValidationError, LeakageError
from engine.evaluation.checks import (
    check_r1_data_validity,
    check_r2_no_leakage,
    check_r3_model_invariants,
    check_r4_evaluation_validity,
    check_r5_cold_start,
)
from engine.schema import Reason, ScoredItem


def test_r1_valid_interactions() -> None:
    interactions = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "timestamp": 100, "signal": 5.0},
            {"user_id": "u1", "item_id": "i2", "timestamp": 200, "signal": 4.0},
            {"user_id": "u2", "item_id": "i2", "timestamp": 300, "signal": 3.0},
        ]
    )
    items = pd.DataFrame([{"item_id": "i1"}, {"item_id": "i2"}])

    report = check_r1_data_validity(interactions, items=items, positive_threshold=4.0)
    assert report.total_interactions == 3
    assert report.unique_users == 2
    assert report.unique_items == 2
    assert report.min_timestamp == 100
    assert report.max_timestamp == 300
    assert report.positive_interactions == 2
    assert 0.0 <= report.sparsity <= 1.0


def test_r1_rejections() -> None:
    # Empty DataFrame
    with pytest.raises(DataValidationError, match="empty"):
        check_r1_data_validity(pd.DataFrame())

    # Nulls
    df_null = pd.DataFrame([{"user_id": None, "item_id": "i1", "timestamp": 100, "signal": 5.0}])
    with pytest.raises(DataValidationError, match="Null values"):
        check_r1_data_validity(df_null)

    # Negative timestamp
    df_neg_ts = pd.DataFrame([{"user_id": "u1", "item_id": "i1", "timestamp": -10, "signal": 5.0}])
    with pytest.raises(DataValidationError, match="Negative timestamp"):
        check_r1_data_validity(df_neg_ts)

    # NaN / Null signal
    df_nan_sig = pd.DataFrame(
        [{"user_id": "u1", "item_id": "i1", "timestamp": 100, "signal": float("nan")}]
    )
    with pytest.raises(DataValidationError, match=r"Null values|NaN"):
        check_r1_data_validity(df_nan_sig)

    # Infinite signal
    df_inf_sig = pd.DataFrame(
        [{"user_id": "u1", "item_id": "i1", "timestamp": 100, "signal": float("inf")}]
    )
    with pytest.raises(DataValidationError, match="infinite"):
        check_r1_data_validity(df_inf_sig)

    # Duplicates
    df_dup = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "timestamp": 100, "signal": 5.0},
            {"user_id": "u1", "item_id": "i1", "timestamp": 100, "signal": 4.0},
        ]
    )
    with pytest.raises(DataValidationError, match="duplicate"):
        check_r1_data_validity(df_dup)

    # Missing from catalogue
    df_ok = pd.DataFrame(
        [{"user_id": "u1", "item_id": "i_missing", "timestamp": 100, "signal": 5.0}]
    )
    cat = pd.DataFrame([{"item_id": "i_other"}])
    with pytest.raises(DataValidationError, match="missing from the catalogue"):
        check_r1_data_validity(df_ok, items=cat)


def test_r2_leakage_check() -> None:
    train = pd.DataFrame([{"user_id": "u1", "item_id": "i1", "timestamp": 100}])
    test = pd.DataFrame([{"user_id": "u1", "item_id": "i2", "timestamp": 200}])

    # Clean
    check_r2_no_leakage(train, test, strategy="chronological")

    # Leaked
    leaked_test = pd.DataFrame([{"user_id": "u1", "item_id": "i2", "timestamp": 50}])
    with pytest.raises(LeakageError):
        check_r2_no_leakage(train, leaked_test, strategy="chronological")


def test_r3_model_invariants_checks() -> None:
    catalogue = {"i1", "i2", "i3", "i4"}
    recs = [
        ScoredItem(item_id="i1", score=10.0, rank=1),
        ScoredItem(item_id="i2", score=8.0, rank=2),
    ]

    # Valid check
    check_r3_model_invariants(recs, k=5, catalogue=catalogue)

    # Duplicate item
    dup_recs = [
        ScoredItem(item_id="i1", score=10.0, rank=1),
        ScoredItem(item_id="i1", score=8.0, rank=2),
    ]
    with pytest.raises(AssertionError, match="Duplicate item"):
        check_r3_model_invariants(dup_recs, k=5)

    # Excluded item
    with pytest.raises(AssertionError, match="Excluded item"):
        check_r3_model_invariants(recs, k=5, exclude_ids={"i1"})

    # Query item in similar items
    with pytest.raises(AssertionError, match="Query item"):
        check_r3_model_invariants(recs, k=5, query_item_id="i1")

    # Unsorted scores
    unsorted = [
        ScoredItem(item_id="i1", score=5.0, rank=1),
        ScoredItem(item_id="i2", score=10.0, rank=2),
    ]
    with pytest.raises(AssertionError, match="Scores not sorted"):
        check_r3_model_invariants(unsorted, k=5)

    # Item not in catalogue
    with pytest.raises(AssertionError, match="not in catalogue"):
        check_r3_model_invariants(recs, k=5, catalogue={"i1"})

    # Faithful reason check
    valid_reason = Reason(item_id="h1", kind="co_occurrence", text="Interacted with h1")
    check_r3_model_invariants(recs, k=5, reason=valid_reason, history_items={"h1", "h2"})

    unfaithful_reason = Reason(item_id="h_not_in_hist", kind="co_occurrence", text="Foo")
    with pytest.raises(AssertionError, match="Unfaithful explanation"):
        check_r3_model_invariants(recs, k=5, reason=unfaithful_reason, history_items={"h1"})


def test_r4_evaluation_validity_check() -> None:
    models_metrics = {
        "popularity": {
            "10": {
                "ndcg": 0.15,
                "precision": 0.1,
                "hit_rate": 0.5,
                "novelty": 5.2,
                "coverage": 0.2,
                "diversity": 0.7,
                "personalisation": 0.0,
            }
        },
        "random": {
            "10": {
                "ndcg": 0.02,
                "precision": 0.01,
                "hit_rate": 0.05,
                "novelty": 10.0,
                "coverage": 0.9,
                "diversity": 0.8,
                "personalisation": 0.95,
            }
        },
    }

    res = check_r4_evaluation_validity(models_metrics, ref_k=10)
    assert res["all_bounds_valid"] is True
    assert res["popularity_beats_random"] is True

    # Bad bounds (negative coverage)
    bad_metrics = {
        "popularity": {
            "10": {
                "coverage": -0.5,
                "ndcg": 0.1,
            }
        }
    }
    res_bad = check_r4_evaluation_validity(bad_metrics, ref_k=10)
    assert res_bad["all_bounds_valid"] is False


def test_r5_cold_start_check() -> None:
    monotonic_curve = {
        "0": {"ndcg@10": 0.05},
        "1": {"ndcg@10": 0.08},
        "5": {"ndcg@10": 0.12},
        "10": {"ndcg@10": 0.15},
    }
    m_res = check_r5_cold_start(monotonic_curve, metric_name="ndcg@10")
    assert m_res["is_monotonic"] is True
    assert len(m_res["non_monotonic_transitions"]) == 0

    non_monotonic_curve = {
        "0": {"ndcg@10": 0.05},
        "1": {"ndcg@10": 0.08},
        "5": {"ndcg@10": 0.06},  # Drop!
        "10": {"ndcg@10": 0.12},
    }
    nm_res = check_r5_cold_start(non_monotonic_curve, metric_name="ndcg@10")
    assert nm_res["is_monotonic"] is False
    assert (1, 5) in nm_res["non_monotonic_transitions"]
