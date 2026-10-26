"""Discovery Engine - MIND Articles Dataset Adapter (Phase 5, P5.2).

Parses the Microsoft News Dataset (MIND):
- news.tsv (8 columns: id, category, subcategory, title, abstract, url, title_entities, abstract_entities)
  into Items with title, categories=[category, subcategory], abstract as text, URL in extra.
- behaviors.tsv (5 columns: impression_id, user_id, time, history, impressions)
  into canonical Interactions (history clicks before impressions, impression clicks at impression time)
  and preserves candidate lists for impression ranking evaluation.
- Handles missing abstracts, Unicode characters, and empty histories.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from engine.adapters.base import DatasetAdapter
from engine.evaluation.splits import split_interactions
from engine.registry import register_adapter
from engine.schema import ContentTypeSpec, ValidationReport

logger = logging.getLogger("mind_adapter")

TIME_FORMATS = [
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%m/%d/%Y %I:%M %p",
]


def parse_mind_timestamp(time_str: str) -> int:
    """Parse MIND timestamp string to Unix epoch seconds."""
    s = time_str.strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        pass

    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=UTC)
            return int(dt.timestamp())
        except ValueError:
            continue

    # Fallback to pandas
    try:
        ts = pd.to_datetime(s, utc=True)
        return int(ts.timestamp())
    except Exception:
        return 0


def parse_news_line(line: str) -> dict[str, Any] | None:
    """Parse a single raw tab-separated line from news.tsv into item fields.

    Expected 8 columns:
    [news_id, category, subcategory, title, abstract, url, title_entities, abstract_entities]
    """
    if not line or not line.strip():
        return None

    parts = line.rstrip("\r\n").split("\t")
    if not parts or not parts[0].strip():
        return None

    news_id = parts[0].strip()
    category = parts[1].strip() if len(parts) > 1 else "news"
    subcategory = parts[2].strip() if len(parts) > 2 else ""
    title = parts[3].strip() if len(parts) > 3 else news_id
    if not title:
        title = news_id

    abstract = parts[4].strip() if len(parts) > 4 else ""
    url = parts[5].strip() if len(parts) > 5 else None

    # Handle shifted columns where abstract was omitted and url was placed at index 4
    if abstract.startswith("http://") or abstract.startswith("https://"):
        if url is None:
            url = abstract
        abstract = ""

    # Categories list: [category, subcategory] excluding empty strings
    cats = [c for c in [category, subcategory] if c and c.strip()]
    if not cats:
        cats = ["news"]

    # Text content: combination of title and abstract for TF-IDF representations
    text = f"{title} {abstract}".strip() if abstract else title
    subtitle = f"{category} / {subcategory}" if subcategory else category

    return {
        "item_id": news_id,
        "title": title,
        "subtitle": subtitle,
        "categories": cats,
        "text": text,
        "year": None,
        "image_url": None,
        "extra": {
            "url": url,
            "category": category,
            "subcategory": subcategory,
        },
    }


def parse_behavior_line(line: str) -> dict[str, Any] | None:
    """Parse a single raw tab-separated line from behaviors.tsv.

    Expected 5 columns:
    [impression_id, user_id, time, history, impressions]
    """
    if not line or not line.strip():
        return None

    parts = line.rstrip("\r\n").split("\t")
    if len(parts) < 5:
        return None

    imp_id = parts[0].strip()
    user_id = parts[1].strip()
    time_str = parts[2].strip()
    history_str = parts[3].strip()
    impressions_str = parts[4].strip()

    if not user_id:
        return None

    ts = parse_mind_timestamp(time_str)

    # History: space-separated news IDs
    history_ids = [nid for nid in history_str.split(" ") if nid.strip()] if history_str else []

    # Impressions: space-separated cand_id-click pairs
    candidates: list[tuple[str, int]] = []
    if impressions_str:
        for pair in impressions_str.split(" "):
            pair_parts = pair.strip().split("-")
            if len(pair_parts) == 2 and pair_parts[0].strip():
                try:
                    candidates.append((pair_parts[0].strip(), int(pair_parts[1].strip())))
                except ValueError:
                    continue

    return {
        "impression_id": imp_id,
        "user_id": user_id,
        "timestamp": ts,
        "history": history_ids,
        "candidates": candidates,
    }


@register_adapter("mind_articles")
@register_adapter("articles")
@register_adapter("mind")
class MindArticlesAdapter(DatasetAdapter):
    """Dataset adapter for MIND News Articles and Behaviors."""

    def __init__(self, spec: ContentTypeSpec, raw_dir: Path | None = None) -> None:
        super().__init__(spec)
        self.raw_dir = raw_dir or (
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / "mind"
        )
        self._items_df: pd.DataFrame | None = None
        self._interactions_df: pd.DataFrame | None = None
        self.impression_candidates: list[dict[str, Any]] = []
        self.missing_abstracts_count: int = 0
        self.missing_catalogue_items_count: int = 0
        self.empty_history_users_count: int = 0
        self._raw_interactions_count: int = 0

    def download(self, raw_dir: Path) -> None:
        """Download MIND dataset to raw_dir if not present."""
        from scripts.fetch_data import fetch_mind

        variant = self.spec.dataset.variant or "small"
        fetch_mind(raw_dir, variant=variant)

    def _locate_mind_files(self, raw_dir: Path) -> dict[str, list[Path]]:
        """Find news.tsv and behaviors.tsv files under raw_dir."""
        result: dict[str, list[Path]] = {"news": [], "behaviors": []}

        found_news = set(raw_dir.rglob("news*.tsv")) | set(raw_dir.rglob("*news*.tsv"))
        found_behaviors = set(raw_dir.rglob("behaviors*.tsv")) | set(
            raw_dir.rglob("*behaviors*.tsv")
        )

        result["news"] = sorted(p for p in found_news if p.is_file())
        result["behaviors"] = sorted(p for p in found_behaviors if p.is_file())
        return result

    def load_raw(self, raw_dir: Path) -> dict[str, Any]:
        """Load raw lines from news.tsv and behaviors.tsv."""
        files = self._locate_mind_files(raw_dir)
        news_files = files["news"]
        behavior_files = files["behaviors"]

        if not news_files or not behavior_files:
            # Fallback to tests fixture if present
            fixture_dir = (
                Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mind"
            )
            if fixture_dir.exists():
                files = self._locate_mind_files(fixture_dir)
                news_files = files["news"]
                behavior_files = files["behaviors"]

        if not news_files or not behavior_files:
            raise FileNotFoundError(
                f"Could not locate news.tsv and behaviors.tsv in {raw_dir}. "
                "Run 'python backend/scripts/fetch_data.py --type articles --variant fast' first."
            )

        news_lines: list[str] = []
        for nf in news_files:
            with nf.open("r", encoding="utf-8", errors="replace") as f:
                news_lines.extend(f.readlines())

        behavior_lines: list[str] = []
        for bf in behavior_files:
            with bf.open("r", encoding="utf-8", errors="replace") as f:
                behavior_lines.extend(f.readlines())

        return {
            "news_lines": news_lines,
            "behavior_lines": behavior_lines,
        }

    def _prepare_data(self) -> None:
        """Parse raw lines, construct canonical Items and Interactions."""
        if self._items_df is not None and self._interactions_df is not None:
            return

        raw = self.load_raw(self.raw_dir)
        news_lines: list[str] = raw["news_lines"]
        behavior_lines: list[str] = raw["behavior_lines"]

        # 1. Parse news into Items
        item_map: dict[str, dict[str, Any]] = {}
        missing_abstracts = 0

        for line in news_lines:
            item = parse_news_line(line)
            if not item:
                continue
            iid = item["item_id"]
            if not item["text"] or item["text"] == item["title"]:
                missing_abstracts += 1
            if iid not in item_map:
                item_map[iid] = item

        self.missing_abstracts_count = missing_abstracts
        catalogue_set = set(item_map.keys())

        # 2. Parse behaviors into Interactions and impression candidates
        parsed_behaviors: list[dict[str, Any]] = []
        for line in behavior_lines:
            b = parse_behavior_line(line)
            if b:
                parsed_behaviors.append(b)

        self.impression_candidates = parsed_behaviors

        # 3. Create interactions conforming to time protocol (P5.3)
        # Track previous impression timestamp per user to prevent backdating
        user_last_ts: dict[str, int] = {}
        interaction_rows: list[dict[str, Any]] = []
        seen_user_items: dict[str, set[str]] = {}
        missing_cat_items = 0
        empty_hist_users = 0

        # Sort behaviors by timestamp ascending
        sorted_behaviors = sorted(parsed_behaviors, key=lambda x: x["timestamp"])

        for b in sorted_behaviors:
            uid = b["user_id"]
            imp_ts = b["timestamp"]
            prev_ts = user_last_ts.get(uid)
            if uid not in seen_user_items:
                seen_user_items[uid] = set()

            # (A) History interactions (occur before this impression session)
            hist = b["history"]
            if not hist and prev_ts is None:
                empty_hist_users += 1
            elif hist:
                n_hist = len(hist)
                for idx, hid in enumerate(hist):
                    if hid not in catalogue_set:
                        missing_cat_items += 1
                        continue
                    if hid in seen_user_items[uid]:
                        continue
                    seen_user_items[uid].add(hid)

                    # Timestamp assignment (F-003):
                    # If this is the user's first observed session (prev_ts is None),
                    # history occurred before this impression: max(0, imp_ts - 86400 - (n_hist - idx) * 60)
                    # If the user already had an earlier session (prev_ts is not None),
                    # newly observed history occurred BETWEEN prev_ts and imp_ts:
                    if prev_ts is None:
                        hist_ts = max(0, imp_ts - 86400 - (n_hist - idx) * 60)
                    else:
                        dt = max(1, imp_ts - prev_ts)
                        fraction = (idx + 1) / (n_hist + 1)
                        hist_ts = prev_ts + max(1, min(int(dt * fraction), dt - 1))

                    interaction_rows.append(
                        {
                            "user_id": uid,
                            "item_id": hid,
                            "signal": 1.0,
                            "timestamp": hist_ts,
                            "positive": True,
                        }
                    )

            # (B) Impression clicked interactions (occur at impression timestamp)
            for cand_id, clicked in b["candidates"]:
                if clicked == 1:
                    if cand_id not in catalogue_set:
                        missing_cat_items += 1
                        continue
                    if cand_id in seen_user_items[uid]:
                        continue
                    seen_user_items[uid].add(cand_id)
                    interaction_rows.append(
                        {
                            "user_id": uid,
                            "item_id": cand_id,
                            "signal": 1.0,
                            "timestamp": imp_ts,
                            "positive": True,
                        }
                    )

            user_last_ts[uid] = imp_ts

        self.missing_catalogue_items_count = missing_cat_items
        self.empty_history_users_count = empty_hist_users
        self._raw_interactions_count = len(interaction_rows)

        df_inter = pd.DataFrame(interaction_rows)
        if not df_inter.empty:
            # Filter users with fewer than min_user_interactions
            min_u = self.spec.dataset.min_user_interactions
            if min_u > 1:
                u_counts = df_inter["user_id"].value_counts()
                active_u = u_counts[u_counts >= min_u].index
                df_inter = df_inter[df_inter["user_id"].isin(active_u)].reset_index(drop=True)

            # Deduplicate by (user_id, item_id) keeping earliest interaction
            df_inter = (
                df_inter.sort_values(by=["user_id", "timestamp", "item_id"], ascending=True)
                .drop_duplicates(subset=["user_id", "item_id"], keep="first")
                .reset_index(drop=True)
            )

        # Build items DataFrame
        if not df_inter.empty:
            surviving_items = set(df_inter["item_id"].unique())
            items_list = [item_map[iid] for iid in surviving_items if iid in item_map]
        else:
            items_list = list(item_map.values())

        items_df = pd.DataFrame(items_list)
        if items_df.empty:
            items_df = pd.DataFrame(
                columns=[
                    "item_id",
                    "title",
                    "subtitle",
                    "categories",
                    "text",
                    "year",
                    "image_url",
                    "extra",
                ]
            )
        else:
            items_df = items_df.sort_values(by="item_id").reset_index(drop=True)

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
        """Validate datasets against schema, quality constraints, and R1 requirements."""
        inter = self.interactions()
        cat = self.items()

        total_int = len(inter)
        u_count = int(inter["user_id"].nunique()) if not inter.empty else 0
        i_count = int(inter["item_id"].nunique()) if not inter.empty else 0

        denom = u_count * i_count
        sparsity = float(1.0 - (total_int / denom)) if denom > 0 else 0.0

        min_ts = int(inter["timestamp"].min()) if not inter.empty else 0
        max_ts = int(inter["timestamp"].max()) if not inter.empty else 0
        min_date = (
            datetime.fromtimestamp(min_ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            if min_ts > 0
            else ""
        )
        max_date = (
            datetime.fromtimestamp(max_ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            if max_ts > 0
            else ""
        )

        report = ValidationReport(
            total_interactions=total_int,
            unique_users=u_count,
            unique_items=len(cat),
            sparsity=round(sparsity, 6),
            min_timestamp=min_ts,
            max_timestamp=max_ts,
            details={
                "min_date": min_date,
                "max_date": max_date,
                "missing_abstracts_count": self.missing_abstracts_count,
                "missing_catalogue_items_count": self.missing_catalogue_items_count,
                "empty_history_users_count": self.empty_history_users_count,
                "raw_interactions_count": self._raw_interactions_count,
            },
        )
        return report

    def split(
        self,
        interactions: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split interactions into train, validation, and test partitions according to config strategy."""
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
