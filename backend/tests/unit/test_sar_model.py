"""Unit tests for SarModel thresholding behavior (FIX-46 / Session 28 citations).

Provides the explicit test functions cited in Session 28:
- test_recommend_history_all_subthreshold_falls_back_to_popularity
- test_recommend_history_ignores_subthreshold_items_as_evidence
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.config import load_config
from engine.models.sar import SarModel


@pytest.fixture(scope="module")
def sar_test_model() -> SarModel:
    """Provide a small fitted SarModel instance for threshold tests."""
    items = pd.DataFrame(
        [
            {"item_id": f"movie_{i}", "title": f"Movie {i}", "categories": ["Action"]}
            for i in range(1, 16)
        ]
    )

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
    spec = load_config("movies", fast=True)
    model = SarModel(spec)
    model.fit(interactions, items)
    return model


def test_recommend_history_all_subthreshold_falls_back_to_popularity(
    sar_test_model: SarModel,
) -> None:
    """FIX-46: History with only low ratings (< positive_threshold) returns popularity mode excluding rated items."""
    thresh = sar_test_model.spec.signal.positive_threshold
    assert thresh == 4.0

    low_history = [("movie_1", 1.0), ("movie_2", 2.0), ("movie_3", 3.0)]
    recs = sar_test_model.recommend_history(low_history, k=5)
    expected_pop = sar_test_model.popular(k=5, exclude_ids={"movie_1", "movie_2", "movie_3"})

    assert [r.item_id for r in recs] == [r.item_id for r in expected_pop]
    assert [r.score for r in recs] == pytest.approx([r.score for r in expected_pop])
    # History items must be excluded from results
    rec_ids = {r.item_id for r in recs}
    assert "movie_1" not in rec_ids
    assert "movie_2" not in rec_ids
    assert "movie_3" not in rec_ids


def test_recommend_history_ignores_subthreshold_items_as_evidence(
    sar_test_model: SarModel,
) -> None:
    """FIX-46: Adding a 1-star item changes nothing except excluding that item from recommendations."""
    # Positive history
    recs_base = sar_test_model.recommend_history([("movie_5", 5.0)], k=10)
    base_ids = [r.item_id for r in recs_base]

    # Case 1: Add a 1-star item that is not in the base recommendation list
    non_rec_item = next(m for m in sar_test_model.catalogue if m != "movie_5" and m not in base_ids)
    recs_with_non_rec = sar_test_model.recommend_history(
        [("movie_5", 5.0), (non_rec_item, 1.0)], k=10
    )
    assert [r.item_id for r in recs_with_non_rec] == base_ids
    assert [r.score for r in recs_with_non_rec] == pytest.approx([r.score for r in recs_base])

    # Case 2: Add a 1-star item that WAS in the base recommendation list
    rec_item_to_dislike = base_ids[0]
    recs_with_dislike = sar_test_model.recommend_history(
        [("movie_5", 5.0), (rec_item_to_dislike, 1.0)], k=10
    )
    assert rec_item_to_dislike not in [r.item_id for r in recs_with_dislike]
