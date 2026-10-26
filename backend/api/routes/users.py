"""Discovery Engine - User profile endpoint (Phase 7, P7.4)."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query, Request

from api.deps import resolve_type_lookups
from api.schemas import CategoryShare, RecentInteraction, UserProfileResponse
from engine.errors import UnknownUser

router = APIRouter(prefix="/v1", tags=["users"])


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    request: Request,
    user_id: str = Path(..., description="User unique identifier", max_length=100),
    type: str = Query(..., description="Content type identifier", max_length=50),
) -> UserProfileResponse:
    """Retrieve user taste profile: interaction counts, category preferences, and recent history."""
    lookups = resolve_type_lookups(request, type)

    # 1. Verify user exists in dataset via O(1) in-memory index
    uid_str = str(user_id)
    if uid_str not in lookups.user_ids:
        raise UnknownUser(user_id=uid_str, content_type=type)

    persona = lookups.user_persona.get(uid_str)
    interaction_count = lookups.user_interactions_count.get(uid_str, 0)
    positive_count = lookups.user_positive_count.get(uid_str, 0)
    first_activity = lookups.user_first_activity.get(uid_str)
    last_activity = lookups.user_last_activity.get(uid_str)

    recent_interactions = [
        RecentInteraction(
            item_id=r["item_id"],
            title=r["title"],
            signal=r["signal"],
            timestamp=r["timestamp"],
        )
        for r in lookups.user_recent_interactions.get(uid_str, [])
    ]

    top_categories = [
        CategoryShare(
            category=c["category"],
            count=c["count"],
            share=c["share"],
        )
        for c in lookups.user_category_shares.get(uid_str, [])
    ]

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
