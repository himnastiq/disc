"""Unit tests for MindArticlesAdapter (Phase 5, P5.2).

Tests news and behavior line parsing, unicode handling, missing abstracts,
empty histories, missing catalogue article dropping, and validation reporting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.adapters.mind import (
    MindArticlesAdapter,
    parse_behavior_line,
    parse_mind_timestamp,
    parse_news_line,
)
from engine.config import load_config
from engine.schema import Interaction, Item


@pytest.fixture(scope="module")
def articles_spec():
    """Load fast articles config for testing."""
    return load_config("articles", fast=True)


def test_parse_mind_timestamp() -> None:
    """Verify timestamp parsing for standard MIND date string formats."""
    ts1 = parse_mind_timestamp("11/11/2019 9:05:58 AM")
    assert ts1 > 1_500_000_000

    ts2 = parse_mind_timestamp("11/14/2019 11:30:00 AM")
    assert ts2 > ts1

    # Empty or invalid string returns 0
    assert parse_mind_timestamp("") == 0
    assert parse_mind_timestamp("invalid-date") == 0


def test_parse_news_line_normal() -> None:
    """Verify parsing a full standard news.tsv line."""
    line = (
        "N12345\tnews\tnewsworld\tHistoric Climate Accord Reached\t"
        "World leaders agreed to reduce emissions globally.\thttps://msn.com/world\t[]\t[]"
    )
    parsed = parse_news_line(line)
    assert parsed is not None
    assert parsed["item_id"] == "N12345"
    assert parsed["title"] == "Historic Climate Accord Reached"
    assert parsed["subtitle"] == "news / newsworld"
    assert parsed["categories"] == ["news", "newsworld"]
    assert "reduce emissions globally" in parsed["text"]
    assert parsed["extra"]["url"] == "https://msn.com/world"

    # Schema validity
    item = Item(**parsed)
    assert item.item_id == "N12345"


def test_parse_news_line_missing_abstract() -> None:
    """Verify handling when abstract is missing or line has truncated columns."""
    line = "N9999\tsports\tfootball\tChampionship Victory Celebrated\t\thttps://msn.com/sports"
    parsed = parse_news_line(line)
    assert parsed is not None
    assert parsed["item_id"] == "N9999"
    assert parsed["title"] == "Championship Victory Celebrated"
    assert parsed["text"] == "Championship Victory Celebrated"  # Title alone
    assert parsed["categories"] == ["sports", "football"]


def test_parse_news_line_unicode_characters() -> None:
    """Verify Unicode characters in titles and abstracts are preserved cleanly."""
    line = (
        "N5555\tlifestyle\tfood\tRenée's Gourmet Café & Chloë's ☕\t"
        "Délicieux croissants and café au lait in Montréal.\thttps://msn.com/cafe\t[]\t[]"
    )
    parsed = parse_news_line(line)
    assert parsed is not None
    assert "Renée" in parsed["title"]
    assert "Café" in parsed["title"]
    assert "☕" in parsed["title"]
    assert "Délicieux" in parsed["text"]

    item = Item(**parsed)
    assert "Renée" in item.title


def test_parse_news_line_empty_title_fallback() -> None:
    """Verify title falls back to item_id if empty."""
    line = "N7777\tfinance\tmarkets\t\tStock market summary\thttps://msn.com/finance"
    parsed = parse_news_line(line)
    assert parsed is not None
    assert parsed["title"] == "N7777"


def test_parse_behavior_line_normal() -> None:
    """Verify standard behavior line parsing into history and candidate clicks."""
    line = "10\tU1234\t11/11/2019 9:05:58 AM\tN10 N20 N30\tN40-1 N50-0 N60-0"
    b = parse_behavior_line(line)
    assert b is not None
    assert b["impression_id"] == "10"
    assert b["user_id"] == "U1234"
    assert b["timestamp"] > 0
    assert b["history"] == ["N10", "N20", "N30"]
    assert b["candidates"] == [("N40", 1), ("N50", 0), ("N60", 0)]


def test_parse_behavior_line_empty_history() -> None:
    """Verify user with empty history produces empty history list without crashing."""
    line = "11\tU5678\t11/12/2019 10:00:00 AM\t\tN10-1 N20-0"
    b = parse_behavior_line(line)
    assert b is not None
    assert b["user_id"] == "U5678"
    assert b["history"] == []
    assert b["candidates"] == [("N10", 1), ("N20", 0)]


def test_mind_adapter_full_pipeline_on_fixtures(articles_spec) -> None:
    """Verify MindArticlesAdapter extracts conforming Items, Interactions, and ValidationReport."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures" / "mind"
    adapter = MindArticlesAdapter(articles_spec, raw_dir=fixture_dir)

    items = adapter.items()
    interactions = adapter.interactions()
    report = adapter.validate()

    assert not items.empty
    assert not interactions.empty
    assert report.total_interactions > 0
    assert report.unique_users > 0
    assert report.unique_items > 0
    assert 0.0 <= report.sparsity <= 1.0

    # Verify item rows satisfy engine Item schema
    for _, row in items.iterrows():
        item_obj = Item(**row.to_dict())
        assert item_obj.item_id
        assert item_obj.title
        assert isinstance(item_obj.categories, list)

    # Verify interaction rows satisfy engine Interaction schema
    for _, row in interactions.iterrows():
        inter_obj = Interaction(**row.to_dict())
        assert inter_obj.user_id
        assert inter_obj.item_id in set(items["item_id"])
        assert inter_obj.positive is True
        assert inter_obj.timestamp >= 0


def test_missing_catalogue_items_dropped_and_counted(articles_spec) -> None:
    """Verify articles in user history missing from catalogue are dropped and counted."""
    adapter = MindArticlesAdapter(articles_spec)

    # Mock raw data where history references N_UNKNOWN which does not exist in news
    mock_news = [
        "N1\tnews\tworld\tKnown News Article 1\tSummary text\thttps://msn.com\t[]\t[]\n",
        "N2\tnews\tworld\tKnown News Article 2\tSummary text\thttps://msn.com\t[]\t[]\n",
    ]
    mock_behaviors = [
        "1\tU1\t11/11/2019 9:00:00 AM\tN1 N_UNKNOWN\tN2-1\n",
        "2\tU1\t11/11/2019 10:00:00 AM\tN1\tN2-1\n",
        "3\tU1\t11/11/2019 11:00:00 AM\tN1\tN2-1\n",
    ]

    adapter.load_raw = lambda _: {"news_lines": mock_news, "behavior_lines": mock_behaviors}  # type: ignore[assignment]
    interactions = adapter.interactions()

    # N_UNKNOWN must not appear in interactions
    assert "N_UNKNOWN" not in set(interactions["item_id"])
    assert adapter.missing_catalogue_items_count >= 1
