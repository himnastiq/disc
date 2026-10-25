"""Discovery Engine - News Articles Robustness Tests (Phase 5, P5.10).

Covers edge cases and defensive invariants specific to news articles:
1. Very short titles (single character, whitespace, punctuation only, fallback to id).
2. Missing abstracts (fewer columns, empty strings, clean fallback to title, count in report).
3. Non-English characters (accents, umlauts, Cyrillic, CJK scripts, Arabic, emojis, NFC).
4. Duplicated articles (duplicate IDs or titles deduplicated cleanly without index collision).
5. History articles missing from catalogue (dropped and counted in data report, safe cold start).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from engine.adapters.mind import (
    MindArticlesAdapter,
    parse_news_line,
)
from engine.config import load_config
from engine.models.tfidf import TfidfProfileModel, clean_article_text


def test_robustness_very_short_titles_and_punctuation() -> None:
    """Verify handling of extremely short titles, punctuation, and empty titles."""
    # 1. Parsing single character and empty titles
    line_single = "N1\tnews\tworld\tX\tAbstract here\thttp://url\t\t"
    item_single = parse_news_line(line_single)
    assert item_single is not None
    assert item_single["title"] == "X"

    # Line with empty title should fall back to item_id
    line_empty_title = "N2\tnews\tworld\t\tAbstract here\thttp://url\t\t"
    item_empty = parse_news_line(line_empty_title)
    assert item_empty is not None
    assert item_empty["title"] == "N2"

    # Line with punctuation-only title
    line_punct = "N3\tnews\tworld\t?!...\tAbstract here\thttp://url\t\t"
    item_punct = parse_news_line(line_punct)
    assert item_punct is not None
    assert item_punct["title"] == "?!..."

    # 2. Text cleaning on short and punctuation-only inputs
    cleaned_punct = clean_article_text("?!...")
    # Cleaned punctuation may be empty or spaces
    assert isinstance(cleaned_punct, str)

    # 3. Model training with short title items
    spec = load_config("articles", fast=True)
    items_df = pd.DataFrame(
        [
            {"item_id": "N1", "title": "A", "categories": ["news"], "text": "A"},
            {"item_id": "N2", "title": "B", "categories": ["news"], "text": "B"},
            {"item_id": "N3", "title": "N3", "categories": ["news"], "text": "N3"},
        ]
    )
    interactions_df = pd.DataFrame(
        [
            {"user_id": "U1", "item_id": "N1", "signal": 1.0, "timestamp": 100},
            {"user_id": "U1", "item_id": "N2", "signal": 1.0, "timestamp": 200},
            {"user_id": "U2", "item_id": "N3", "signal": 1.0, "timestamp": 200},
        ]
    )

    model = TfidfProfileModel(spec)
    model.fit(interactions_df, items_df)
    recs = model.recommend_user("U1", k=2)
    assert len(recs) > 0
    assert all(r.item_id in {"N1", "N2", "N3"} for r in recs)

    recs_cold = model.recommend_history([("N1", 1.0)], k=2)
    assert len(recs_cold) > 0
    assert all(r.item_id in {"N1", "N2", "N3"} for r in recs_cold)


def test_robustness_missing_abstracts() -> None:
    """Verify handling of missing abstracts and counting in data report."""
    # 1. Parsing lines with missing abstracts
    line_no_abstract_col = "N10\ttech\tgadgets\tSmartphone Released"
    item_no_abs = parse_news_line(line_no_abstract_col)
    assert item_no_abs is not None
    assert item_no_abs["title"] == "Smartphone Released"
    assert item_no_abs["text"] == "Smartphone Released"

    line_empty_abstract = "N11\ttech\tgadgets\tTablet Launch\t\thttp://url\t\t"
    item_empty_abs = parse_news_line(line_empty_abstract)
    assert item_empty_abs is not None
    assert item_empty_abs["title"] == "Tablet Launch"
    assert item_empty_abs["text"] == "Tablet Launch"

    # 2. Verify adapter counting missing abstracts
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        news_file = raw_dir / "news.tsv"
        behaviors_file = raw_dir / "behaviors.tsv"

        # 2 items missing abstracts, 1 with abstract
        news_file.write_text(
            "N1\ttech\tmobile\tPhone 1\t\thttp://url\t\t\n"
            "N2\ttech\tmobile\tPhone 2\thttp://url\n"
            "N3\ttech\tmobile\tPhone 3\tFull abstract about phone\thttp://url\t\t\n",
            encoding="utf-8",
        )
        behaviors_file.write_text(
            "1\tU1\t11/11/2019 10:00:00 AM\tN1\tN2-1 N3-0\n",
            encoding="utf-8",
        )

        spec = load_config("articles", fast=True)
        adapter = MindArticlesAdapter(spec, raw_dir=raw_dir)
        report = adapter.validate()

        assert adapter.missing_abstracts_count >= 2
        assert "missing_abstracts_count" in report.details
        assert report.details["missing_abstracts_count"] >= 2


def test_robustness_non_english_characters() -> None:
    """Verify handling of Unicode, accents, Cyrillic, CJK, and emojis."""
    multilingual_text = "Élysée & Über-cool: Новости дня! 東京オリンピック 2020 🚀📰 — أخبار عاجلة"
    cleaned = clean_article_text(multilingual_text)

    # Must preserve Unicode characters in NFC form
    assert "elysee" in cleaned or "élysee" in cleaned or "Élysée".lower() in cleaned
    assert "новости" in cleaned
    assert "東京オリンピック" in cleaned

    # Verify TF-IDF model fitting on multilingual items
    spec = load_config("articles", fast=True)
    items_df = pd.DataFrame(
        [
            {
                "item_id": "N_FR",
                "title": "Champs-Élysées Découverte",
                "categories": ["voyage"],
                "text": "Champs-Élysées Découverte dans le cœur de Paris.",
            },
            {
                "item_id": "N_JP",
                "title": "東京オリンピック大会",
                "categories": ["スポーツ"],
                "text": "東京オリンピック大会の最新ハイライトニュース。",
            },
            {
                "item_id": "N_RU",
                "title": "Новости космической станции",
                "categories": ["наука"],
                "text": "Новости космической станции и исследование космоса.",
            },
        ]
    )
    interactions_df = pd.DataFrame(
        [
            {"user_id": "U_MULTI", "item_id": "N_JP", "signal": 1.0, "timestamp": 100},
            {"user_id": "U_MULTI", "item_id": "N_FR", "signal": 1.0, "timestamp": 200},
            {"user_id": "U_OTHER", "item_id": "N_RU", "signal": 1.0, "timestamp": 200},
        ]
    )

    model = TfidfProfileModel(spec)
    model.fit(interactions_df, items_df)

    # Recommends multilingual items without encoding or index errors
    recs = model.recommend_user("U_MULTI", k=3)
    assert len(recs) > 0
    assert recs[0].item_id in {"N_FR", "N_JP", "N_RU"}

    recs_cold = model.recommend_history([("N_JP", 1.0)], k=2)
    assert len(recs_cold) > 0
    assert all(r.item_id in {"N_FR", "N_JP", "N_RU"} for r in recs_cold)


def test_robustness_duplicated_articles() -> None:
    """Verify deduplication when news.tsv contains duplicate article IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        news_file = raw_dir / "news.tsv"
        behaviors_file = raw_dir / "behaviors.tsv"

        # N1 appears twice with different titles
        news_file.write_text(
            "N1\tnews\tworld\tOriginal Title\tAbstract 1\thttp://url\t\t\n"
            "N1\tnews\tworld\tUpdated Title\tAbstract 1 Updated\thttp://url\t\t\n"
            "N2\tnews\tworld\tUnique Title\tAbstract 2\thttp://url\t\t\n",
            encoding="utf-8",
        )
        behaviors_file.write_text(
            "1\tU1\t11/11/2019 10:00:00 AM\tN1\tN2-1\n"
            "2\tU1\t11/11/2019 11:00:00 AM\tN1\tN2-1\n",  # Duplicate interaction
            encoding="utf-8",
        )

        spec = load_config("articles", fast=True)
        adapter = MindArticlesAdapter(spec, raw_dir=raw_dir)
        items_df = adapter.items()
        inter_df = adapter.interactions()

        # Item IDs must be strictly unique
        assert items_df["item_id"].is_unique
        assert len(items_df) == 2

        # User-item interactions must be deduplicated
        assert len(inter_df.drop_duplicates(subset=["user_id", "item_id"])) == len(inter_df)


def test_robustness_history_articles_missing_from_catalogue() -> None:
    """Verify that articles in user history missing from catalogue are dropped and counted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        news_file = raw_dir / "news.tsv"
        behaviors_file = raw_dir / "behaviors.tsv"

        # Only N1 and N2 are in catalogue
        news_file.write_text(
            "N1\tnews\tworld\tTitle 1\tAbstract 1\thttp://url\t\t\n"
            "N2\tnews\tworld\tTitle 2\tAbstract 2\thttp://url\t\t\n",
            encoding="utf-8",
        )
        # History contains N_GHOST_1 and N_GHOST_2 which are missing from news.tsv
        behaviors_file.write_text(
            "1\tU1\t11/11/2019 10:00:00 AM\tN1 N_GHOST_1 N_GHOST_2\tN2-1\n",
            encoding="utf-8",
        )

        spec = load_config("articles", fast=True)
        adapter = MindArticlesAdapter(spec, raw_dir=raw_dir)
        report = adapter.validate()
        inter_df = adapter.interactions()

        # Missing catalogue items counted
        assert adapter.missing_catalogue_items_count == 2
        assert report.details["missing_catalogue_items_count"] == 2

        # Ghost items must not appear in interactions
        assert "N_GHOST_1" not in inter_df["item_id"].values
        assert "N_GHOST_2" not in inter_df["item_id"].values

        # Cold-start recommendations with missing history items
        model = TfidfProfileModel(spec)
        model.fit(inter_df, adapter.items())

        # History with only unknown items falls back to popular without error
        recs_all_unknown = model.recommend_history([("N_GHOST_999", 1.0)], k=2)
        assert len(recs_all_unknown) > 0
        assert all(r.item_id in {"N1", "N2"} for r in recs_all_unknown)

        # History with mix of known and unknown items scores known cleanly
        recs_mixed = model.recommend_history([("N1", 1.0), ("N_GHOST_888", 1.0)], k=2)
        assert len(recs_mixed) > 0
        assert all(r.item_id in {"N1", "N2"} for r in recs_mixed)
