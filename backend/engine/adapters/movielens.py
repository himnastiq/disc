"""Discovery Engine - MovieLens dataset adapter (P3.2)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from discovery.datasets.movielens import load_item_df, load_pandas_df
from engine.adapters.base import DatasetAdapter
from engine.evaluation.checks import check_r1_data_validity
from engine.evaluation.splits import split_interactions
from engine.registry import register_adapter
from engine.schema import ValidationReport

if TYPE_CHECKING:
    from engine.schema import ContentTypeSpec


def clean_movie_title(raw_title: str) -> tuple[str, int | None]:
    """Clean a MovieLens movie title string and extract release year.

    Transformations:
        1. Strip trailing release year formatted as (YYYY) or (YYYY-YYYY).
        2. Strip trailing parenthesized alternate titles such as (a.k.a. ...), (L' Postino), etc.
        3. Move trailing grammatical articles (', The', ', A', ', An', ', Il', ', La', etc.) to the front.
        4. Preserve non-ASCII characters and trim whitespace.

    Args:
        raw_title: Raw movie title from MovieLens metadata.

    Returns:
        tuple[str, int | None]: (cleaned_display_title, parsed_year_or_none)
    """
    title = raw_title.strip()
    year: int | None = None

    # 1. Extract trailing year (YYYY)
    year_match = re.search(r"\s*\(\s*(\d{4})\s*\)\s*$", title)
    if year_match:
        try:
            year = int(year_match.group(1))
        except ValueError:
            year = None
        title = title[: year_match.start()].strip()

    # 2. Strip trailing parenthesized alternate titles (may have multiple)
    while True:
        paren_match = re.search(r"\s*\([^)]*\)\s*$", title)
        if paren_match:
            title = title[: paren_match.start()].strip()
        else:
            break

    # 3. Move trailing articles to the front
    article_pattern = re.compile(
        r",\s*(The|A|An|Il|La|Le|Les|Der|Die|Das|El|Los|Las)\s*$",
        re.IGNORECASE,
    )
    article_match = article_pattern.search(title)
    if article_match:
        art = article_match.group(1).strip()
        # Normalise capitalization nicely
        if art.lower() in {"a", "an", "the", "il", "la", "le", "el"}:
            art = art.capitalize()
        base = title[: article_match.start()].strip()
        title = f"{art} {base}"

    return title.strip(), year


@register_adapter("movielens")
@register_adapter("movies")
class MovieLensAdapter(DatasetAdapter):
    """Dataset adapter for MovieLens 100K and 1M datasets."""

    def __init__(self, spec: ContentTypeSpec, raw_dir: Path | None = None) -> None:
        super().__init__(spec)
        self.raw_dir = raw_dir or (
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / "movielens"
        )
        self._items_df: pd.DataFrame | None = None
        self._interactions_df: pd.DataFrame | None = None

    def download(self, raw_dir: Path) -> None:
        """Download and extract MovieLens archive to raw_dir if not present."""
        from scripts.fetch_data import fetch_movielens

        variant = self.spec.dataset.variant or "100k"
        fetch_movielens(raw_dir, variant=variant)

    def load_raw(self, raw_dir: Path) -> dict[str, pd.DataFrame]:
        """Load raw ratings and item metadata dataframes using vendored movielens loader."""
        variant = self.spec.dataset.variant.lower()
        if (
            not (raw_dir / f"ml-{variant}").exists()
            and not (raw_dir / f"ml-{variant}.zip").exists()
        ):
            self.download(raw_dir)

        ratings_raw = load_pandas_df(
            size=variant,
            local_cache_path=str(raw_dir),
            header=["userID", "itemID", "rating", "timestamp"],
        )

        items_raw = load_item_df(
            size=variant,
            local_cache_path=str(raw_dir),
            title_col="title",
            genres_col="genres",
            year_col="year",
        )

        return {"ratings": ratings_raw, "items": items_raw}

    def items(self) -> pd.DataFrame:
        """Return canonical catalogue items DataFrame conforming to schema."""
        if self._items_df is not None:
            return self._items_df

        raw = self.load_raw(self.raw_dir)
        raw_items = raw["items"]

        rows: list[dict[str, Any]] = []
        for _, row in raw_items.iterrows():
            item_id = str(row["itemID"])
            raw_title = str(row.get("title", ""))
            clean_title, parsed_year = clean_movie_title(raw_title)

            # Year fallback if raw title extraction didn't find one but item_df had one
            if parsed_year is None:
                raw_year = row.get("year")
                if pd.notna(raw_year) and str(raw_year).isdigit():
                    parsed_year = int(raw_year)

            # Parse genres into category list
            raw_genres = str(row.get("genres", ""))
            if raw_genres and raw_genres != "nan":
                categories = [
                    g.strip()
                    for g in raw_genres.split("|")
                    if g.strip() and g.strip().lower() not in {"unknown", "none"}
                ]
            else:
                categories = []

            # Subtitle is top categories
            subtitle = " | ".join(categories[:2]) if categories else None

            # Descriptive text summary
            cat_str = ", ".join(categories) if categories else "General"
            year_str = f" ({parsed_year})" if parsed_year else ""
            text = f"{clean_title}{year_str}. Genres: {cat_str}."

            rows.append(
                {
                    "item_id": item_id,
                    "title": clean_title,
                    "subtitle": subtitle,
                    "categories": categories,
                    "text": text,
                    "year": parsed_year,
                    "image_url": None,
                    "extra": {
                        "raw_title": raw_title,
                        "raw_genres": raw_genres,
                    },
                }
            )

        self._items_df = pd.DataFrame(rows)
        return self._items_df

    def interactions(self) -> pd.DataFrame:
        """Return canonical interactions DataFrame conforming to schema with min-interaction filters."""
        if self._interactions_df is not None:
            return self._interactions_df

        raw = self.load_raw(self.raw_dir)
        raw_ratings = raw["ratings"]

        self._raw_interactions_count = len(raw_ratings)
        self._raw_users_count = int(raw_ratings["userID"].nunique())
        self._raw_items_count = int(raw_ratings["itemID"].nunique())

        # Ensure catalogue items are loaded so we only include valid catalogue items
        catalogue = self.items()
        known_item_ids = set(catalogue["item_id"])

        df = pd.DataFrame(
            {
                "user_id": raw_ratings["userID"].astype(str),
                "item_id": raw_ratings["itemID"].astype(str),
                "signal": raw_ratings["rating"].astype(float),
                "timestamp": raw_ratings["timestamp"].astype(int),
            }
        )

        # Drop interactions with unknown items
        df = df[df["item_id"].isin(known_item_ids)]

        # Apply minimum interaction filtering
        min_user = self.spec.dataset.min_user_interactions
        if min_user > 1:
            user_counts = df["user_id"].value_counts()
            active_users = user_counts[user_counts >= min_user].index
            df = df[df["user_id"].isin(active_users)]

        min_item = self.spec.dataset.min_item_interactions
        if min_item > 1:
            item_counts = df["item_id"].value_counts()
            active_items = item_counts[item_counts >= min_item].index
            df = df[df["item_id"].isin(active_items)]

        self._filtered_users_count = max(0, self._raw_users_count - int(df["user_id"].nunique()))
        self._filtered_items_count = max(0, self._raw_items_count - int(df["item_id"].nunique()))

        # Add boolean positive flag
        df["positive"] = df["signal"] >= self.spec.signal.positive_threshold

        self._interactions_df = df.reset_index(drop=True)
        return self._interactions_df

    def validate(self, output_path: Path | None = None) -> ValidationReport:
        """Validate MovieLens dataset against R1 data validity invariants and optionally write report to JSON."""
        import json

        base_report = check_r1_data_validity(
            interactions=self.interactions(),
            items=self.items(),
            positive_threshold=self.spec.signal.positive_threshold,
        )

        filtered_users = getattr(self, "_filtered_users_count", 0)
        filtered_items = getattr(self, "_filtered_items_count", 0)

        report_data = base_report.model_dump()
        report_data["filtered_users"] = filtered_users
        report_data["filtered_items"] = filtered_items
        report_data["details"] = {
            "variant": self.spec.dataset.variant,
            "min_user_interactions": self.spec.dataset.min_user_interactions,
            "min_item_interactions": self.spec.dataset.min_item_interactions,
            "raw_total_interactions": getattr(
                self, "_raw_interactions_count", base_report.total_interactions
            ),
            "raw_unique_users": getattr(self, "_raw_users_count", base_report.unique_users),
            "raw_unique_items": getattr(self, "_raw_items_count", base_report.unique_items),
            "retained_interactions": base_report.total_interactions,
            "retained_users": base_report.unique_users,
            "retained_items": base_report.unique_items,
            "timestamp_range_seconds": (
                (base_report.max_timestamp - base_report.min_timestamp)
                if base_report.max_timestamp is not None and base_report.min_timestamp is not None
                else 0
            ),
        }

        report = ValidationReport.model_validate(report_data)

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")

        return report

    def split(self, interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split interactions using configured strategy and verify R2 leakage invariants."""
        split_ratio = self.spec.split.ratio
        test_ratio = (1.0 - split_ratio) / 2.0
        return split_interactions(
            interactions=interactions,
            strategy=self.spec.split.strategy,
            ratios=(split_ratio, test_ratio, test_ratio),
            run_leakage_check=True,
        )
