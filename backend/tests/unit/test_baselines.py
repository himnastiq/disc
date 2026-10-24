"""Property tests and invariant checks for baseline models (P2.4 / R3)."""

from pathlib import Path

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.config import load_config
from engine.errors import UnknownItem, UnknownUser
from engine.evaluation.checks import check_r3_model_invariants
from engine.models.baselines import PopularityModel, RandomModel
from engine.schema import ContentTypeSpec


@pytest.fixture
def spec() -> ContentTypeSpec:
    return load_config("movies")


@pytest.fixture
def fitted_models(
    spec: ContentTypeSpec,
) -> tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame]:
    items_data = [
        {"item_id": f"item_{i}", "title": f"Title {i}", "categories": ["Action"]}
        for i in range(1, 21)
    ]
    items_df = pd.DataFrame(items_data)

    interactions_data = [
        # user_1 has seen item_1 (positive), item_2 (positive), item_3 (negative)
        {
            "user_id": "user_1",
            "item_id": "item_1",
            "signal": 5.0,
            "timestamp": 100,
            "positive": True,
        },
        {
            "user_id": "user_1",
            "item_id": "item_2",
            "signal": 4.5,
            "timestamp": 110,
            "positive": True,
        },
        {
            "user_id": "user_1",
            "item_id": "item_3",
            "signal": 2.0,
            "timestamp": 120,
            "positive": False,
        },
        # user_2 has seen item_1 (positive), item_4 (positive)
        {
            "user_id": "user_2",
            "item_id": "item_1",
            "signal": 4.0,
            "timestamp": 130,
            "positive": True,
        },
        {
            "user_id": "user_2",
            "item_id": "item_4",
            "signal": 4.5,
            "timestamp": 140,
            "positive": True,
        },
        # user_3 has seen item_2 (positive)
        {
            "user_id": "user_3",
            "item_id": "item_2",
            "signal": 5.0,
            "timestamp": 150,
            "positive": True,
        },
    ]
    interactions_df = pd.DataFrame(interactions_data)

    pop = PopularityModel(spec)
    pop.fit(interactions_df, items_df)

    rnd = RandomModel(spec, seed=42)
    rnd.fit(interactions_df, items_df)

    return pop, rnd, items_df, interactions_df


def test_popularity_ranking_order(
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
) -> None:
    pop, _, _, _ = fitted_models
    # item_1 has 2 positive, item_2 has 2 positive, item_4 has 1 positive
    # item_1 and item_2 tie with 2, item_1 wins tie-break lexicographically
    recs = pop.popular(k=5)
    assert len(recs) == 5
    assert recs[0].item_id == "item_1"
    assert recs[0].score == 2.0
    assert recs[1].item_id == "item_2"
    assert recs[1].score == 2.0
    assert recs[2].item_id == "item_4"
    assert recs[2].score == 1.0


def test_unknown_user_and_item_errors(
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
) -> None:
    pop, rnd, _, _ = fitted_models
    for model in (pop, rnd):
        with pytest.raises(UnknownUser):
            model.recommend_user("unknown_user", k=5)
        with pytest.raises(UnknownItem):
            model.similar_items("unknown_item", k=5)


def test_cold_start_consistency_popularity(
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
) -> None:
    pop, _, _, _ = fitted_models
    # For user_1: seen item_1, item_2, item_3
    # user recommendation
    user_recs = pop.recommend_user("user_1", k=5)

    # cold start recommendation with user_1's history
    history = [("item_1", 5.0), ("item_2", 4.5), ("item_3", 2.0)]
    cold_recs = pop.recommend_history(history, k=5)

    assert len(user_recs) == len(cold_recs)
    for u_rec, c_rec in zip(user_recs, cold_recs, strict=False):
        assert u_rec.item_id == c_rec.item_id
        assert u_rec.score == c_rec.score
        assert u_rec.rank == c_rec.rank


def test_save_load_roundtrip_popularity(
    tmp_path: Path,
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
    spec: ContentTypeSpec,
) -> None:
    pop, _, _, _ = fitted_models
    save_dir = tmp_path / "pop_artifacts"
    pop.save(save_dir)

    loaded = PopularityModel(spec)
    loaded.load(save_dir)

    assert loaded.item_counts == pop.item_counts
    assert loaded.sorted_items == pop.sorted_items
    assert loaded.known_users == pop.known_users
    recs_original = pop.popular(k=5)
    recs_loaded = loaded.popular(k=5)
    assert [r.item_id for r in recs_original] == [r.item_id for r in recs_loaded]


def test_save_load_roundtrip_random(
    tmp_path: Path,
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
    spec: ContentTypeSpec,
) -> None:
    _, rnd, _, _ = fitted_models
    save_dir = tmp_path / "rnd_artifacts"
    rnd.save(save_dir)

    loaded = RandomModel(spec)
    loaded.load(save_dir)

    assert loaded.seed == rnd.seed
    assert loaded.catalogue == rnd.catalogue
    assert loaded.known_users == rnd.known_users
    recs_orig = rnd.recommend_user("user_1", k=5)
    recs_loaded = loaded.recommend_user("user_1", k=5)
    assert [r.item_id for r in recs_orig] == [r.item_id for r in recs_loaded]


# ---------------------------------------------------------------------------
# Hypothesis Property Tests for Invariants (R3)
# ---------------------------------------------------------------------------


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    k=st.integers(min_value=1, max_value=30),
    exclude_sample=st.lists(
        st.sampled_from([f"item_{i}" for i in range(1, 21)]),
        unique=True,
        max_size=10,
    ),
)
def test_r3_invariants_popularity(
    k: int,
    exclude_sample: list[str],
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
) -> None:
    pop, _, items_df, _ = fitted_models
    catalogue = set(items_df["item_id"])

    # 1. Popular endpoint
    recs = pop.popular(k=k, exclude_ids=exclude_sample)
    check_r3_model_invariants(recs, k=k, catalogue=catalogue, exclude_ids=exclude_sample)

    # 2. Similar items must never contain the query item itself
    query_item = "item_1"
    sims = pop.similar_items(query_item, k=k)
    check_r3_model_invariants(sims, k=k, catalogue=catalogue, query_item_id=query_item)


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    k=st.integers(min_value=1, max_value=30),
    user_id=st.sampled_from(["user_1", "user_2", "user_3"]),
)
def test_r3_invariants_random(
    k: int,
    user_id: str,
    fitted_models: tuple[PopularityModel, RandomModel, pd.DataFrame, pd.DataFrame],
) -> None:
    _, rnd, items_df, interactions_df = fitted_models
    catalogue = set(items_df["item_id"])

    # Determinism check: multiple calls must return the exact same recommendations
    recs1 = rnd.recommend_user(user_id, k=k)
    recs2 = rnd.recommend_user(user_id, k=k)
    assert [r.item_id for r in recs1] == [r.item_id for r in recs2]

    # Invariants check (seen items must be excluded)
    seen_items = set(interactions_df[interactions_df["user_id"] == user_id]["item_id"])
    check_r3_model_invariants(recs1, k=k, catalogue=catalogue, exclude_ids=seen_items)
