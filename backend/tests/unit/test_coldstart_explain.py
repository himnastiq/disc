"""Unit tests for coldstart normalization and explain helpers (P2.11)."""

from engine.coldstart import normalize_history
from engine.explain import find_top_contributor, format_reason


def test_normalize_history_empty() -> None:
    res = normalize_history([])
    assert res.normalized_history == []
    assert res.unknown_item_ids == []
    assert res.duplicate_item_ids == []
    assert res.dropped_overflow_count == 0


def test_normalize_history_valid_and_deduplication() -> None:
    raw = [
        ("item_1", 3.0),
        ("item_2", 4.0),
        {"item_id": "item_1", "signal": 5.0},  # Duplicate item_1 with higher signal
    ]
    res = normalize_history(raw)
    assert len(res.normalized_history) == 2
    assert ("item_1", 5.0) in res.normalized_history
    assert ("item_2", 4.0) in res.normalized_history
    assert res.duplicate_item_ids == ["item_1"]


def test_normalize_history_unknown_items() -> None:
    catalogue = {"item_1", "item_2"}
    raw = [
        ("item_1", 5.0),
        ("item_unknown_xyz", 4.0),
        ("item_unknown_abc", 3.0),
    ]
    res = normalize_history(raw, catalogue=catalogue)
    assert len(res.normalized_history) == 1
    assert res.normalized_history[0] == ("item_1", 5.0)
    assert "item_unknown_xyz" in res.unknown_item_ids
    assert "item_unknown_abc" in res.unknown_item_ids


def test_normalize_history_invalid_signals() -> None:
    raw = [
        ("item_1", "not_a_number"),
        ("item_2", float("nan")),
        ("item_3", float("inf")),
        ("item_4", 15.0),  # Exceeds max_signal=10.0 -> clamped
    ]
    res = normalize_history(raw, default_signal=1.0, max_signal=10.0)
    # item_1, item_2, item_3 fallback to default_signal 1.0
    # item_4 clamped to 10.0
    items_dict = dict(res.normalized_history)
    assert items_dict["item_1"] == 1.0
    assert items_dict["item_2"] == 1.0
    assert items_dict["item_3"] == 1.0
    assert items_dict["item_4"] == 10.0
    assert len(res.invalid_signal_items) == 3


def test_normalize_history_overflow_capping() -> None:
    raw = [(f"item_{i}", 4.0) for i in range(1, 31)]
    res = normalize_history(raw, max_history_length=10)
    assert len(res.normalized_history) == 10
    assert res.dropped_overflow_count == 20
    # Should keep the last 10
    assert res.normalized_history[0][0] == "item_21"
    assert res.normalized_history[-1][0] == "item_30"


def test_find_top_contributor() -> None:
    history = ["h1", "h2", "h3"]
    contributions = {
        "h1": 0.2,
        "h2": 0.8,
        "h4": 1.5,  # Not in history, should be ignored!
    }
    top = find_top_contributor(history, contributions)
    assert top is not None
    best_item, best_score, share = top
    assert best_item == "h2"
    assert best_score == 0.8
    # Total positive contribution in history = 0.2 + 0.8 = 1.0
    # Share = 0.8 / 1.0 = 0.8
    assert share == 0.8


def test_find_top_contributor_empty_or_disjoint() -> None:
    assert find_top_contributor([], {"h1": 1.0}) is None
    assert find_top_contributor(["h1"], {"h2": 1.0}) is None


def test_format_reason() -> None:
    # With title
    r1 = format_reason("i1", item_title="Inception", kind="similar_item")
    assert r1 is not None
    assert r1.item_id == "i1"
    assert r1.text == "Because you liked 'Inception'"

    # Below threshold -> drops reason
    r_drop = format_reason("i1", contribution_share=0.1, min_threshold=0.2)
    assert r_drop is None

    # Above threshold -> preserves reason
    r_keep = format_reason("i1", contribution_share=0.3, min_threshold=0.2)
    assert r_keep is not None

    # Global popularity reason
    r_pop = format_reason(item_id=None, kind="popularity")
    assert r_pop is not None
    assert r_pop.item_id is None
    assert "Popular" in r_pop.text
