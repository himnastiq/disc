"""Discovery Engine - Serving lookups precomputation for sub-20s startup (FIX-57).

Precomputes per-user serving lookup tables at training time so that the API server
does not perform expensive groupby operations over millions of interaction rows
during startup.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.artifacts import as_str_list

if TYPE_CHECKING:
    from engine.schema import ContentTypeSpec


def compute_serving_lookups(
    spec: ContentTypeSpec,
    items: pd.DataFrame,
    interactions: pd.DataFrame,
    users_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Precompute per-user lookup table for fast API startup.

    Columns produced:
    - user_id: string ID
    - seen_items: list[str] of items interacted with (unique, ordered)
    - positive_count: int count of positive interactions (signal >= positive_threshold)
    - interaction_count: int total interaction count
    - first_timestamp: int | None timestamp of first activity
    - last_timestamp: int | None timestamp of most recent activity
    - persona: str | None persona classification
    - recent_interactions: str (JSON array of up to 10 most recent items)
    - category_shares: str (JSON array of top 10 category share dicts)
    """
    if interactions.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "seen_items",
                "positive_count",
                "interaction_count",
                "first_timestamp",
                "last_timestamp",
                "persona",
                "recent_interactions",
                "category_shares",
            ]
        )

    # 1. Item catalogue metadata & categories map
    item_titles: dict[str, str] = {}
    item_cats: dict[str, list[str]] = {}
    if not items.empty:
        for r in items.itertuples():
            iid = str(r.item_id)
            item_titles[iid] = str(getattr(r, "title", iid))
            item_cats[iid] = as_str_list(getattr(r, "categories", None))

    # 2. Extract arrays from interactions in natural row order
    pos_thresh = float(getattr(getattr(spec, "signal", None), "positive_threshold", 1.0))
    has_pos = "positive" in interactions.columns
    has_sig = "signal" in interactions.columns
    has_ts = "timestamp" in interactions.columns

    u_col = interactions["user_id"].astype(str).values
    i_col = interactions["item_id"].astype(str).values
    sig_col = interactions["signal"].values if has_sig else None
    ts_col = interactions["timestamp"].values if has_ts else None
    pos_col = (
        interactions["positive"].values
        if has_pos
        else ((interactions["signal"] >= pos_thresh).values if has_sig else None)
    )

    user_seen: dict[str, list[str]] = defaultdict(list)
    user_pos: dict[str, int] = defaultdict(int)
    user_recent_raw: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    user_cats: dict[str, Counter[str]] = defaultdict(Counter)
    user_first_ts: dict[str, int] = {}
    user_last_ts: dict[str, int] = {}

    n = len(interactions)
    for idx in range(n):
        u = str(u_col[idx])
        i = str(i_col[idx])
        user_seen[u].append(i)

        if pos_col is not None and bool(pos_col[idx]):
            user_pos[u] += 1

        cur_ts = int(ts_col[idx]) if (ts_col is not None and pd.notna(ts_col[idx])) else 0
        sig_val = float(sig_col[idx]) if (sig_col is not None and pd.notna(sig_col[idx])) else None
        ts_val = int(ts_col[idx]) if (ts_col is not None and pd.notna(ts_col[idx])) else None

        user_recent_raw[u].append(
            (
                cur_ts,
                {
                    "item_id": i,
                    "title": item_titles.get(i, i),
                    "signal": sig_val,
                    "timestamp": ts_val,
                },
            )
        )

        if ts_col is not None and pd.notna(ts_col[idx]):
            if u not in user_first_ts or cur_ts < user_first_ts[u]:
                user_first_ts[u] = cur_ts
            if u not in user_last_ts or cur_ts > user_last_ts[u]:
                user_last_ts[u] = cur_ts

        cats = item_cats.get(i)
        if cats:
            occ_counter = user_cats[u]
            for c in cats:
                occ_counter[c] += 1

    # 3. Pull user personas and metadata from users_df if available
    user_personas: dict[str, str] = {}
    if users_df is not None and not users_df.empty:
        for r in users_df.itertuples():
            uid = str(r.user_id)
            p = getattr(r, "persona", None)
            if pd.notna(p):
                user_personas[uid] = str(p)
            f_ts = getattr(r, "first_timestamp", None)
            if pd.notna(f_ts) and uid not in user_first_ts:
                user_first_ts[uid] = int(f_ts)
            l_ts = getattr(r, "last_timestamp", None)
            if pd.notna(l_ts) and uid not in user_last_ts:
                user_last_ts[uid] = int(l_ts)

    all_uids: list[str] = list(user_seen.keys())
    if users_df is not None and not users_df.empty:
        existing = set(all_uids)
        for uid in users_df["user_id"].astype(str):
            if uid not in existing:
                all_uids.append(uid)
                existing.add(uid)

    rows: list[dict[str, Any]] = []
    for u in all_uids:
        raw_seen = user_seen.get(u, [])
        # Unique seen items preserving first-interaction order
        seen_unique = list(dict.fromkeys(raw_seen))
        pos_cnt = user_pos.get(u, 0)
        cnt = len(raw_seen)
        f_ts = user_first_ts.get(u)
        l_ts = user_last_ts.get(u)
        p = user_personas.get(u)
        raw_rec = user_recent_raw.get(u, [])
        sorted_rec = sorted(raw_rec, key=lambda x: x[0], reverse=True)[:10]
        rec = [x[1] for x in sorted_rec]

        c_counter: Counter[str] | None = user_cats.get(u)
        shares: list[dict[str, Any]] = []
        if c_counter:
            tot = sum(c_counter.values())
            if tot > 0:
                for c, count in c_counter.most_common(10):
                    shares.append(
                        {
                            "category": c,
                            "count": count,
                            "share": round(count / tot, 4),
                        }
                    )

        rows.append(
            {
                "user_id": u,
                "seen_items": seen_unique,
                "positive_count": pos_cnt,
                "interaction_count": cnt,
                "first_timestamp": f_ts,
                "last_timestamp": l_ts,
                "persona": p,
                "recent_interactions": json.dumps(rec),
                "category_shares": json.dumps(shares),
            }
        )

    return pd.DataFrame(rows)
