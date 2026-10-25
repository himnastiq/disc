"""Discovery Engine - User profile endpoint (Phase 7, P7.4)."""

from __future__ import annotations

from collections import Counter

import pandas as pd
from fastapi import APIRouter, Path, Query, Request

from api.deps import resolve_loaded_artifacts
from api.schemas import CategoryShare, RecentInteraction, UserProfileResponse
from engine.config import load_config
from engine.errors import UnknownUser

router = APIRouter(prefix="/v1", tags=["users"])


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    request: Request,
    user_id: str = Path(..., description="User unique identifier", max_length=100),
    type: str = Query(..., description="Content type identifier", max_length=50),
) -> UserProfileResponse:
    """Retrieve user taste profile: interaction counts, category preferences, and recent history."""
    loaded = resolve_loaded_artifacts(request, type)

    # 1. Verify user exists in dataset
    uid_str = str(user_id)
    user_matches = loaded.users[loaded.users["user_id"].astype(str) == uid_str]
    interactions_matches = loaded.interactions[
        loaded.interactions["user_id"].astype(str) == uid_str
    ]

    if user_matches.empty and interactions_matches.empty:
        raise UnknownUser(user_id=uid_str, content_type=type)

    user_row = user_matches.iloc[0] if not user_matches.empty else None
    persona = (
        str(user_row["persona"])
        if user_row is not None and pd.notna(user_row.get("persona"))
        else None
    )

    # 2. Compute interaction and positive counts
    interaction_count = len(interactions_matches)
    spec = load_config(type, fast=True)
    if "positive" in interactions_matches.columns:
        positive_count = int(interactions_matches["positive"].sum())
    else:
        threshold = spec.signal.positive_threshold
        positive_count = int((interactions_matches["signal"] >= threshold).sum())

    # 3. Timestamps
    first_activity: int | str | None = None
    last_activity: int | str | None = None

    if user_row is not None and pd.notna(user_row.get("first_timestamp")):
        first_activity = int(user_row["first_timestamp"])
    elif not interactions_matches.empty and pd.notna(interactions_matches["timestamp"].min()):
        first_activity = int(interactions_matches["timestamp"].min())

    if user_row is not None and pd.notna(user_row.get("last_timestamp")):
        last_activity = int(user_row["last_timestamp"])
    elif not interactions_matches.empty and pd.notna(interactions_matches["timestamp"].max()):
        last_activity = int(interactions_matches["timestamp"].max())

    # 4. Recent items (last 10 with titles and timestamps)
    recent_interactions: list[RecentInteraction] = []
    if not interactions_matches.empty:
        # Sort by timestamp descending; fallback to index order if missing
        if "timestamp" in interactions_matches.columns:
            sorted_interactions = interactions_matches.sort_values(
                by="timestamp", ascending=False
            ).head(10)
        else:
            sorted_interactions = interactions_matches.iloc[::-1].head(10)

        # Build quick item lookup dictionary
        relevant_ids = set(sorted_interactions["item_id"].astype(str))
        items_sub = loaded.items[loaded.items["item_id"].astype(str).isin(relevant_ids)]
        title_map = dict(zip(items_sub["item_id"].astype(str), items_sub["title"], strict=False))

        for _, row in sorted_interactions.iterrows():
            item_id_str = str(row["item_id"])
            title = title_map.get(item_id_str, item_id_str)
            sig_val = float(row["signal"]) if pd.notna(row.get("signal")) else None
            ts_val = int(row["timestamp"]) if pd.notna(row.get("timestamp")) else None

            recent_interactions.append(
                RecentInteraction(
                    item_id=item_id_str,
                    title=str(title),
                    signal=sig_val,
                    timestamp=ts_val,
                )
            )

    # 5. Top categories with shares
    top_categories: list[CategoryShare] = []
    if not interactions_matches.empty:
        all_user_items = set(interactions_matches["item_id"].astype(str))
        items_for_cats = loaded.items[loaded.items["item_id"].astype(str).isin(all_user_items)]

        # Map item_id to its list of categories
        cat_map: dict[str, list[str]] = {}
        for _, irow in items_for_cats.iterrows():
            raw_cats = irow.get("categories")
            if isinstance(raw_cats, (list, tuple)):
                cat_map[str(irow["item_id"])] = [str(c) for c in raw_cats if c]

        # Tally categories across each interaction
        category_counts: Counter[str] = Counter()
        for _, row in interactions_matches.iterrows():
            item_cats = cat_map.get(str(row["item_id"]), [])
            for c in item_cats:
                category_counts[c] += 1

        total_cat_instances = sum(category_counts.values())
        if total_cat_instances > 0:
            for cat, count in category_counts.most_common():
                share = round(count / total_cat_instances, 4)
                top_categories.append(
                    CategoryShare(
                        category=cat,
                        count=count,
                        share=share,
                    )
                )

    return UserProfileResponse(
        user_id=uid_str,
        content_type=type,
        persona=persona,
        interaction_count=interaction_count,
        positive_count=positive_count,
        first_activity=first_activity,
        last_activity=last_activity,
        top_categories=top_categories,
        recent_items=recent_interactions,
    )
