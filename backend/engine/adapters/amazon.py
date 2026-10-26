"""Discovery Engine - Amazon Products dataset adapter (P4.2).

Adapts Amazon 5-core product review datasets (Video Games, Musical Instruments)
to the canonical schema, joining review interactions with item metadata.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

import pandas as pd

from engine.adapters.base import DatasetAdapter
from engine.evaluation.checks import check_r1_data_validity
from engine.evaluation.splits import split_interactions
from engine.registry import register_adapter
from engine.schema import ValidationReport

if TYPE_CHECKING:
    from engine.schema import ContentTypeSpec


def _open_text(path: Path) -> IO[str]:
    """Open a plain text or gzip text file."""
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _parse_dict_line(line: str) -> dict[str, Any] | None:
    """Parse a JSON or Python dict representation line from Amazon data files."""
    line = line.strip()
    if not line:
        return None
    try:
        res = json.loads(line)
        return res if isinstance(res, dict) else None
    except Exception:
        try:
            # Fallback for Stanford SNAP 2014 single-quoted dictionary literals
            import ast

            res = ast.literal_eval(line)
            return res if isinstance(res, dict) else None
        except Exception:
            return None


@register_adapter("amazon_products")
@register_adapter("products")
@register_adapter("amazon")
class AmazonProductsAdapter(DatasetAdapter):
    """Dataset adapter for Amazon Product Reviews (5-core) and metadata."""

    def __init__(self, spec: ContentTypeSpec, raw_dir: Path | None = None) -> None:
        super().__init__(spec)
        self.raw_dir = raw_dir or (
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / "amazon"
        )
        self._items_df: pd.DataFrame | None = None
        self._interactions_df: pd.DataFrame | None = None
        self.missing_metadata_count: int = 0
        self.missing_titles_count: int = 0
        self._raw_interactions_count: int = 0
        self._raw_users_count: int = 0
        self._raw_items_count: int = 0

    def download(self, raw_dir: Path) -> None:
        """Download Amazon product reviews and metadata to raw_dir if not present."""
        from scripts.fetch_data import fetch_amazon

        variant = self.spec.dataset.variant or "instruments"
        fetch_amazon(raw_dir, variant=variant)

    def _find_data_files(self, raw_dir: Path) -> tuple[Path, Path]:
        """Locate reviews and meta files for current variant."""
        variant = (self.spec.dataset.variant or "instruments").lower()
        if variant in ("default", "standard"):
            variant = "video_games"
        elif variant in ("fast", "small"):
            variant = "instruments"

        # Check subfolder first, then raw_dir directly
        candidate_dirs = [raw_dir / variant, raw_dir]
        for cdir in candidate_dirs:
            if not cdir.exists():
                continue
            # Look for review file
            rev_files = list(cdir.glob("reviews_*.json*")) + list(cdir.glob("*reviews*.json*"))
            meta_files = list(cdir.glob("meta_*.json*")) + list(cdir.glob("*meta*.json*"))
            if rev_files and meta_files:
                return rev_files[0], meta_files[0]
            if rev_files and not meta_files:
                # Check parent or other candidate dirs for meta
                for mdir in candidate_dirs:
                    other_metas = list(mdir.glob("meta_*.json*")) + list(mdir.glob("*meta*.json*"))
                    if other_metas:
                        return rev_files[0], other_metas[0]

        raise FileNotFoundError(
            f"Could not locate Amazon review and metadata files in {raw_dir} for variant '{variant}'. "
            f"Run 'python backend/scripts/fetch_data.py --type products --variant {variant}' first."
        )

    def load_raw(self, raw_dir: Path) -> dict[str, Any]:
        """Load raw review records and metadata records from disk."""
        rev_path, meta_path = self._find_data_files(raw_dir)

        # 1. Read metadata
        meta_by_asin: dict[str, dict[str, Any]] = {}
        with _open_text(meta_path) as f:
            for line in f:
                d = _parse_dict_line(line)
                if d and "asin" in d:
                    meta_by_asin[str(d["asin"]).strip()] = d

        # 2. Read reviews
        review_rows: list[dict[str, Any]] = []
        with _open_text(rev_path) as f:
            for line in f:
                d = _parse_dict_line(line)
                if not d:
                    continue
                asin = str(d.get("asin", "")).strip()
                reviewer_id = str(d.get("reviewerID", "")).strip()
                if not asin or not reviewer_id:
                    continue
                rating = float(d.get("overall", d.get("rating", 5.0)))
                ts = int(d.get("unixReviewTime", d.get("timestamp", 0)))
                review_rows.append(
                    {
                        "user_id": reviewer_id,
                        "item_id": asin,
                        "signal": rating,
                        "timestamp": ts,
                    }
                )

        return {"reviews": review_rows, "metadata": meta_by_asin}

    def _prepare_data(self) -> None:
        """Parse raw reviews and metadata, apply join, filtering, and budget capping."""
        if self._items_df is not None and self._interactions_df is not None:
            return

        raw = self.load_raw(self.raw_dir)
        raw_reviews: list[dict[str, Any]] = raw["reviews"]
        meta_by_asin: dict[str, dict[str, Any]] = raw["metadata"]

        self._raw_interactions_count = len(raw_reviews)
        df_rev = pd.DataFrame(raw_reviews)
        self._raw_users_count = int(df_rev["user_id"].nunique()) if not df_rev.empty else 0
        self._raw_items_count = int(df_rev["item_id"].nunique()) if not df_rev.empty else 0

        # Build initial items dictionary from observed interaction ASINs
        item_rows: list[dict[str, Any]] = []
        missing_meta = 0
        missing_titles = 0

        unique_asins = sorted(df_rev["item_id"].unique()) if not df_rev.empty else []
        for asin in unique_asins:
            meta = meta_by_asin.get(asin)
            if meta is None:
                missing_meta += 1
                title = asin
                brand = None
                price = None
                image_url = None
                categories: list[str] = ["General"]
            else:
                raw_title = str(meta.get("title", "")).strip()
                if not raw_title:
                    missing_titles += 1
                    title = asin
                else:
                    title = raw_title

                brand = str(meta.get("brand", "")).strip() or None

                raw_price = meta.get("price")
                try:
                    price = float(raw_price) if raw_price is not None else None
                except (ValueError, TypeError):
                    price = None

                raw_im = str(meta.get("imUrl", meta.get("image_url", ""))).strip()
                image_url = raw_im if raw_im else None

                raw_cats = meta.get("categories", [])
                categories = []
                if isinstance(raw_cats, list):
                    for entry in raw_cats:
                        if isinstance(entry, list):
                            categories.extend([str(c).strip() for c in entry if str(c).strip()])
                        elif isinstance(entry, str) and entry.strip():
                            categories.append(entry.strip())
                if not categories:
                    categories = ["General"]

            subtitle = brand or (categories[0] if categories else None)
            text = f"{title}. Category: {', '.join(categories[:3])}. Brand: {brand or 'Unknown'}."

            item_rows.append(
                {
                    "item_id": asin,
                    "title": title,
                    "subtitle": subtitle,
                    "categories": categories,
                    "text": text,
                    "image_url": image_url,
                    "price": price,
                    "brand": brand,
                }
            )

        self.missing_metadata_count = missing_meta
        self.missing_titles_count = missing_titles
        items_df = pd.DataFrame(item_rows)

        # Apply minimum interaction filtering
        df_inter = df_rev.copy()
        min_user = self.spec.dataset.min_user_interactions
        if min_user > 1 and not df_inter.empty:
            u_counts = df_inter["user_id"].value_counts()
            active_users = u_counts[u_counts >= min_user].index
            df_inter = df_inter[df_inter["user_id"].isin(active_users)]

        min_item = self.spec.dataset.min_item_interactions
        if min_item > 1 and not df_inter.empty:
            i_counts = df_inter["item_id"].value_counts()
            active_items = i_counts[i_counts >= min_item].index
            df_inter = df_inter[df_inter["item_id"].isin(active_items)]

        # Item cap by popularity to respect max_items_in_similarity (P4.2)
        max_items = self.spec.serving.max_items_in_similarity
        if max_items and not df_inter.empty:
            item_counts = df_inter["item_id"].value_counts()
            if len(item_counts) > max_items:
                capped_items = set(item_counts.head(max_items).index)
                df_inter = df_inter[df_inter["item_id"].isin(capped_items)]

        # Filter items_df to only items that survived filtering
        surviving_items = set(df_inter["item_id"].unique()) if not df_inter.empty else set()
        items_df = items_df[items_df["item_id"].isin(surviving_items)].reset_index(drop=True)
        df_inter = df_inter.reset_index(drop=True)

        self._items_df = items_df
        self._interactions_df = df_inter

    def items(self) -> pd.DataFrame:
        """Return canonical catalogue items DataFrame conforming to schema."""
        self._prepare_data()
        assert self._items_df is not None
        return self._items_df

    def interactions(self) -> pd.DataFrame:
        """Return canonical interactions DataFrame conforming to schema."""
        self._prepare_data()
        assert self._interactions_df is not None
        return self._interactions_df

    def validate(self) -> ValidationReport:
        """Produce validation report conforming to R1 invariant."""
        inter_df = self.interactions()
        items_df = self.items()

        base_report = check_r1_data_validity(inter_df, items_df)
        report_data = base_report.model_dump()
        report_data["filtered_users"] = max(0, self._raw_users_count - base_report.unique_users)
        report_data["filtered_items"] = max(0, self._raw_items_count - base_report.unique_items)
        report_data["details"] = {
            "content_type": self.spec.type,
            "variant": self.spec.dataset.variant,
            "min_user_interactions": self.spec.dataset.min_user_interactions,
            "min_item_interactions": self.spec.dataset.min_item_interactions,
            "missing_metadata_count": self.missing_metadata_count,
            "missing_titles_count": self.missing_titles_count,
            "duplicate_interactions_count": int(
                inter_df.duplicated(subset=["user_id", "item_id", "timestamp"]).sum()
            ),
        }
        return ValidationReport.model_validate(report_data)

    def split(
        self,
        interactions: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Perform chronological per-user split."""
        df = interactions if interactions is not None else self.interactions()
        split_ratio = self.spec.split.ratio
        test_ratio = (1.0 - split_ratio) / 2.0
        ratios = (split_ratio, test_ratio, test_ratio)

        return split_interactions(
            df,
            strategy=self.spec.split.strategy,
            ratios=ratios,
            run_leakage_check=True,
        )
