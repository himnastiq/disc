"""Integration tests for SAR cold-start consistency (P3.6 / R3).

Verifies that for 50 sampled known training users, top-10 recommendations
from `recommend_user` equal top-10 recommendations from `recommend_history`
on their training history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from engine.adapters.movielens import MovieLensAdapter
from engine.config import load_config
from engine.evaluation.checks import check_r3_model_invariants
from engine.models.sar import SarModel

if TYPE_CHECKING:
    import pandas as pd


@pytest.fixture(scope="module")
def trained_movielens_sar() -> tuple[SarModel, pd.DataFrame, pd.DataFrame]:
    """Train SarModel on MovieLens 100K data with flat weighting convention."""
    spec = load_config("movies", fast=True)
    # Use flat weighting (timedecay_formula=False) to match hypothetical history convention
    spec.model.params["timedecay_formula"] = False

    adapter = MovieLensAdapter(spec)
    if (
        not (adapter.raw_dir / "ml-100k").exists()
        and not (adapter.raw_dir / "ml-100k.zip").exists()
    ):
        pytest.skip("MovieLens 100K dataset not found in data/raw/movielens")

    interactions = adapter.interactions()
    items = adapter.items()
    train_df, _, _ = adapter.split(interactions)

    model = SarModel(spec)
    model.fit(train_df, items)
    return model, train_df, items


def test_sar_cold_start_consistency_50_known_users_flat_weighting(
    trained_movielens_sar: tuple[SarModel, pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify top-10 from recommend_user equals top-10 from recommend_history for 50 sampled users.

    Under flat weighting, history tuples (item_id, signal) from train_df construct
    the exact same user affinity vector and produce identical recommendations.
    """
    model, train_df, items = trained_movielens_sar
    catalogue = set(items["item_id"])

    # Sample 50 unique users deterministically
    unique_users = sorted(train_df["user_id"].unique())[:50]
    assert len(unique_users) == 50

    mismatches: list[str] = []

    for user_id in unique_users:
        user_rows = train_df[train_df["user_id"] == user_id]
        user_history = list(zip(user_rows["item_id"], user_rows["signal"], strict=False))

        recs_user = model.recommend_user(user_id, k=10)
        recs_hist = model.recommend_history(user_history, k=10)

        # Invariant checks on both outputs
        check_r3_model_invariants(recs_user, k=10, catalogue=catalogue)
        check_r3_model_invariants(recs_hist, k=10, catalogue=catalogue)

        user_item_ids = [r.item_id for r in recs_user]
        hist_item_ids = [r.item_id for r in recs_hist]

        if user_item_ids != hist_item_ids:
            mismatches.append(
                f"User {user_id}: recommend_user={user_item_ids} vs recommend_history={hist_item_ids}"
            )

    assert not mismatches, f"Found {len(mismatches)} consistency mismatches:\n" + "\n".join(
        mismatches[:5]
    )


def test_sar_cold_start_consistency_timedecay_affinities(
    trained_movielens_sar: tuple[SarModel, pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify consistency when model is trained with time decay and supplied with training affinities."""
    spec = load_config("movies", fast=True)
    spec.model.params["timedecay_formula"] = True

    _, train_df, items = trained_movielens_sar
    model = SarModel(spec)
    model.fit(train_df, items)

    unique_users = sorted(train_df["user_id"].unique())[:50]
    assert len(unique_users) == 50

    mismatches: list[str] = []

    for user_id in unique_users:
        u_idx = model.sar.user2index[user_id]
        row = model.sar.user_affinity[u_idx, :]
        history_affinities = [
            (model.sar.index2item[idx], float(val))
            for idx, val in zip(row.indices, row.data, strict=False)
        ]

        recs_user = model.recommend_user(user_id, k=10)
        recs_hist = model.recommend_history(history_affinities, k=10)

        user_item_ids = [r.item_id for r in recs_user]
        hist_item_ids = [r.item_id for r in recs_hist]

        if user_item_ids != hist_item_ids:
            mismatches.append(f"User {user_id} mismatch under time decay")

    assert not mismatches, f"Found {len(mismatches)} mismatches under time decay."
