"""Unit tests for evaluation metrics with hand-computed verification (P2.7 / R4)."""

from typing import Any

import pandas as pd
import pytest

from engine.evaluation.metrics import (
    bootstrap_ci,
    compute_headline_metrics_with_ci,
    coverage,
    hit_rate,
    intra_list_diversity,
    mean_average_precision,
    ndcg,
    novelty,
    personalisation_score,
    precision,
    recall,
)


@pytest.fixture
def tiny_fixture() -> dict[str, Any]:
    catalog_items = ["i1", "i2", "i3", "i4", "i5"]
    item_categories = {
        "i1": ["Action"],
        "i2": ["Action", "Comedy"],
        "i3": ["Comedy"],
        "i4": ["Drama"],
        "i5": ["Horror"],
    }

    # 4 train interactions: i1:1, i2:2, i4:1 (total N=4)
    train_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "rating": 1.0},
            {"user_id": "u1", "item_id": "i2", "rating": 1.0},
            {"user_id": "u2", "item_id": "i2", "rating": 1.0},
            {"user_id": "u2", "item_id": "i4", "rating": 1.0},
        ]
    )

    # Test ground truth: u1 has {i3}, u2 has {i1, i5}
    true_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i3", "rating": 1.0},
            {"user_id": "u2", "item_id": "i1", "rating": 1.0},
            {"user_id": "u2", "item_id": "i5", "rating": 1.0},
        ]
    )

    # Predictions:
    # u1: i3 (0.9), i2 (0.8) -> hit on i3
    # u2: i2 (0.95), i4 (0.7) -> 0 hits
    pred_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i3", "score": 0.9},
            {"user_id": "u1", "item_id": "i2", "score": 0.8},
            {"user_id": "u2", "item_id": "i2", "score": 0.95},
            {"user_id": "u2", "item_id": "i4", "score": 0.7},
        ]
    )

    return {
        "catalog_items": catalog_items,
        "item_categories": item_categories,
        "train_df": train_df,
        "true_df": true_df,
        "pred_df": pred_df,
    }


def test_hit_rate_against_hand_computed_value(tiny_fixture: dict[str, Any]) -> None:
    hr = hit_rate(tiny_fixture["true_df"], tiny_fixture["pred_df"], k=2)
    # Hand-computed: u1 hit (1), u2 miss (0) -> 1/2 = 0.5
    assert hr == pytest.approx(0.5, abs=1e-5)


def test_coverage_against_hand_computed_value(tiny_fixture: dict[str, Any]) -> None:
    cov = coverage(tiny_fixture["pred_df"], tiny_fixture["catalog_items"], k=2)
    # Hand-computed: rec items {i2, i3, i4} (3 items) out of 5 catalog items -> 3/5 = 0.6
    assert cov == pytest.approx(0.6, abs=1e-5)


def test_novelty_against_hand_computed_value(tiny_fixture: dict[str, Any]) -> None:
    nov = novelty(tiny_fixture["pred_df"], tiny_fixture["train_df"], k=2)
    # Hand-computed:
    # i3: -log2(1/4) = 2.0
    # i2: -log2(2/4) = 1.0
    # i2: -log2(2/4) = 1.0
    # i4: -log2(1/4) = 2.0
    # Mean: (2 + 1 + 1 + 2) / 4 = 1.5
    assert nov == pytest.approx(1.5, abs=1e-5)


def test_intra_list_diversity_against_hand_computed_value(
    tiny_fixture: dict[str, Any],
) -> None:
    div = intra_list_diversity(tiny_fixture["pred_df"], tiny_fixture["item_categories"], k=2)
    # Hand-computed:
    # u1: i3 ("Comedy") & i2 ("Action", "Comedy") -> Jaccard=1/2=0.5 -> dist=0.5
    # u2: i2 ("Action", "Comedy") & i4 ("Drama") -> Jaccard=0/3=0.0 -> dist=1.0
    # Mean: (0.5 + 1.0) / 2 = 0.75
    assert div == pytest.approx(0.75, abs=1e-5)


def test_personalisation_against_hand_computed_value(
    tiny_fixture: dict[str, Any],
) -> None:
    pers = personalisation_score(tiny_fixture["pred_df"], k=2)
    # Hand-computed:
    # u1 top-2: {i2, i3}
    # u2 top-2: {i2, i4}
    # Intersection = {i2} (1), Union = {i2, i3, i4} (3)
    # Jaccard = 1/3, Distance = 1.0 - 1/3 = 2/3
    assert pers == pytest.approx(2.0 / 3.0, abs=1e-5)


def test_ranking_metrics_against_hand_computed_values(
    tiny_fixture: dict[str, Any],
) -> None:
    p = precision(tiny_fixture["true_df"], tiny_fixture["pred_df"], k=2)
    # u1: 1 hit / 2 = 0.5. u2: 0 hits / 2 = 0.0 -> Mean = 0.25
    assert p == pytest.approx(0.25, abs=1e-5)

    r = recall(tiny_fixture["true_df"], tiny_fixture["pred_df"], k=2)
    # u1: 1 hit / 1 actual = 1.0. u2: 0 hits / 2 actual = 0.0 -> Mean = 0.5
    assert r == pytest.approx(0.5, abs=1e-5)

    n = ndcg(tiny_fixture["true_df"], tiny_fixture["pred_df"], k=2)
    assert n > 0.0

    m = mean_average_precision(tiny_fixture["true_df"], tiny_fixture["pred_df"], k=2)
    assert m > 0.0


def test_empty_dataframe_metrics_graceful() -> None:
    empty_df = pd.DataFrame(columns=["user_id", "item_id", "score"])
    assert precision(empty_df, empty_df, k=5) == 0.0
    assert recall(empty_df, empty_df, k=5) == 0.0
    assert hit_rate(empty_df, empty_df, k=5) == 0.0
    assert coverage(empty_df, ["i1", "i2"], k=5) == 0.0
    assert novelty(empty_df, empty_df, k=5) == 0.0
    assert intra_list_diversity(empty_df, {}, k=5) == 0.0
    assert personalisation_score(empty_df, k=5) == 0.0


def test_ndcg_unfiltered_true_users_invariant() -> None:
    """Verify NDCG@K is invariant to presence of non-evaluated users in true_df (FIX-16)."""
    # 5 evaluated users with predictions (including rank column)
    pred_rows = []
    for u in range(1, 6):
        uid = f"u{u}"
        for rank, i in enumerate(range(1, 11), start=1):
            pred_rows.append(
                {"user_id": uid, "item_id": f"i{i}", "score": 10.0 - rank, "rank": rank}
            )
    preds_df = pd.DataFrame(pred_rows)

    # Ground truth for evaluated users: u1 has hit on i1 (rank 1), u2 has hit on i2 (rank 2), others have no hits
    matched_true = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "signal": 5.0},
            {"user_id": "u2", "item_id": "i2", "signal": 4.0},
            {"user_id": "u3", "item_id": "i99", "signal": 5.0},
            {"user_id": "u4", "item_id": "i98", "signal": 5.0},
            {"user_id": "u5", "item_id": "i97", "signal": 5.0},
        ]
    )

    # True with 500 extra users who were never evaluated in preds_df
    extra_true = pd.DataFrame(
        [
            {"user_id": f"extra_u{i}", "item_id": f"extra_item_{i}", "signal": 5.0}
            for i in range(500)
        ]
    )
    full_true = pd.concat([matched_true, extra_true], ignore_index=True)

    ndcg_matched = ndcg(matched_true, preds_df, k=10)
    ndcg_full = ndcg(full_true, preds_df, k=10)

    # Invariant: extra non-evaluated users must not dilute NDCG
    assert ndcg_matched > 0.0
    assert ndcg_full == pytest.approx(ndcg_matched, abs=1e-6)


def test_ndcg_matches_plain_numpy_independent_formula() -> None:
    """Verify NDCG matches plain numpy calculation using standard DCG/IDCG formula (FIX-16)."""
    import math

    # u1: hit at rank 1 (i1) out of 2 relevant -> DCG = 1/log2(2) = 1.0; IDCG = 1/log2(2) + 1/log2(3) = 1.63092975
    # u2: hit at rank 3 (i3) out of 1 relevant -> DCG = 1/log2(4) = 0.5; IDCG = 1/log2(2) = 1.0
    preds_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "score": 3.0, "rank": 1},
            {"user_id": "u1", "item_id": "i2", "score": 2.0, "rank": 2},
            {"user_id": "u1", "item_id": "i9", "score": 1.0, "rank": 3},
            {"user_id": "u2", "item_id": "i8", "score": 3.0, "rank": 1},
            {"user_id": "u2", "item_id": "i7", "score": 2.0, "rank": 2},
            {"user_id": "u2", "item_id": "i3", "score": 1.0, "rank": 3},
        ]
    )
    true_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "signal": 5.0},
            {"user_id": "u1", "item_id": "i5", "signal": 4.0},
            {"user_id": "u2", "item_id": "i3", "signal": 5.0},
        ]
    )

    expected_u1 = (1.0 / math.log2(2)) / (1.0 / math.log2(2) + 1.0 / math.log2(3))
    expected_u2 = (1.0 / math.log2(4)) / (1.0 / math.log2(2))
    expected_mean = (expected_u1 + expected_u2) / 2.0

    calculated = ndcg(true_df, preds_df, k=10)
    assert calculated == pytest.approx(expected_mean, rel=1e-4)


def test_bootstrap_ci_properties() -> None:
    """Verify bootstrap CI bounds, coverage, and deterministic properties (FIX-17)."""
    import numpy as np

    # Empty array
    assert bootstrap_ci([]) == (0.0, 0.0)

    # Constant array
    assert bootstrap_ci([0.42, 0.42, 0.42]) == (0.42, 0.42)

    # Known distribution
    rng = np.random.default_rng(123)
    data = rng.normal(loc=10.0, scale=2.0, size=500)
    lo, hi = bootstrap_ci(data, n_bootstraps=500, ci=0.95, seed=42)
    sample_mean = float(np.mean(data))

    assert lo <= sample_mean <= hi
    assert 9.7 <= lo <= 10.0
    assert 10.0 <= hi <= 10.3

    # Determinism with seed
    lo2, hi2 = bootstrap_ci(data, n_bootstraps=500, ci=0.95, seed=42)
    assert lo == lo2 and hi == hi2


def test_compute_headline_metrics_with_ci_contract() -> None:
    """Verify compute_headline_metrics_with_ci returns all metrics and CIs (FIX-17)."""
    # 3 users: u1 perfect hits, u2 partial hit, u3 no hit
    true_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "signal": 5.0},
            {"user_id": "u1", "item_id": "i2", "signal": 5.0},
            {"user_id": "u2", "item_id": "i3", "signal": 4.0},
            {"user_id": "u3", "item_id": "i9", "signal": 4.0},
        ]
    )
    pred_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "i1", "score": 2.0},
            {"user_id": "u1", "item_id": "i2", "score": 1.0},
            {"user_id": "u2", "item_id": "i3", "score": 2.0},
            {"user_id": "u2", "item_id": "i8", "score": 1.0},
            {"user_id": "u3", "item_id": "i4", "score": 2.0},
            {"user_id": "u3", "item_id": "i5", "score": 1.0},
        ]
    )

    result = compute_headline_metrics_with_ci(true_df, pred_df, k=2, n_bootstraps=300)
    assert result["evaluated_users"] == 3

    for m in ["precision", "recall", "ndcg", "map", "hit_rate"]:
        assert m in result
        assert f"{m}_ci95" in result
        val = result[m]
        lo, hi = result[f"{m}_ci95"]
        assert 0.0 <= lo <= val + 1e-4
        assert val - 1e-4 <= hi <= 1.0
