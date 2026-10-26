"""Phase 3 Gate and 'break your own work' ritual (P3.13).

Rigorous gate checks and adversarial tests for the Movies pipeline:
1. Popularity computed from train only (future viral test items never leak into popularity).
2. No test items in similarity (test-only co-occurrences never appear in item_similarity).
3. Reasons only reference history items (explanations strictly cite history items).
4. Seen items never recommended (seen items strictly excluded, even under popularity fallback).
5. Phase 3 artifact validation (manifest, schema, and R1-R5 invariants).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.artifacts import verify_artifacts
from engine.config import load_config
from engine.evaluation.checks import (
    check_r1_data_validity,
    check_r2_no_leakage,
    check_r3_model_invariants,
    check_r4_evaluation_validity,
)
from engine.models.baselines import PopularityModel
from engine.models.sar import SarModel


@pytest.fixture(scope="module")
def movies_spec():
    """Load fast movies config for gate testing."""
    return load_config("movies", fast=True)


@pytest.fixture(scope="module")
def synthetic_split_dataset():
    """Create a synthetic train/test split with distinct future items for ritual checks."""
    train_items = [f"item_{i}" for i in range(1, 31)]
    future_test_items = [f"future_item_{i}" for i in range(1, 11)]
    all_items_list = train_items + future_test_items

    items_df = pd.DataFrame(
        [
            {"item_id": iid, "title": f"Title {iid}", "categories": ["Drama"]}
            for iid in all_items_list
        ]
    )

    # Train interactions: 10 users, each interacting with items such that all 30 train_items have interactions
    train_rows = []
    base_ts = 1_000_000_000
    for u in range(1, 11):
        uid = f"user_{u}"
        # Each user interacts with 10 items; together covering all 30 items
        for offset in range(10):
            item_num = ((u - 1) * 3 + offset) % 30 + 1
            iid = f"item_{item_num}"
            train_rows.append(
                {
                    "user_id": uid,
                    "item_id": iid,
                    "signal": 4.0,
                    "timestamp": base_ts + (u * 1000) + offset,
                }
            )
    train_df = pd.DataFrame(train_rows)

    # Test interactions: future timestamp, contains future_test_items with massive counts
    test_rows = []
    future_ts = base_ts + 1_000_000
    for u in range(1, 11):
        uid = f"user_{u}"
        for idx in range(1, 11):
            iid = f"future_item_{idx}"
            test_rows.append(
                {
                    "user_id": uid,
                    "item_id": iid,
                    "signal": 5.0,
                    "timestamp": future_ts + (u * 1000) + idx,
                }
            )
    test_df = pd.DataFrame(test_rows)

    return train_df, test_df, items_df


@pytest.mark.integration
def test_gate_popularity_computed_from_train_only(
    movies_spec,
    synthetic_split_dataset,
) -> None:
    """RITUAL 1: Verify popularity is strictly computed from train interactions.

    Future items in test_df with viral engagement must NEVER leak into popularity.
    """
    train_df, test_df, items_df = synthetic_split_dataset
    check_r2_no_leakage(train_df, test_df)

    # Fit PopularityModel and SarModel strictly on train_df
    pop_model = PopularityModel(movies_spec)
    pop_model.fit(train_df, items_df)

    sar_model = SarModel(movies_spec)
    sar_model.fit(train_df, items_df)

    # Check top popular recommendations (k=15 <= 30 train items with positive counts)
    pop_recs = pop_model.popular(k=15)
    sar_pop_recs = sar_model.popular(k=15)

    pop_rec_ids = {r.item_id for r in pop_recs}
    sar_rec_ids = {r.item_id for r in sar_pop_recs}

    # Assert no future test item appears in popular recommendations
    future_items = {f"future_item_{i}" for i in range(1, 11)}
    assert pop_rec_ids.isdisjoint(future_items), "Future test items leaked into PopularityModel!"
    assert sar_rec_ids.isdisjoint(future_items), "Future test items leaked into SAR popularity!"

    # Every item in popular recs must have positive count from train_df
    train_items = set(train_df["item_id"])
    assert pop_rec_ids.issubset(train_items)
    assert sar_rec_ids.issubset(train_items)

    # Break-your-own-work check: If a model was accidentally fitted on test_df,
    # future items would dominate popularity
    leaked_pop_model = PopularityModel(movies_spec)
    leaked_pop_model.fit(test_df, items_df)
    leaked_recs = {r.item_id for r in leaked_pop_model.popular(k=10)}
    assert leaked_recs == future_items, "Leaked test model should have selected future items"


@pytest.mark.integration
def test_gate_no_test_items_in_similarity(
    movies_spec,
    synthetic_split_dataset,
) -> None:
    """RITUAL 2: Verify test items never leak into item similarity structure.

    Items unobserved in training must have zero similarity or zero non-zero neighbors.
    """
    train_df, test_df, items_df = synthetic_split_dataset
    sar_model = SarModel(movies_spec)
    sar_model.fit(train_df, items_df)

    assert sar_model.sar is not None
    sim_matrix = sar_model.sar.item_similarity
    item2index = sar_model.sar.item2index

    # Future test items that co-occur in test_df must have ZERO similarity in train-fitted model
    for i in range(1, 11):
        future_iid = f"future_item_{i}"
        if future_iid in item2index:
            idx = item2index[future_iid]
            row = sim_matrix[idx, :]
            nnz = row.nnz if hasattr(row, "nnz") else np.count_nonzero(row)
            assert nnz == 0, (
                f"Future test item {future_iid} has non-zero similarity in train model!"
            )

    # Break-your-own-work check: If fitted on test_df, future items DO have non-zero similarity
    leaked_sar = SarModel(movies_spec)
    leaked_sar.fit(test_df, items_df)
    assert leaked_sar.sar is not None
    leaked_sim = leaked_sar.sar.item_similarity
    leaked_item2index = leaked_sar.sar.item2index

    f1_idx = leaked_item2index["future_item_1"]
    f1_row = leaked_sim[f1_idx, :]
    f1_nnz = f1_row.nnz if hasattr(f1_row, "nnz") else np.count_nonzero(f1_row)
    assert f1_nnz > 0, "Test-fitted model must have non-zero co-occurrences between test items"


@pytest.mark.integration
def test_gate_reasons_only_reference_history_items(
    movies_spec,
    synthetic_split_dataset,
) -> None:
    """RITUAL 3: Verify attribution reasons only reference items in the user's history."""
    train_df, _, items_df = synthetic_split_dataset
    sar_model = SarModel(movies_spec)
    sar_model.fit(train_df, items_df)

    # 1. Known user explanation check
    for uid in ["user_1", "user_2", "user_3"]:
        user_history = set(train_df[train_df["user_id"] == uid]["item_id"])
        recs = sar_model.recommend_user(uid, k=5)
        for r in recs:
            reason = sar_model.explain(user_id=uid, item_id=r.item_id)
            if reason is not None and reason.item_id is not None:
                assert reason.item_id in user_history, (
                    f"Reason item {reason.item_id} for user {uid} is not in user history {user_history}"
                )
                assert reason.item_id != r.item_id, "Reason cannot be the recommended item itself"

    # 2. Hypothetical cold-start history explanation check
    hypothetical_history = [("item_1", 5.0), ("item_2", 4.0), ("item_3", 5.0)]
    cold_history_ids = {h[0] for h in hypothetical_history}
    cold_recs = sar_model.recommend_history(hypothetical_history, k=5)
    for r in cold_recs:
        reason = sar_model.explain(user_id=None, item_id=r.item_id, history=hypothetical_history)
        if reason is not None and reason.item_id is not None:
            assert reason.item_id in cold_history_ids, (
                f"Cold start reason {reason.item_id} is not in provided history {cold_history_ids}"
            )
            assert reason.item_id != r.item_id


@pytest.mark.integration
def test_gate_seen_items_never_recommended_even_under_popular_fallback(
    movies_spec,
    synthetic_split_dataset,
) -> None:
    """RITUAL 4: Verify seen items are strictly excluded from recommendations.

    Adversarial test: A user has seen the TOP 5 most popular items.
    Even with popularity fallback or neighbor overlaps, none of those 5 seen items can appear.
    """
    train_df, _, items_df = synthetic_split_dataset
    sar_model = SarModel(movies_spec)
    sar_model.fit(train_df, items_df)

    # Find the top 5 most popular items in train_df
    top5_popular = list(train_df["item_id"].value_counts().head(5).index)

    # Known user test: verify seen items never appear
    for uid in ["user_1", "user_2"]:
        user_seen = set(train_df[train_df["user_id"] == uid]["item_id"])
        recs = sar_model.recommend_user(uid, k=20)
        rec_ids = [r.item_id for r in recs]
        assert set(rec_ids).isdisjoint(user_seen), f"Seen items recommended to user {uid}"

    # Adversarial cold-start test: history contains exactly the top 5 popular items
    adversarial_history = [(iid, 5.0) for iid in top5_popular]
    recs = sar_model.recommend_history(adversarial_history, k=20)
    rec_ids = [r.item_id for r in recs]
    assert set(rec_ids).isdisjoint(set(top5_popular)), (
        f"Seen popular items appeared in cold start recommendations: {set(rec_ids).intersection(set(top5_popular))}"
    )


@pytest.mark.integration
@pytest.mark.real_data
def test_gate_real_movies_artifacts_integrity() -> None:
    """Verify artifacts/movies directory passes cryptographic manifest check and R1-R5 invariants."""
    artifacts_dir = Path(__file__).resolve().parent.parent.parent.parent / "artifacts" / "movies"
    if not (artifacts_dir / "manifest.json").exists():
        pytest.skip(
            "artifacts/movies/manifest.json does not exist yet; run make train TYPE=movies first"
        )

    # Cryptographic integrity check
    manifest = verify_artifacts(artifacts_dir)
    assert manifest["content_type"] == "movies"

    # Load and verify items and interactions
    items_df = pd.read_parquet(artifacts_dir / "items.parquet")
    interactions_df = pd.read_parquet(artifacts_dir / "interactions.parquet")

    # R1: Data report sanity
    check_r1_data_validity(interactions_df, items_df)

    # Load metrics.json and check R4 evaluation validity
    import json

    with open(artifacts_dir / "metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)

    # Check R4 validity
    check_r4_evaluation_validity(metrics)
    assert metrics["sanity_checks"]["all_bounds_valid"] is True
    assert metrics["sanity_checks"]["popularity_beats_random"] is True
    assert metrics["sanity_checks"]["leakage_check_passed"] is True
    assert metrics["sanity_checks"]["model_beats_popularity"] is True

    # Check model invariants on saved SAR model
    spec = load_config("movies", fast=False)
    sar_model = SarModel(spec)
    sar_model.load(artifacts_dir / "model")
    cat_set = set(items_df["item_id"])
    assert sar_model.sar is not None
    for uid in list(sar_model.sar.user2index.keys())[:20]:
        user_train_seen = sar_model.user_seen.get(uid, set())
        recs = sar_model.recommend_user(uid, k=10)
        check_r3_model_invariants(recs=recs, k=10, catalogue=cat_set, exclude_ids=user_train_seen)
