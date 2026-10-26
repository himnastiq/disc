"""Discovery Engine - Text search indexing and normalization (Phase 7, P7.3)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from api.schemas import SearchItem
from engine.artifacts import as_str_list

_PUNCTUATION_REGEX = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_REGEX = re.compile(r"\s+")
_ARTICLES_REGEX = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Normalize text: NFKD decomposition, lowercase, strip accents and punctuation."""
    if not text:
        return ""
    # 1. NFKD normalization and ASCII transliteration (strip accents)
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_clean = decomposed.encode("ASCII", "ignore").decode("utf-8")

    # 2. Lowercase
    lowered = ascii_clean.lower()

    # 3. Strip punctuation to spaces
    no_punct = _PUNCTUATION_REGEX.sub(" ", lowered)

    # 4. Collapse consecutive whitespace and strip
    return _WHITESPACE_REGEX.sub(" ", no_punct).strip()


def strip_article(text: str) -> str:
    """Strip leading grammatical articles ('the ', 'a ', 'an ')."""
    return _ARTICLES_REGEX.sub("", text).strip()


class ItemSearchIndex:
    """In-memory search index for catalogue items with multi-tier ranking."""

    def __init__(self, items_df: pd.DataFrame, interactions_df: pd.DataFrame | None = None) -> None:
        self._entries: list[dict[str, Any]] = []
        self._items_by_id: dict[str, dict[str, Any]] = {}

        # Compute popularity ranks (1 = highest interaction count)
        pop_ranks: dict[str, int] = {}
        if interactions_df is not None and not interactions_df.empty:
            counts = interactions_df["item_id"].astype(str).value_counts()
            for rank, (item_id, _) in enumerate(counts.items(), start=1):
                pop_ranks[str(item_id)] = rank

        default_rank = len(pop_ranks) + 1000

        for _, row in items_df.iterrows():
            item_id = str(row["item_id"])
            title = str(row.get("title", item_id))
            subtitle = str(row["subtitle"]) if pd.notna(row.get("subtitle")) else None
            categories = as_str_list(row.get("categories"))
            year_val = row.get("year")
            year = int(year_val) if pd.notna(year_val) else None
            img_val = row.get("image_url")
            image_url = str(img_val) if pd.notna(img_val) else None

            norm_title = normalize_text(title)
            norm_no_art = strip_article(norm_title)
            words = set(norm_title.split())

            pop_rank = pop_ranks.get(item_id, default_rank)

            entry = {
                "item_id": item_id,
                "title": title,
                "subtitle": subtitle,
                "categories": categories,
                "year": year,
                "image_url": image_url,
                "popularity_rank": pop_rank,
                "norm_title": norm_title,
                "norm_no_art": norm_no_art,
                "words": words,
            }
            self._entries.append(entry)
            self._items_by_id[item_id] = entry

    def get_entry(self, item_id: str) -> dict[str, Any] | None:
        """Return raw search index entry for item_id, or None if not indexed."""
        return self._items_by_id.get(str(item_id))

    def get_popularity_rank(self, item_id: str) -> int | None:
        """Return precomputed popularity rank for item_id, or None if not indexed."""
        entry = self._items_by_id.get(str(item_id))
        return entry["popularity_rank"] if entry is not None else None

    def search(self, query: str, limit: int = 20) -> tuple[list[SearchItem], int]:
        """Execute normalized search with hierarchical match-type ranking.

        Ranking hierarchy:
          1. Exact match (exact == query or no_article == query_no_art)
          2. Prefix match (starts with query or query_no_art)
          3. Word-start match (any word in title starts with query)
          4. Contains match (query is substring of title)
        Ties are broken by popularity rank (lower number = higher popularity), then item_id.

        Returns:
            Tuple of (ranked_results, total_matches) where total_matches reflects
            the total number of matching items across all tiers prior to limit truncation.
        """
        norm_query = normalize_text(query)
        if not norm_query:
            return [], 0

        query_no_art = strip_article(norm_query)

        exact_matches: list[tuple[int, str, dict[str, Any]]] = []
        prefix_matches: list[tuple[int, str, dict[str, Any]]] = []
        word_start_matches: list[tuple[int, str, dict[str, Any]]] = []
        contains_matches: list[tuple[int, str, dict[str, Any]]] = []

        for entry in self._entries:
            nt = entry["norm_title"]
            nna = entry["norm_no_art"]
            words = entry["words"]
            pop_rank = entry["popularity_rank"]
            item_id = entry["item_id"]

            # Tier 1: Exact match
            if nt == norm_query or (query_no_art and nna == query_no_art):
                exact_matches.append((pop_rank, item_id, entry))
                continue

            # Tier 2: Prefix match
            if nt.startswith(norm_query) or (query_no_art and nna.startswith(query_no_art)):
                prefix_matches.append((pop_rank, item_id, entry))
                continue

            # Tier 3: Word-start match
            if any(w.startswith(norm_query) for w in words) or (
                query_no_art and any(w.startswith(query_no_art) for w in words)
            ):
                word_start_matches.append((pop_rank, item_id, entry))
                continue

            # Tier 4: Contains match
            if norm_query in nt or (query_no_art and query_no_art in nna):
                contains_matches.append((pop_rank, item_id, entry))

        # Sort each tier by popularity rank, then item_id
        exact_matches.sort(key=lambda x: (x[0], x[1]))
        prefix_matches.sort(key=lambda x: (x[0], x[1]))
        word_start_matches.sort(key=lambda x: (x[0], x[1]))
        contains_matches.sort(key=lambda x: (x[0], x[1]))

        results: list[SearchItem] = []

        for _, _, entry in exact_matches:
            if len(results) >= limit:
                break
            results.append(
                SearchItem(
                    item_id=entry["item_id"],
                    title=entry["title"],
                    subtitle=entry["subtitle"],
                    categories=entry["categories"],
                    year=entry["year"],
                    image_url=entry["image_url"],
                    popularity_rank=entry["popularity_rank"],
                    match_type="exact",
                )
            )

        for _, _, entry in prefix_matches:
            if len(results) >= limit:
                break
            results.append(
                SearchItem(
                    item_id=entry["item_id"],
                    title=entry["title"],
                    subtitle=entry["subtitle"],
                    categories=entry["categories"],
                    year=entry["year"],
                    image_url=entry["image_url"],
                    popularity_rank=entry["popularity_rank"],
                    match_type="prefix",
                )
            )

        for _, _, entry in word_start_matches:
            if len(results) >= limit:
                break
            results.append(
                SearchItem(
                    item_id=entry["item_id"],
                    title=entry["title"],
                    subtitle=entry["subtitle"],
                    categories=entry["categories"],
                    year=entry["year"],
                    image_url=entry["image_url"],
                    popularity_rank=entry["popularity_rank"],
                    match_type="word_start",
                )
            )

        for _, _, entry in contains_matches:
            if len(results) >= limit:
                break
            results.append(
                SearchItem(
                    item_id=entry["item_id"],
                    title=entry["title"],
                    subtitle=entry["subtitle"],
                    categories=entry["categories"],
                    year=entry["year"],
                    image_url=entry["image_url"],
                    popularity_rank=entry["popularity_rank"],
                    match_type="contains",
                )
            )

        total_matches = (
            len(exact_matches)
            + len(prefix_matches)
            + len(word_start_matches)
            + len(contains_matches)
        )
        return results, total_matches
