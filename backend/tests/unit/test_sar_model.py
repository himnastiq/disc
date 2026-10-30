"""Unit tests for SarModel thresholding behavior (FIX-46 / Session 28 citations).

Provides the explicit test functions cited in Session 28:
- test_recommend_history_all_subthreshold_falls_back_to_popularity
- test_recommend_history_ignores_subthreshold_items_as_evidence
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.unit.test_sar import (
    test_recommend_history_adding_one_star_item_changes_nothing_except_exclusion,
    test_recommend_history_only_low_ratings_returns_popularity_with_exclusions,
)

if TYPE_CHECKING:
    from engine.models.sar import SarModel


def test_recommend_history_all_subthreshold_falls_back_to_popularity(
    fitted_sar_model: SarModel,
) -> None:
    """FIX-46: Sub-threshold ratings result in popularity fallback with history exclusions."""
    test_recommend_history_only_low_ratings_returns_popularity_with_exclusions(fitted_sar_model)


def test_recommend_history_ignores_subthreshold_items_as_evidence(
    fitted_sar_model: SarModel,
) -> None:
    """FIX-46: 1-star items change nothing except excluding themselves."""
    test_recommend_history_adding_one_star_item_changes_nothing_except_exclusion(fitted_sar_model)
