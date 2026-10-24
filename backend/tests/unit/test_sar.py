"""Unit and property tests for SarModel wrapper (P3.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from scipy import sparse

from engine.config import load_config
from engine.errors import UnknownItem, UnknownUser
from engine.evaluation.checks import check_r3_model_invariants
from engine.models.sar import SarModel

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module")
def small_movies_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a small self-contained interactions and catalogue fixture for SAR tests."""
    items = pd.DataFrame(
        [
            {"item_id": f"movie_{i}", "title": f"Movie {i}", "categories": ["Action"]}
            for i in range(1, 16)
        ]
    )

    # 5 users, each with 5-8 interactions
    interactions_list = []
    for u in range(1, 6):
        uid = f"user_{u}"
        for step in range(1, 7):
            item_idx = ((u * 3 + step) % 15) + 1
            interactions_list.append(
                {
                    "user_id": uid,
                    "item_id": f"movie_{item_idx}",
                    "signal": 5.0 if step % 2 == 0 else 3.0,
                    "timestamp": 1000 * u + step * 10,
                    "positive": True,
                }
            )

    interactions = pd.DataFrame(interactions_list)
    return interactions, items


@pytest.fixture(scope="module")
def fitted_sar_model(small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame]) -> SarModel:
    """Provide a fitted SarModel instance."""
    interactions, items = small_movies_fixture
    spec = load_config("movies", fast=True)
    model = SarModel(spec)
    model.fit(interactions, items)
    return model


def test_sar_fit_and_r3_invariants(
    fitted_sar_model: SarModel,
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify SAR satisfies R3 model invariants for all training users."""
    interactions, items = small_movies_fixture
    users = list(interactions["user_id"].unique())
    catalogue = set(items["item_id"])

    for user in users:
        seen = set(interactions[interactions["user_id"] == user]["item_id"])
        for k in [3, 5, 10]:
            recs = fitted_sar_model.recommend_user(user, k=k)
            check_r3_model_invariants(recs, k=k, catalogue=catalogue, exclude_ids=seen)


def test_sar_seen_items_excluded(
    fitted_sar_model: SarModel,
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify SAR never recommends already seen items when allow_repeat is False."""
    interactions, _ = small_movies_fixture
    for uid in ["user_1", "user_2"]:
        seen_items = set(interactions[interactions["user_id"] == uid]["item_id"])
        recs = fitted_sar_model.recommend_user(uid, k=10)
        rec_ids = {r.item_id for r in recs}
        assert rec_ids.isdisjoint(seen_items), (
            f"Seen items leaked in recommendations: {rec_ids & seen_items}"
        )


def test_sar_unknown_user_raises(fitted_sar_model: SarModel) -> None:
    """Verify recommend_user raises UnknownUser with user_id attribute and clear message."""
    with pytest.raises(UnknownUser) as exc_info:
        fitted_sar_model.recommend_user("non_existent_user_999", k=5)
    assert exc_info.value.user_id == "non_existent_user_999"
    assert exc_info.value.content_type == "movies"
    assert "Unknown user ID: 'non_existent_user_999'" in str(exc_info.value)


def test_sar_similar_items_never_returns_query_item(
    fitted_sar_model: SarModel,
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify similar_items never returns the query item itself."""
    _, items = small_movies_fixture
    for item_id in items["item_id"]:
        sims = fitted_sar_model.similar_items(item_id, k=5)
        sim_ids = [s.item_id for s in sims]
        assert item_id not in sim_ids, (
            f"Query item {item_id} was returned in its own similarity list"
        )
        assert len(sim_ids) == len(set(sim_ids)), "Duplicate items returned in similarity"


def test_sar_unknown_item_raises(fitted_sar_model: SarModel) -> None:
    """Verify similar_items raises UnknownItem with item_id attribute and clear message."""
    with pytest.raises(UnknownItem) as exc_info:
        fitted_sar_model.similar_items("movie_unknown_999", k=5)
    assert exc_info.value.item_id == "movie_unknown_999"
    assert exc_info.value.content_type == "movies"
    assert "Unknown item ID: 'movie_unknown_999'" in str(exc_info.value)


def test_sar_popular_deterministic(fitted_sar_model: SarModel) -> None:
    """Verify popular items ordering is deterministic and excludes specified IDs."""
    pop1 = fitted_sar_model.popular(k=5)
    pop2 = fitted_sar_model.popular(k=5)
    assert [p.item_id for p in pop1] == [p.item_id for p in pop2]
    assert [p.score for p in pop1] == [p.score for p in pop2]

    excluded_item = pop1[0].item_id
    pop_excluded = fitted_sar_model.popular(k=5, exclude_ids={excluded_item})
    assert excluded_item not in [p.item_id for p in pop_excluded]


def test_sar_save_and_load_roundtrip(
    fitted_sar_model: SarModel,
    tmp_path: Path,
) -> None:
    """Verify saving to disk and loading into fresh instance produces bitwise identical recommendations."""
    save_dir = tmp_path / "sar_model_artifacts"
    fitted_sar_model.save(save_dir)

    assert (save_dir / "model_meta.json").exists()
    assert (save_dir / "index2item.json").exists()
    assert (save_dir / "index2user.json").exists()
    assert (save_dir / "item_similarity.npz").exists()
    assert (save_dir / "user_affinity.npz").exists()
    assert (save_dir / "item_frequencies.npy").exists()

    spec = load_config("movies", fast=True)
    loaded_model = SarModel(spec)
    loaded_model.load(save_dir)

    # Compare recommendations on test user
    orig_recs = fitted_sar_model.recommend_user("user_1", k=5)
    loaded_recs = loaded_model.recommend_user("user_1", k=5)

    assert [(r.item_id, r.score, r.rank) for r in orig_recs] == [
        (r.item_id, r.score, r.rank) for r in loaded_recs
    ]

    # Compare similar items
    orig_sims = fitted_sar_model.similar_items("movie_1", k=5)
    loaded_sims = loaded_model.similar_items("movie_1", k=5)
    assert [(r.item_id, r.score, r.rank) for r in orig_sims] == [
        (r.item_id, r.score, r.rank) for r in loaded_sims
    ]


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    k=st.integers(min_value=1, max_value=10),
    user_idx=st.integers(min_value=1, max_value=5),
)
def test_sar_hypothesis_invariants(
    fitted_sar_model: SarModel,
    k: int,
    user_idx: int,
) -> None:
    """Property test verifying length <= k, no duplicates, and catalogue membership."""
    uid = f"user_{user_idx}"
    recs = fitted_sar_model.recommend_user(uid, k=k)

    assert len(recs) <= k
    assert len(recs) == len({r.item_id for r in recs}), "Duplicates found in recommendation list"
    assert all(r.item_id in fitted_sar_model.catalogue for r in recs)
    assert all(isinstance(r.score, float) for r in recs)

    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True), "Scores are not sorted descending"


def test_sar_popularity_padding_preserves_non_increasing_scores(
    fitted_sar_model: SarModel,
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify forced popularity padding assigns scores strictly non-increasing and passes R3."""
    interactions, items = small_movies_fixture
    catalogue = set(items["item_id"])

    # For user_1, request k=8 which exceeds the number of novel similar candidates with score > 0
    uid = "user_1"
    seen = set(interactions[interactions["user_id"] == uid]["item_id"])
    expected_k = min(8, len(catalogue - seen))

    # Force k so padding is guaranteed
    recs = fitted_sar_model.recommend_user(uid, k=8)
    assert len(recs) == expected_k

    # Must satisfy all R3 invariants including non-increasing scores
    check_r3_model_invariants(recs, k=8, catalogue=catalogue, exclude_ids=seen)

    # Verify scores are strictly non-increasing across the transition into padded items
    user_scores = [r.score for r in recs]
    for i in range(len(user_scores) - 1):
        assert user_scores[i] >= user_scores[i + 1], (
            f"User rec scores not non-increasing at index {i}: {user_scores[i]} < {user_scores[i + 1]}"
        )

    # Test via recommend_history with a single item to force heavy padding
    hist = [("movie_1", 5.0)]
    hist_recs = fitted_sar_model.recommend_history(hist, k=10)
    assert len(hist_recs) == 10
    check_r3_model_invariants(hist_recs, k=10, catalogue=catalogue, exclude_ids={"movie_1"})

    # Verify scores are strictly non-increasing across the transition into padded items
    hist_scores = [r.score for r in hist_recs]
    for i in range(len(hist_scores) - 1):
        assert hist_scores[i] >= hist_scores[i + 1], (
            f"Scores not non-increasing at index {i}: {hist_scores[i]} < {hist_scores[i + 1]}"
        )


def test_sar_top_neighbors_per_item_sparsification(
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify item_similarity retains at most top_neighbors_per_item sparse entries per row."""
    interactions, items = small_movies_fixture
    spec = load_config("movies", fast=True)
    # Set tight neighbor cap of 3
    spec.serving.top_neighbors_per_item = 3

    model = SarModel(spec)
    model.fit(interactions, items)
    assert model.sar is not None
    sim = model.sar.item_similarity
    assert isinstance(sim, sparse.csr_matrix)

    # Check each row has at most 3 non-zeros
    nnz_per_row = np.diff(sim.indptr)
    assert (nnz_per_row <= 3).all(), f"Row has > 3 neighbors: {nnz_per_row.max()}"

    # Diagonal must be 0 (no self-similarity)
    diag = sim.diagonal()
    assert (diag == 0.0).all(), "Diagonal contains non-zero entries"

    # similar_items must satisfy R3 invariants
    for item_id in items["item_id"]:
        recs = model.similar_items(item_id, k=5)
        check_r3_model_invariants(recs, k=5, catalogue=set(items["item_id"]), query_item_id=item_id)


def test_sar_max_items_in_similarity_budget_cap(
    small_movies_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify max_items_in_similarity restricts similarity matrix to top-popular items."""
    interactions, items = small_movies_fixture
    spec = load_config("movies", fast=True)
    # 15 items in small_movies_fixture; cap to top 5
    spec.serving.max_items_in_similarity = 5

    model = SarModel(spec)
    model.fit(interactions, items)
    assert model.sar is not None

    # Similarity matrix must have exactly 5 items
    assert model.sar.n_items == 5
    assert len(model.sar.item2index) == 5
    assert model.sar.item_similarity.shape == (5, 5)

    # Full catalogue still retains all 15 items
    assert len(model.catalogue) == 15

    # Top 5 items are indeed the top 5 most popular
    expected_top5 = set(model.sorted_popular[:5])
    assert set(model.sar.item2index.keys()) == expected_top5

    # Capped-out item falls back to popular and satisfies R3
    capped_out_item = model.sorted_popular[-1]
    assert capped_out_item not in model.sar.item2index
    sims = model.similar_items(capped_out_item, k=5)
    check_r3_model_invariants(
        sims, k=5, catalogue=set(items["item_id"]), query_item_id=capped_out_item
    )

    # Unknown item not in catalogue still raises UnknownItem
    with pytest.raises(UnknownItem) as exc_info:
        model.similar_items("totally_unknown_movie", k=5)
    assert exc_info.value.item_id == "totally_unknown_movie"
