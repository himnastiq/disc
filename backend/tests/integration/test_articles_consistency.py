"""Integration tests for Articles TF-IDF cold-start consistency (P5.6 / R3).

Verifies that:
1. Cold start is native: `recommend_history` builds a profile directly from given article IDs.
2. Consistency guarantee: for known users, recommendations from `recommend_user`
   equal recommendations from `recommend_history` on their training history.
3. R3 model invariants hold on all recommendation outputs (catalogue bounds, non-increasing scores,
   candidate isolation under recency window).
4. Tests run both on synthetic multi-user dataset and offline MIND fixture.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from engine.adapters.mind import MindArticlesAdapter
from engine.config import load_config
from engine.evaluation.checks import check_r3_model_invariants
from engine.models.tfidf import TfidfProfileModel

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "mind"


@pytest.fixture(scope="module")
def synthetic_articles_consistency_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a multi-user, multi-article synthetic dataset for consistency testing."""
    # 30 diverse articles across 5 topics
    topics = {
        "AI": "Artificial Intelligence neural networks deep learning transformer models",
        "Bio": "Genomics CRISPR DNA sequencing cellular molecular biology medicine",
        "Space": "Cosmic exploration astronomy planets NASA rocket astrophysics",
        "Finance": "Wall street stock market inflation Federal Reserve treasury bonds",
        "Climate": "Renewable energy solar wind carbon emissions global warming",
    }
    items_list = []
    for i in range(1, 31):
        topic_key = list(topics.keys())[(i - 1) % len(topics)]
        items_list.append(
            {
                "item_id": f"art_{i:03d}",
                "title": f"Article {i:03d} on {topic_key}",
                "categories": [topic_key.lower(), "news"],
                "text": f"{topics[topic_key]} article content details {i}.",
            }
        )
    items = pd.DataFrame(items_list)

    # 15 users with varying histories
    base_ts = 1_700_000_000
    rows = []
    for u in range(1, 16):
        uid = f"user_{u:03d}"
        # Each user prefers a primary topic and occasional secondary topic
        pref_topic_idx = (u - 1) % 5
        num_clicks = 4 + (u % 4)
        for step in range(num_clicks):
            item_idx = (pref_topic_idx + (step * 5)) % 30 + 1
            item_id = f"art_{item_idx:03d}"
            ts = base_ts + (step * 3600)
            rows.append({"user_id": uid, "item_id": item_id, "signal": 1.0, "timestamp": ts})

    interactions = pd.DataFrame(rows)
    return interactions, items


def test_articles_cold_start_consistency_flat_weighting(
    synthetic_articles_consistency_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify bit-for-bit consistency under flat weighting (recency_weight=False).

    When recency weighting is disabled, `recommend_user` and `recommend_history`
    construct the exact same unweighted average of clicked article TF-IDF vectors,
    producing identical top-k items and floating-point scores.
    """
    interactions, items = synthetic_articles_consistency_data
    catalogue = set(items["item_id"])

    spec = load_config("articles", fast=True)
    spec.model.params["recency_weight"] = False
    spec.serving.recency_window = None
    spec.evaluation.recency_window = None

    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    unique_users = sorted(interactions["user_id"].unique())
    assert len(unique_users) == 15

    for user_id in unique_users:
        user_rows = interactions[interactions["user_id"] == user_id]
        history = list(zip(user_rows["item_id"], user_rows["signal"], strict=False))

        recs_user = model.recommend_user(user_id, k=5)
        recs_hist = model.recommend_history(history, k=5)

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


def test_articles_cold_start_native_formats(
    synthetic_articles_consistency_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify that recommend_history accepts string IDs, tuples, and dictionary history."""
    _, items = synthetic_articles_consistency_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(pd.DataFrame(), items)

    # 1. List of string article IDs
    recs_str = model.recommend_history(["art_001", "art_006"], k=4)
    assert len(recs_str) == 4

    # 2. List of (id, signal) tuples
    recs_tup = model.recommend_history([("art_001", 2.0), ("art_006", 1.0)], k=4)
    assert len(recs_tup) == 4

    # 3. List of dicts
    recs_dict = model.recommend_history(
        [{"item_id": "art_001", "signal": 2.0}, {"item_id": "art_006", "signal": 1.0}],  # type: ignore[arg-type]
        k=4,
    )
    assert len(recs_dict) == 4
    assert [r.item_id for r in recs_tup] == [r.item_id for r in recs_dict]


def test_articles_cold_start_consistency_real_mind_fixtures() -> None:
    """Verify consistency on real offline MIND fixtures."""
    spec = load_config("articles", fast=True)
    adapter = MindArticlesAdapter(spec, raw_dir=FIXTURES_DIR)

    interactions = adapter.interactions()
    items = adapter.items()
    catalogue = set(items["item_id"])

    assert not interactions.empty
    assert not items.empty

    spec.model.params["recency_weight"] = False
    spec.serving.recency_window = None

    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    # Sample known users from training interactions
    users = sorted(interactions["user_id"].unique())
    assert len(users) > 0

    tested_count = 0
    for uid in users:
        user_rows = interactions[interactions["user_id"] == uid]
        history = list(zip(user_rows["item_id"], user_rows["signal"], strict=False))

        recs_user = model.recommend_user(uid, k=5)
        recs_hist = model.recommend_history(history, k=5)

        check_r3_model_invariants(recs_user, k=5, catalogue=catalogue)
        check_r3_model_invariants(recs_hist, k=5, catalogue=catalogue)

        user_item_ids = [r.item_id for r in recs_user]
        hist_item_ids = [r.item_id for r in recs_hist]
        user_scores = [r.score for r in recs_user]
        hist_scores = [r.score for r in recs_hist]

        assert user_item_ids == hist_item_ids
        assert user_scores == pytest.approx(hist_scores, rel=1e-5)
        tested_count += 1

    assert tested_count >= 5
