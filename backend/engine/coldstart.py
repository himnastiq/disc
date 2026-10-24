"""Discovery Engine - Cold-start history normalization and validation (P2.11)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection


@dataclass
class HistoryNormalizationResult:
    """Outcome of normalizing an arbitrary client-provided cold-start history."""

    normalized_history: list[tuple[str, float]] = field(default_factory=list)
    unknown_item_ids: list[str] = field(default_factory=list)
    duplicate_item_ids: list[str] = field(default_factory=list)
    invalid_signal_items: list[tuple[str, Any]] = field(default_factory=list)
    dropped_overflow_count: int = 0

    @property
    def valid_items(self) -> list[str]:
        return [item_id for item_id, _ in self.normalized_history]


def normalize_history(
    raw_history: list[tuple[Any, ...]] | list[dict[str, Any]] | list[Any],
    catalogue: Collection[str] | None = None,
    max_history_length: int = 50,
    default_signal: float = 1.0,
    min_signal: float = 0.0,
    max_signal: float = 10.0,
) -> HistoryNormalizationResult:
    """Normalize, deduplicate, validate, and cap client cold-start history.

    Rules:
        - Handles empty input gracefully.
        - Coerces IDs to clean strings.
        - Deduplicates repeated items (preserves last occurrence and highest signal).
        - Validates signals (finite floats within bounds; falls back to default_signal).
        - Filters out items not in catalogue (if catalogue provided) and reports them.
        - Caps total history length to max_history_length, dropping oldest overflow.

    Args:
        raw_history: List of (item_id, signal) tuples or dicts {"item_id": ..., "signal": ...}.
        catalogue: Optional set of known catalogue item IDs.
        max_history_length: Maximum allowed items in history (default 50).
        default_signal: Signal weight to use when missing or invalid.
        min_signal: Minimum allowable signal.
        max_signal: Maximum allowable signal.

    Returns:
        HistoryNormalizationResult: Clean history and audit report of dropped/fixed entries.
    """
    result = HistoryNormalizationResult()
    if not raw_history:
        return result

    cat_set = {str(x) for x in catalogue} if catalogue is not None else None

    # Step 1: Parse and validate input pairs
    seen_map: dict[str, float] = {}
    duplicates: list[str] = []
    unknowns: list[str] = []
    invalid_signals: list[tuple[str, Any]] = []

    for entry in raw_history:
        # Extract item_id and raw_signal
        if isinstance(entry, dict):
            raw_id = entry.get("item_id")
            raw_sig = entry.get("signal", default_signal)
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            raw_id, raw_sig = entry[0], entry[1]
        elif isinstance(entry, (list, tuple)) and len(entry) == 1:
            raw_id, raw_sig = entry[0], default_signal
        else:
            continue

        item_id = str(raw_id).strip() if raw_id is not None else ""
        if not item_id:
            continue

        # Parse signal
        try:
            signal_val = float(raw_sig)
            if math.isnan(signal_val) or math.isinf(signal_val):
                invalid_signals.append((item_id, raw_sig))
                signal_val = default_signal
            elif signal_val < min_signal:
                signal_val = min_signal
            elif signal_val > max_signal:
                signal_val = max_signal
        except (ValueError, TypeError):
            invalid_signals.append((item_id, raw_sig))
            signal_val = default_signal

        # Catalogue check
        if cat_set is not None and item_id not in cat_set:
            if item_id not in unknowns:
                unknowns.append(item_id)
            continue

        # Deduplication
        if item_id in seen_map:
            if item_id not in duplicates:
                duplicates.append(item_id)
            # Update to max signal
            seen_map[item_id] = max(seen_map[item_id], signal_val)
        else:
            seen_map[item_id] = signal_val

    # Step 2: Cap history length
    items_list = list(seen_map.items())
    if len(items_list) > max_history_length:
        dropped_count = len(items_list) - max_history_length
        items_list = items_list[-max_history_length:]
    else:
        dropped_count = 0

    result.normalized_history = items_list
    result.unknown_item_ids = unknowns
    result.duplicate_item_ids = duplicates
    result.invalid_signal_items = invalid_signals
    result.dropped_overflow_count = dropped_count

    return result
