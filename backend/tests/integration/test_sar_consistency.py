"""Integration tests for SAR cold-start consistency (P3.6 / R3).

Verifies that for known training users, recommendations from `recommend_user`
equal recommendations from `recommend_history` on their training history:
1. Synthetic fixture version that runs unconditionally in CI without downloaded data.
2. Shipped configuration (time decay on) documenting expected divergence between
   user-based (time-decayed timestamps) and cold-start (flat hypothetical signals) scoring.
3. Score and item ID comparisons within floating-point tolerance.
4. MovieLens 100K 50-user integration consistency tests.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.adapters.movielens import MovieLensAdapter
from engine.config import load_config
from engine.evaluation.checks import check_r3_model_invariants
from engine.models.sar import SarModel


@pytest.fixture(scope="module")
def synthetic_sar_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a self-contained synthetic dataset for CI consistency testing without downloads."""
    items = pd.DataFrame(
        [
            {"item_id": f"movie_{i}", "title": f"Movie {i}", "categories": ["Action"]}
            for i in range(1, 31)
        ]
    )

    # 10 users with multiple interactions spread over 60 days
    base_ts = 1_000_000_000
    rows = []
    for u in range(1, 11):
        uid = f"user_{u}"
        for offset, item_idx in enumerate(range(u, u + 10)):
            item_id = f"movie_{item_idx % 30 + 1}"
            ts = base_ts + (offset * 5 * 86400)
            rating = 3.0 + ((u + offset) % 3)
            rows.append({"user_id": uid, "item_id": item_id, "signal": rating, "timestamp": ts})

    interactions = pd.DataFrame(rows)
    return interactions, items


def test_sar_cold_start_consistency_synthetic_ci_flat_weighting(
    synthetic_sar_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify SAR consistency on synthetic fixture in CI without downloaded data (flat weighting).

    Under flat weighting, history tuples (item_id, signal) from training data construct
    the exact same user affinity vector, producing matching item IDs and scores.
    """
    interactions, items = synthetic_sar_fixture
    catalogue = set(items["item_id"])

    spec = load_config("movies", fast=True)
    spec.model.params["timedecay_formula"] = False

    model = SarModel(spec)
    model.fit(interactions, items)

    unique_users = sorted(interactions["user_id"].unique())
    assert len(unique_users) == 10

    for user_id in unique_users:
        user_rows = interactions[interactions["user_id"] == user_id]
        user_history = list(zip(user_rows["item_id"], user_rows["signal"], strict=False))

        recs_user = model.recommend_user(user_id, k=5)
        recs_hist = model.recommend_history(user_history, k=5)

        # Invariant checks on both outputs
        check_r3_model_invariants(recs_user, k=5, catalogue=catalogue)
        check_r3_model_invariants(recs_hist, k=5, catalogue=catalogue)

        user_item_ids = [r.item_id for r in recs_user]
        hist_item_ids = [r.item_id for r in recs_hist]
        user_scores = [r.score for r in recs_user]
        hist_scores = [r.score for r in recs_hist]

        assert user_item_ids == hist_item_ids, (
            f"User {user_id} item mismatch: {user_item_ids} != {hist_item_ids}"
        )
        assert user_scores == pytest.approx(hist_scores, rel=1e-5), (
            f"User {user_id} score mismatch: {user_scores} != {hist_scores}"
        )


def test_sar_cold_start_consistency_shipped_config_timedecay_synthetic_ci(
    synthetic_sar_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify consistency and expected divergence with shipped config (time decay on) in CI.

    Expected difference between user-based and history-based scoring:
    ----------------------------------------------------------------
    Under the shipped configuration, time decay is enabled (half-life = 30 days).
    In `recommend_user`, historical user interactions are weighted by:
        affinity(item, timestamp) = signal * 2 ** (-(t_now - timestamp) / half_life)
    which exponentially discounts older interactions and prioritizes recent items.

    In cold-start scoring via `recommend_history`, hypothetical interaction histories
    provided at serving time (e.g. from an onboarding questionnaire or temporary session)
    do not possess historical timestamps and are weighted with flat affinity:
        affinity(item) = signal * 1.0

    Because older interactions in the training split have 2^(-dt / half_life) < 1.0,
    flat-weighted cold-start affinities are strictly greater than or equal to decayed affinities.
    Consequently, raw scores from flat cold-start history will generally exceed user-based scores,
    and ranking may diverge if the user's interaction history spans significant elapsed time.

    When `recommend_history` is supplied with the user's exact decayed training affinities,
    the mathematical inputs to the similarity matrix multiplication are identical, and both
    item IDs and numerical scores match within floating-point tolerance (rel=1e-5).
    """
    interactions, items = synthetic_sar_fixture
    catalogue = set(items["item_id"])

    # Shipped config: timedecay_formula is True
    spec = load_config("movies", fast=True)
    assert spec.model.params.get("timedecay_formula") is True, (
        "Shipped config must have timedecay_formula enabled"
    )

    model = SarModel(spec)
    model.fit(interactions, items)
    assert model.sar is not None

    unique_users = sorted(interactions["user_id"].unique())

    for user_id in unique_users:
        user_rows = interactions[interactions["user_id"] == user_id]
        user_history_flat = list(zip(user_rows["item_id"], user_rows["signal"], strict=False))

        recs_user = model.recommend_user(user_id, k=5)
        recs_hist_flat = model.recommend_history(user_history_flat, k=5)

        # Both pipelines must satisfy R3 invariants
        check_r3_model_invariants(recs_user, k=5, catalogue=catalogue)
        check_r3_model_invariants(recs_hist_flat, k=5, catalogue=catalogue)

        # 1. Verification of expected difference: flat cold-start scores >= decayed user scores
        # Due to 2^(-dt/half_life) <= 1.0, flat affinity sum >= decayed affinity sum
        user_top_score = recs_user[0].score if recs_user else 0.0
        hist_top_score = recs_hist_flat[0].score if recs_hist_flat else 0.0
        assert hist_top_score >= user_top_score - 1e-6, (
            f"Expected flat history score ({hist_top_score}) >= decayed user score ({user_top_score})"
        )

        # 2. Verification of exact consistency when decayed affinities are supplied
        u_idx = model.sar.user2index[user_id]
        row = model.sar.user_affinity[u_idx, :]
        history_affinities = [
            (model.sar.index2item[idx], float(val))
            for idx, val in zip(row.indices, row.data, strict=False)
        ]

        recs_hist_decayed = model.recommend_history(history_affinities, k=5)
        check_r3_model_invariants(recs_hist_decayed, k=5, catalogue=catalogue)

        user_item_ids = [r.item_id for r in recs_user]
        hist_decayed_ids = [r.item_id for r in recs_hist_decayed]
        user_scores = [r.score for r in recs_user]
        hist_decayed_scores = [r.score for r in recs_hist_decayed]

        assert user_item_ids == hist_decayed_ids, (
            f"User {user_id} item mismatch: {user_item_ids} != {hist_decayed_ids}"
        )
        assert user_scores == pytest.approx(hist_decayed_scores, rel=1e-5), (
            f"User {user_id} score mismatch: {user_scores} != {hist_decayed_scores}"
        )


@pytest.fixture(scope="module")
def trained_movielens_sar() -> tuple[SarModel, pd.DataFrame, pd.DataFrame]:
    """Train SarModel on MovieLens 100K data with flat weighting convention."""
    spec = load_config("movies", fast=True)
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


@pytest.mark.real_data
def test_sar_cold_start_consistency_50_known_users_flat_weighting(
    trained_movielens_sar: tuple[SarModel, pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify top-10 from recommend_user equals top-10 from recommend_history for 50 sampled users.

    Under flat weighting, history tuples (item_id, signal) from train_df construct
    the exact same user affinity vector and produce identical recommendations and scores.
    """
    model, train_df, items = trained_movielens_sar
    catalogue = set(items["item_id"])

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
        user_scores = [r.score for r in recs_user]
        hist_scores = [r.score for r in recs_hist]

        if user_item_ids != hist_item_ids or user_scores != pytest.approx(hist_scores, rel=1e-5):
            mismatches.append(
                f"User {user_id}: recommend_user={user_item_ids} vs recommend_history={hist_item_ids}"
            )

    assert not mismatches, f"Found {len(mismatches)} consistency mismatches:\n" + "\n".join(
        mismatches[:5]
    )


@pytest.mark.real_data
def test_sar_cold_start_consistency_timedecay_affinities(
    trained_movielens_sar: tuple[SarModel, pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify consistency when model is trained with time decay and supplied with training affinities."""
    spec = load_config("movies", fast=True)
    spec.model.params["timedecay_formula"] = True

    _, train_df, items = trained_movielens_sar
    model = SarModel(spec)
    model.fit(train_df, items)
    assert model.sar is not None

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
        user_scores = [r.score for r in recs_user]
        hist_scores = [r.score for r in recs_hist]

        if user_item_ids != hist_item_ids or user_scores != pytest.approx(hist_scores, rel=1e-5):
            mismatches.append(f"User {user_id} mismatch under time decay")

    assert not mismatches, f"Found {len(mismatches)} mismatches under time decay."
