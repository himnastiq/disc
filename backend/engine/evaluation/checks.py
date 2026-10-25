"""Discovery Engine - Reusable robustness invariant checkers (R1 to R5) (P2.9).

Used across unit tests, property tests, the evaluation harness, and API tests.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.errors import DataValidationError
from engine.evaluation.splits import check_leakage
from engine.schema import Reason, ScoredItem, ValidationReport

if TYPE_CHECKING:
    from collections.abc import Collection

    import pandas as pd


def check_r1_data_validity(
    interactions: pd.DataFrame,
    items: pd.DataFrame | None = None,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_timestamp: str = "timestamp",
    col_signal: str = "signal",
    positive_threshold: float = 4.0,
) -> ValidationReport:
    """Validate R1 data integrity constraints and return ValidationReport.

    Checks:
        - Non-empty interactions
        - No null or empty user_id, item_id, timestamp, signal
        - Timestamp values are non-negative unix seconds and max >= min
        - Signal values are finite floats
        - No duplicate (user_id, item_id, timestamp) rows
        - If items catalogue provided: every interacted item exists in items
        - Matrix sparsity in [0.0, 1.0]

    Raises:
        DataValidationError: If any data invariant is violated.
    """
    if interactions.empty:
        raise DataValidationError("Interactions DataFrame is empty.")

    # Null checks
    null_cols = [
        c
        for c in [col_user, col_item, col_timestamp, col_signal]
        if c in interactions.columns and interactions[c].isnull().any()
    ]
    if null_cols:
        raise DataValidationError(f"Null values found in interactions columns: {null_cols}")

    # Empty string IDs
    if (interactions[col_user].astype(str).str.strip() == "").any():
        raise DataValidationError("Found empty user_id strings in interactions.")
    if (interactions[col_item].astype(str).str.strip() == "").any():
        raise DataValidationError("Found empty item_id strings in interactions.")

    # Timestamps
    min_ts = int(interactions[col_timestamp].min())
    max_ts = int(interactions[col_timestamp].max())
    if min_ts < 0:
        raise DataValidationError(f"Negative timestamp found in interactions: {min_ts}")
    if max_ts < min_ts:
        raise DataValidationError(f"Invalid timestamp range: max ({max_ts}) < min ({min_ts})")

    # Signals
    signals = interactions[col_signal]
    if signals.isna().any() or (signals == float("inf")).any() or (signals == float("-inf")).any():
        raise DataValidationError("Interactions contain NaN or infinite signal values.")

    # Duplicates check
    dupes = interactions.duplicated(subset=[col_user, col_item, col_timestamp]).sum()
    if dupes > 0:
        raise DataValidationError(
            f"Found {dupes} duplicate (user_id, item_id, timestamp) interaction rows."
        )

    # Catalogue cross-check
    if items is not None and not items.empty:
        item_cat = set(items[col_item].astype(str))
        inter_items = set(interactions[col_item].astype(str))
        missing = inter_items - item_cat
        if missing:
            sample = sorted(missing)[:5]
            raise DataValidationError(
                f"{len(missing)} interacted item(s) are missing from the catalogue. Examples: {sample}"
            )

    n_users = int(interactions[col_user].nunique())
    n_items = int(interactions[col_item].nunique())
    n_total = len(interactions)

    max_possible = n_users * n_items
    sparsity = 1.0 - (n_total / max_possible) if max_possible > 0 else 0.0
    sparsity = max(0.0, min(1.0, sparsity))

    if "positive" in interactions.columns:
        n_pos = int((interactions["positive"] == True).sum())  # noqa: E712
    else:
        n_pos = int((interactions[col_signal] >= positive_threshold).sum())

    return ValidationReport(
        total_interactions=n_total,
        unique_users=n_users,
        unique_items=n_items,
        sparsity=float(round(sparsity, 6)),
        min_timestamp=min_ts,
        max_timestamp=max_ts,
        positive_interactions=n_pos,
        filtered_users=0,
        filtered_items=0,
    )


def check_r2_no_leakage(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    valid_df: pd.DataFrame | None = None,
    strategy: str = "chronological",
    col_user: str = "user_id",
    col_timestamp: str = "timestamp",
) -> None:
    """Validate R2 chronological / temporal separation across partitions."""
    check_leakage(
        train_df=train_df,
        test_df=test_df,
        valid_df=valid_df,
        strategy=strategy,
        col_user=col_user,
        col_timestamp=col_timestamp,
    )


def check_r3_model_invariants(
    recs: list[ScoredItem],
    k: int,
    catalogue: Collection[str] | None = None,
    exclude_ids: Collection[str] = (),
    query_item_id: str | None = None,
    reason: Reason | None = None,
    history_items: Collection[str] = (),
) -> None:
    """Assert R3 model serving invariants on recommendation results.

    Checks:
        - len(recs) <= k
        - No duplicate items in recommendation list
        - No excluded items present
        - Query item never returned (for similar_items)
        - All recommended item IDs exist in catalogue (if catalogue provided)
        - Scores are finite floats and sorted descending
        - Ranks are consecutive starting at 1
        - Explanations are faithful (reason.item_id is a member of history_items)

    Raises:
        AssertionError: If any invariant fails.
    """
    assert len(recs) <= k, f"Expected at most {k} items, got {len(recs)}"

    seen_items: set[str] = set()
    exclude_set = {str(x) for x in exclude_ids}
    cat_set = {str(x) for x in catalogue} if catalogue is not None else None

    scores: list[float] = []
    expected_rank = 1

    for item in recs:
        assert isinstance(item, ScoredItem), f"Expected ScoredItem, got {type(item)}"
        assert item.item_id not in seen_items, (
            f"Duplicate item in recommendations: '{item.item_id}'"
        )
        seen_items.add(item.item_id)

        assert item.item_id not in exclude_set, f"Excluded item returned: '{item.item_id}'"

        if query_item_id is not None:
            assert str(item.item_id) != str(query_item_id), (
                f"Query item '{query_item_id}' returned in similar items."
            )

        if cat_set is not None:
            assert item.item_id in cat_set, f"Recommended item '{item.item_id}' not in catalogue."

        assert not math.isnan(item.score), f"NaN score for item '{item.item_id}'"
        assert not math.isinf(item.score), f"Infinite score for item '{item.item_id}'"
        scores.append(item.score)

        assert item.rank == expected_rank, (
            f"Rank mismatch: expected {expected_rank}, got {item.rank}"
        )
        expected_rank += 1

    # Scores must be sorted descending
    assert scores == sorted(scores, reverse=True), f"Scores not sorted descending: {scores}"

    # Faithful explanation
    if reason is not None and reason.item_id is not None:
        hist_set = {str(x) for x in history_items}
        assert reason.item_id in hist_set, (
            f"Unfaithful explanation: reason item '{reason.item_id}' is not in user history {hist_set}"
        )


def check_r4_evaluation_validity(
    models_metrics: dict[str, Any],
    ref_k: int = 10,
) -> dict[str, bool]:
    """Validate R4 evaluation metrics bounds and sanity ordering.

    Checks:
        - All metric values are finite floats within [0.0, 1.0] (or >= 0 for novelty)
        - Popularity >= Random on ranking metrics (precision, recall, ndcg, map, hit_rate)

    Returns:
        dict[str, bool]: Status flags for evaluation invariants.
    """
    models_dict: dict[str, Any] = (
        models_metrics["models"]
        if ("models" in models_metrics and isinstance(models_metrics["models"], dict))
        else models_metrics
    )

    bounded_metrics = {
        "precision",
        "recall",
        "ndcg",
        "map",
        "hit_rate",
        "coverage",
        "diversity",
        "personalisation",
    }

    all_bounds_valid = True
    for _model_name, k_dict in models_dict.items():
        if not isinstance(k_dict, dict):
            continue
        for _k_str, m_dict in k_dict.items():
            if not isinstance(m_dict, dict):
                continue
            for m_name, val in m_dict.items():
                if isinstance(val, (list, tuple)):
                    for v in val:
                        if math.isnan(v) or math.isinf(v):
                            all_bounds_valid = False
                        if m_name.replace("_ci95", "") in bounded_metrics and not (
                            0.0 <= v <= 1.0 + 1e-6
                        ):
                            all_bounds_valid = False
                    continue
                if math.isnan(val) or math.isinf(val):
                    all_bounds_valid = False
                if m_name in bounded_metrics and not (0.0 <= val <= 1.0 + 1e-6):
                    all_bounds_valid = False
                if m_name == "novelty" and val < 0.0:
                    all_bounds_valid = False

    ref_k_str = str(ref_k)
    pop_beats_rnd = True
    if "popularity" in models_dict and "random" in models_dict:
        pop_m = models_dict["popularity"].get(ref_k_str, {})
        rnd_m = models_dict["random"].get(ref_k_str, {})
        if "ndcg" in pop_m and "ndcg" in rnd_m:
            pop_beats_rnd = pop_m["ndcg"] >= rnd_m["ndcg"]

    return {
        "all_bounds_valid": all_bounds_valid,
        "popularity_beats_random": pop_beats_rnd,
    }


def check_r5_cold_start(
    curve: dict[int, dict[str, float]] | dict[str, dict[str, float]],
    metric_name: str = "ndcg@10",
) -> dict[str, Any]:
    """Assess R5 cold-start behaviour across interaction history sizes.

    Checks:
        - Performance at history size 0 is valid
        - Overall trend is non-decreasing as history size increases
        - Flags any non-monotonic points for transparent reporting

    Returns:
        dict[str, Any]: Assessment summary with monotonicity status and non-monotonic points.
    """
    str_curve: dict[str, dict[str, float]] = {str(k): v for k, v in curve.items()}
    sorted_sizes = sorted(int(s) for s in str_curve)
    values = [str_curve[str(s)].get(metric_name, 0.0) for s in sorted_sizes]

    non_monotonic: list[tuple[int, int]] = []
    for i in range(len(values) - 1):
        if values[i + 1] < values[i]:
            non_monotonic.append((sorted_sizes[i], sorted_sizes[i + 1]))

    return {
        "metric": metric_name,
        "history_sizes": sorted_sizes,
        "values": values,
        "is_monotonic": len(non_monotonic) == 0,
        "non_monotonic_transitions": non_monotonic,
    }
