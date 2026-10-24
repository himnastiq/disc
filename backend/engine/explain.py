"""Discovery Engine - Faithful explanation helpers (P2.11 / R3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.schema import Reason

if TYPE_CHECKING:
    from collections.abc import Collection


def find_top_contributor(
    history_item_ids: Collection[str],
    contributions: dict[str, float],
) -> tuple[str, float, float] | None:
    """Identify the history item with highest contribution to a recommendation score.

    Computes:
        best_item = argmax_{h in H} contributions[h]
        share = best_score / sum_{h in H} max(0, contributions[h])

    Args:
        history_item_ids: User's interaction history item IDs.
        contributions: Map of history_item_id -> affinity/similarity score.

    Returns:
        tuple[str, float, float] | None: (best_item_id, best_score, share_of_total),
                                        or None if history or contributions are empty.
    """
    hist_set = {str(x) for x in history_item_ids}
    relevant = {k: float(v) for k, v in contributions.items() if str(k) in hist_set and v > 0.0}

    if not relevant:
        return None

    best_item = max(relevant.keys(), key=lambda k: relevant[k])
    best_score = relevant[best_item]

    total_positive = sum(relevant.values())
    share = (best_score / total_positive) if total_positive > 0.0 else 0.0

    return best_item, best_score, share


def format_reason(
    item_id: str | None,
    item_title: str | None = None,
    kind: str = "similar_item",
    contribution_share: float | None = None,
    min_threshold: float = 0.2,
) -> Reason | None:
    """Format a faithful Reason object for API presentation.

    If contribution_share is provided and falls below min_threshold, returns None
    to avoid presenting noisy, low-confidence explanations.

    Args:
        item_id: Contributing history item ID (or None if global popularity).
        item_title: Clean title of the history item (if available in catalogue).
        kind: Reason classification (e.g. 'similar_item', 'genre_match', 'co_occurrence').
        contribution_share: Fraction of score attributable to this item [0.0, 1.0].
        min_threshold: Minimum share required to show a reason (default 0.2 = 20%).

    Returns:
        Reason | None: Validated Reason instance or None.
    """
    if contribution_share is not None and contribution_share < min_threshold:
        return None

    if item_title:
        text = f"Because you liked '{item_title}'"
    elif item_id:
        text = f"Because you liked item {item_id}"
    else:
        text = "Popular across the platform"

    return Reason(
        kind=kind,
        item_id=str(item_id) if item_id is not None else None,
        text=text,
    )
