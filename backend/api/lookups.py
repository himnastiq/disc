"""Discovery Engine - Precomputed lookup structures for sub-millisecond serving (FIX-34)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from engine.artifacts import LoadedArtifacts
    from engine.schema import ContentTypeSpec


from engine.artifacts import as_str_list


@dataclass
class TypeLookups:
    """Precomputed in-memory lookup indices for a single content type."""

    content_type: str
    spec: ContentTypeSpec
    artifact_version: str = "1.0.0"
    catalogue_ids: set[str] = field(default_factory=set)
    user_ids: set[str] = field(default_factory=set)
    item_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    user_seen_items: dict[str, set[str]] = field(default_factory=dict)
    user_positive_count: dict[str, int] = field(default_factory=dict)
    user_interactions_count: dict[str, int] = field(default_factory=dict)
    user_topn: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    user_recent_interactions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    user_category_shares: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    user_first_activity: dict[str, int | None] = field(default_factory=dict)
    user_last_activity: dict[str, int | None] = field(default_factory=dict)
    user_persona: dict[str, str | None] = field(default_factory=dict)


def build_type_lookups(spec: ContentTypeSpec, loaded: LoadedArtifacts) -> TypeLookups:
    """Build precomputed lookup indices from loaded artifacts without per-request DataFrame scans."""
    artifact_ver = str(loaded.manifest.get("artifact_schema_version", "1.0.0"))
    lookups = TypeLookups(content_type=spec.type, spec=spec, artifact_version=artifact_ver)

    # 1. Item catalogue and metadata dict
    items_df = loaded.items
    catalogue_ids: set[str] = set()
    item_metadata: dict[str, dict[str, Any]] = {}
    item_categories: dict[str, list[str]] = {}

    for row in items_df.itertuples():
        iid = str(row.item_id)
        catalogue_ids.add(iid)
        cats = as_str_list(getattr(row, "categories", None))
        item_categories[iid] = cats

        sub = getattr(row, "subtitle", None)
        subtitle = str(sub) if pd.notna(sub) else None

        yr = getattr(row, "year", None)
        year = int(yr) if pd.notna(yr) else None

        img = getattr(row, "image_url", None)
        image_url = str(img) if pd.notna(img) else None

        extra_val = getattr(row, "extra", None)
        extra = extra_val if isinstance(extra_val, dict) else {}

        item_metadata[iid] = {
            "title": str(getattr(row, "title", iid)),
            "subtitle": subtitle,
            "categories": cats,
            "year": year,
            "image_url": image_url,
            "extra": extra,
        }

    lookups.catalogue_ids = catalogue_ids
    lookups.item_metadata = item_metadata

    # 2. Users metadata from users.parquet
    user_ids: set[str] = set()
    users_df = loaded.users
    if not users_df.empty:
        for row in users_df.itertuples():
            uid = str(row.user_id)
            user_ids.add(uid)
            p = getattr(row, "persona", None)
            lookups.user_persona[uid] = str(p) if pd.notna(p) else None

            f_ts = getattr(row, "first_timestamp", None)
            lookups.user_first_activity[uid] = int(f_ts) if pd.notna(f_ts) else None

            l_ts = getattr(row, "last_timestamp", None)
            lookups.user_last_activity[uid] = int(l_ts) if pd.notna(l_ts) else None

    # 3. Interactions grouping: precompute seen items, positive counts, recent history, category shares
    inter_df = loaded.interactions
    if not inter_df.empty:
        # Normalize columns once
        user_col = inter_df["user_id"].astype(str)
        item_col = inter_df["item_id"].astype(str)
        has_pos = "positive" in inter_df.columns
        pos_series = (
            inter_df["positive"].astype(bool)
            if has_pos
            else (inter_df["signal"] >= spec.signal.positive_threshold)
        )
        sig_col = (
            inter_df["signal"]
            if "signal" in inter_df.columns
            else pd.Series(1.0, index=inter_df.index)
        )
        ts_col = (
            inter_df["timestamp"]
            if "timestamp" in inter_df.columns
            else pd.Series(0, index=inter_df.index)
        )

        temp_df = pd.DataFrame(
            {
                "user_id": user_col,
                "item_id": item_col,
                "positive": pos_series,
                "signal": sig_col,
                "timestamp": ts_col,
            }
        )

        for uid_val, grp in temp_df.groupby("user_id"):
            uid_str = str(uid_val)
            user_ids.add(uid_str)
            seen = set(grp["item_id"])
            lookups.user_seen_items[uid_str] = seen
            lookups.user_interactions_count[uid_str] = len(grp)
            lookups.user_positive_count[uid_str] = int(grp["positive"].sum())

            if lookups.user_first_activity.get(uid_str) is None:
                min_ts = grp["timestamp"].min()
                lookups.user_first_activity[uid_str] = int(min_ts) if pd.notna(min_ts) else None

            if lookups.user_last_activity.get(uid_str) is None:
                max_ts = grp["timestamp"].max()
                lookups.user_last_activity[uid_str] = int(max_ts) if pd.notna(max_ts) else None

            # Recent interactions: up to 10 sorted by timestamp descending
            sorted_grp = grp.sort_values(by="timestamp", ascending=False).head(10)
            recent_list = []
            for r in sorted_grp.itertuples():
                item_id_str = str(r.item_id)
                meta = item_metadata.get(item_id_str, {})
                sig_raw: Any = getattr(r, "signal", None)
                ts_raw: Any = getattr(r, "timestamp", None)
                recent_list.append(
                    {
                        "item_id": item_id_str,
                        "title": meta.get("title", item_id_str),
                        "signal": float(sig_raw) if pd.notna(sig_raw) else None,
                        "timestamp": int(ts_raw) if pd.notna(ts_raw) else None,
                    }
                )
            lookups.user_recent_interactions[uid_str] = recent_list

            # Category shares
            cat_counts: Counter[str] = Counter()
            for iid_str in grp["item_id"]:
                for c in item_categories.get(iid_str, []):
                    cat_counts[c] += 1
            tot = sum(cat_counts.values())
            shares = []
            if tot > 0:
                for c, cnt in cat_counts.most_common(10):
                    shares.append(
                        {
                            "category": c,
                            "count": cnt,
                            "share": round(cnt / tot, 4),
                        }
                    )
            lookups.user_category_shares[uid_str] = shares

    lookups.user_ids = user_ids

    # 4. Topn rows grouped by user
    if loaded.topn is not None and not loaded.topn.empty:
        topn_df = (
            loaded.topn.sort_values(by="rank") if "rank" in loaded.topn.columns else loaded.topn
        )
        user_topn_map: dict[str, list[tuple[str, float]]] = {}
        topn_user_col = topn_df["user_id"].astype(str)
        topn_item_col = topn_df["item_id"].astype(str)
        topn_score_col = topn_df["score"].astype(float)

        compact_topn = pd.DataFrame(
            {
                "user_id": topn_user_col,
                "item_id": topn_item_col,
                "score": topn_score_col,
            }
        )

        for uid_val, grp in compact_topn.groupby("user_id"):
            uid_str = str(uid_val)
            items_scores = list(zip(grp["item_id"], grp["score"], strict=False))
            user_topn_map[uid_str] = items_scores

        lookups.user_topn = user_topn_map

    return lookups
