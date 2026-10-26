"""Discovery Engine - Cross-type consistency checks (P6.5).

Verifies that:
1. All three content types ('movies', 'products', 'articles') load through the same
   unified artifact loader (engine.artifacts.load_artifacts) with verified SHA-256 manifests.
2. All three models pass the identical R3 invariant suite via a parametrised test
   over registry.types():
   - R3.1: Monotonic non-increasing scores
   - R3.2: Strictly consecutive 1-indexed ranks (1..k)
   - R3.3: Strict item uniqueness (no duplicates)
   - R3.4: Catalogue membership (all recommended items in catalogue)
   - R3.5: Exclusion compliance (exclude_ids and training seen items never recommended)
   - R3.6: Self-exclusion (similar_items never contains query item)
   - R3.7: Cold-start / History adaptation (recommend_history satisfies all invariants)
   - R3.8: Explanation attribution fidelity (explain references valid history item or None)
   - R3.9: Recency window candidate constraint (freshness boundary preserved if applicable)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from engine import registry
from engine.artifacts import load_artifacts
from engine.config import load_config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


def _assert_r3_invariants(
    recs: list[Any],
    k: int,
    catalogue: set[str],
    exclusions: set[str] | None = None,
    query_item_id: str | None = None,
    fresh_candidates: set[str] | None = None,
) -> None:
    """Assert standard R3 recommendation invariants across any content type."""
    assert len(recs) <= k, f"Expected at most {k} recommendations, got {len(recs)}"
    if not recs:
        return

    # R3.1: Monotonic non-increasing scores
    for i in range(len(recs) - 1):
        assert recs[i].score >= recs[i + 1].score - 1e-9, (
            f"Score monotonicity violated: rank {recs[i].rank} ({recs[i].score}) "
            f"< rank {recs[i + 1].rank} ({recs[i + 1].score})"
        )

    # R3.2: Strictly consecutive 1-indexed ranks
    ranks = [r.rank for r in recs]
    assert ranks == list(range(1, len(recs) + 1)), f"Ranks not consecutive 1..k: {ranks}"

    # R3.3: Strict item uniqueness
    rec_ids = [r.item_id for r in recs]
    assert len(set(rec_ids)) == len(rec_ids), f"Duplicate items in recommendations: {rec_ids}"

    # R3.4: Catalogue membership
    for r in recs:
        assert r.item_id in catalogue, f"Item {r.item_id} not in catalogue"

    # R3.5: Exclusion compliance
    if exclusions:
        for r in recs:
            assert r.item_id not in exclusions, (
                f"Excluded item {r.item_id} found in recommendations"
            )

    # R3.6: Query item self-exclusion
    if query_item_id is not None:
        assert query_item_id not in rec_ids, (
            f"Query item {query_item_id} returned in its own similar_items"
        )

    # R3.9: Recency window candidate constraint
    if fresh_candidates is not None:
        for r in recs:
            assert r.item_id in fresh_candidates, (
                f"Item {r.item_id} outside fresh candidates window {fresh_candidates}"
            )


@pytest.mark.integration
@pytest.mark.parametrize("content_type", registry.types())
def test_cross_type_artifacts_loader(content_type: str) -> None:
    """All registered artifact bundles load cleanly through load_artifacts with verified manifest."""
    art_dir = get_artifacts_dir() / content_type
    assert art_dir.exists(), f"Artifact directory missing: {art_dir}"

    loaded = load_artifacts(art_dir, verify=True)

    assert loaded.manifest is not None
    assert loaded.manifest["content_type"] == content_type
    assert "files" in loaded.manifest
    assert len(loaded.manifest["files"]) >= 4

    assert not loaded.items.empty
    assert "item_id" in loaded.items.columns
    assert "title" in loaded.items.columns

    assert not loaded.interactions.empty
    assert "user_id" in loaded.interactions.columns
    assert "item_id" in loaded.interactions.columns

    assert not loaded.users.empty
    assert "user_id" in loaded.users.columns

    assert loaded.topn is not None
    assert not loaded.topn.empty
    assert "user_id" in loaded.topn.columns
    assert "item_id" in loaded.topn.columns
    assert "rank" in loaded.topn.columns
    assert "score" in loaded.topn.columns

    assert loaded.metrics is not None
    assert "models" in loaded.metrics
    assert loaded.model_dir.exists()


@pytest.mark.integration
@pytest.mark.parametrize("content_type", registry.types())
def test_cross_type_r3_invariant_suite(content_type: str) -> None:
    """All models pass identical R3 invariant suite across all registered content types."""
    art_dir = get_artifacts_dir() / content_type
    loaded = load_artifacts(art_dir, verify=True)
    catalogue = set(loaded.items["item_id"].astype(str))

    spec = load_config(content_type, fast=True)
    model = registry.build_model(spec)
    model.load(loaded.model_dir)

    fresh_cands = getattr(model, "fresh_candidates", None)

    # 1. Test Popular Recommendations (k=10)
    pop_recs = model.popular(k=10)
    _assert_r3_invariants(pop_recs, k=10, catalogue=catalogue, fresh_candidates=fresh_cands)

    # 1b. Test Popular with explicit exclusions
    if len(pop_recs) >= 3:
        excl_test = {pop_recs[0].item_id, pop_recs[1].item_id}
        pop_excl_recs = model.popular(k=5, exclude_ids=excl_test)
        _assert_r3_invariants(
            pop_excl_recs,
            k=5,
            catalogue=catalogue,
            exclusions=excl_test,
            fresh_candidates=fresh_cands,
        )

    # 2. Test Similar Items for multiple catalogue items
    sample_items = list(loaded.items["item_id"].astype(str).head(3))
    for q_item in sample_items:
        sim_recs = model.similar_items(item_id=q_item, k=5)
        _assert_r3_invariants(
            sim_recs,
            k=5,
            catalogue=catalogue,
            query_item_id=q_item,
            fresh_candidates=fresh_cands,
        )

    # 3. Test Known User Recommendations
    sample_users = [
        u for u in loaded.interactions["user_id"].astype(str).unique() if u in model.user_seen
    ][:3]
    for uid in sample_users:
        train_seen = model.user_seen.get(uid, set())
        user_recs = model.recommend_user(user_id=uid, k=5)
        _assert_r3_invariants(
            user_recs,
            k=5,
            catalogue=catalogue,
            exclusions=train_seen if not spec.model.allow_repeat else None,
            fresh_candidates=fresh_cands,
        )

        # Test explicit extra exclusions
        if user_recs:
            extra_excl = {user_recs[0].item_id}
            user_excl_recs = model.recommend_user(user_id=uid, k=5, exclude_ids=extra_excl)
            _assert_r3_invariants(
                user_excl_recs,
                k=5,
                catalogue=catalogue,
                exclusions=train_seen.union(extra_excl),
                fresh_candidates=fresh_cands,
            )

    # 4. Test recommend_history (Cold Start & Incremental History)
    test_hist_items = list(loaded.items["item_id"].astype(str).iloc[:3])
    hist_test = [(item_id, 4.5) for item_id in test_hist_items]

    # History size 0 (Cold baseline)
    cold_recs = model.recommend_history(history=[], k=5)
    _assert_r3_invariants(cold_recs, k=5, catalogue=catalogue, fresh_candidates=fresh_cands)

    # History size > 0
    hist_seen = {item_id for item_id, _ in hist_test}
    hist_recs = model.recommend_history(history=hist_test, k=5)
    _assert_r3_invariants(
        hist_recs,
        k=5,
        catalogue=catalogue,
        exclusions=hist_seen,
        fresh_candidates=fresh_cands,
    )

    # 5. Test Explanation Attribution Fidelity (R3.8)
    if hist_recs:
        top_rec_item = hist_recs[0].item_id
        reason = model.explain(
            recommended_item_id=top_rec_item,
            history=hist_test,
            min_threshold=0.0,
        )
        if reason is not None:
            assert reason.item_id in hist_seen, (
                f"Reason item {reason.item_id} for {content_type} not in input history {hist_seen}"
            )
            assert len(reason.text) > 0
            assert reason.kind in {
                "similar_item",
                "article_similarity",
                "genre_match",
                "category_match",
            }
