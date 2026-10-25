"""Discovery Engine - Recommendation endpoints (Phase 7, P7.5, P7.6, P7.7)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from fastapi import APIRouter, Query, Request

from api.deps import resolve_loaded_artifacts, resolve_model
from api.schemas import (
    RecommendationReason,
    RecommendResponse,
    ScoredItemResponse,
)
from engine.config import load_config
from engine.errors import UnknownUser

if TYPE_CHECKING:
    from engine.artifacts import LoadedArtifacts
    from engine.models.base import RecommenderModel

router = APIRouter(prefix="/v1", tags=["recommendations"])


def compute_display_scores(scores: list[float]) -> list[float]:
    """Calculate min-max normalized display scores in [0.0, 1.0] across results list."""
    if not scores:
        return []
    s_min = min(scores)
    s_max = max(scores)
    if s_max == s_min:
        return [1.0] * len(scores)
    return [round(float((s - s_min) / (s_max - s_min)), 4) for s in scores]


def hydrate_items(item_ids: list[str], items_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Fetch item titles, subtitles, categories, year, and images for response enrichment."""
    id_set = set(item_ids)
    subset = items_df[items_df["item_id"].astype(str).isin(id_set)]
    result: dict[str, dict[str, Any]] = {}

    for _, row in subset.iterrows():
        iid = str(row["item_id"])
        cats_raw = row.get("categories")
        categories = list(cats_raw) if isinstance(cats_raw, (list, tuple)) else []
        subtitle = str(row["subtitle"]) if pd.notna(row.get("subtitle")) else None
        year = int(row["year"]) if pd.notna(row.get("year")) else None
        image_url = str(row["image_url"]) if pd.notna(row.get("image_url")) else None

        extra: dict[str, Any] = {}
        for col in items_df.columns:
            if col not in (
                "item_id",
                "title",
                "subtitle",
                "categories",
                "year",
                "image_url",
                "text",
            ):
                val = row[col]
                if pd.notna(val):
                    extra[col] = val

        result[iid] = {
            "title": str(row.get("title", iid)),
            "subtitle": subtitle,
            "categories": categories,
            "year": year,
            "image_url": image_url,
            "extra": extra,
        }

    return result


def parse_exclusions(exclude_list: list[str]) -> set[str]:
    """Parse exclusion IDs supporting both multiple query params and comma-separated strings."""
    result: set[str] = set()
    for item in exclude_list:
        for piece in str(item).split(","):
            cleaned = piece.strip()
            if cleaned:
                result.add(cleaned)
    return result


@router.get("/recommend", response_model=RecommendResponse)
def get_recommendations(
    request: Request,
    type: str = Query(..., description="Content type identifier", max_length=50),
    user_id: str = Query(..., description="User unique identifier", max_length=100),
    k: int = Query(default=10, ge=1, le=100, description="Number of recommendations requested"),
    exclude: list[str] = Query(default_factory=list, description="Item IDs to explicitly exclude"),
) -> RecommendResponse:
    """Serve personalized recommendations from precomputed topn.parquet when possible, or compute live."""
    loaded: LoadedArtifacts = resolve_loaded_artifacts(request, type)
    model: RecommenderModel = resolve_model(request, type)
    spec = load_config(type, fast=True)

    uid_str = str(user_id)

    # 1. Verify user exists
    user_exists = (
        not loaded.users[loaded.users["user_id"].astype(str) == uid_str].empty
        or not loaded.interactions[loaded.interactions["user_id"].astype(str) == uid_str].empty
    )
    if not user_exists:
        raise UnknownUser(user_id=uid_str, content_type=type)

    # 2. Exclusions: user-supplied + past interactions (if allow_repeat is False)
    exclusions = parse_exclusions(exclude)
    user_seen: set[str] = set()
    if not spec.model.allow_repeat:
        u_interactions = loaded.interactions[loaded.interactions["user_id"].astype(str) == uid_str]
        user_seen = set(u_interactions["item_id"].astype(str))
        exclusions.update(user_seen)

    # 3. Check user's positive interactions to determine mode
    if "positive" in loaded.interactions.columns:
        user_pos_count = int(
            loaded.interactions[
                (loaded.interactions["user_id"].astype(str) == uid_str)
                & (loaded.interactions["positive"].astype(bool))
            ].shape[0]
        )
    else:
        user_pos_count = int(
            loaded.interactions[
                (loaded.interactions["user_id"].astype(str) == uid_str)
                & (loaded.interactions["signal"] >= spec.signal.positive_threshold)
            ].shape[0]
        )

    min_pos_for_pers = spec.serving.min_positive_items_for_personalization
    serving_mode = "popularity" if user_pos_count < min_pos_for_pers else "personalized"

    # 4. Attempt precomputed topn.parquet retrieval
    scored_items: list[tuple[str, float]] = []
    source = "live_model"

    if serving_mode == "personalized" and loaded.topn is not None and not loaded.topn.empty:
        user_topn = loaded.topn[loaded.topn["user_id"].astype(str) == uid_str]
        if not user_topn.empty:
            filtered_topn = user_topn[
                ~user_topn["item_id"].astype(str).isin(exclusions)
            ].sort_values(by="rank")

            if len(filtered_topn) >= k:
                source = "topn_parquet"
                for _, row in filtered_topn.head(k).iterrows():
                    scored_items.append((str(row["item_id"]), float(row["score"])))

    # 5. Live computation fallback if topn was insufficient or user needs live serving
    if not scored_items:
        model_results = model.recommend_user(user_id=uid_str, k=k, exclude_ids=exclusions)
        for item in model_results:
            scored_items.append((str(item.item_id), float(item.score)))

    # Ensure k items returned
    scored_items = scored_items[:k]

    # 6. Hydrate items metadata and calculate display scores
    raw_scores = [s for _, s in scored_items]
    display_scores = compute_display_scores(raw_scores)
    item_ids = [iid for iid, _ in scored_items]
    hydrated = hydrate_items(item_ids, loaded.items)

    results: list[ScoredItemResponse] = []
    for (iid, score), d_score in zip(scored_items, display_scores, strict=False):
        meta_info = hydrated.get(iid, {})

        # Compute faithful explanation reason if applicable
        reason_obj: RecommendationReason | None = None
        try:
            exp = model.explain(recommended_item_id=iid, user_id=uid_str)
            if exp is not None:
                reason_obj = RecommendationReason(
                    kind=exp.kind,
                    item_id=exp.item_id,
                    text=exp.text,
                    similarity_score=getattr(exp, "score", None),
                )
        except Exception:
            reason_obj = None

        results.append(
            ScoredItemResponse(
                item_id=iid,
                title=meta_info.get("title", iid),
                subtitle=meta_info.get("subtitle"),
                categories=meta_info.get("categories", []),
                year=meta_info.get("year"),
                image_url=meta_info.get("image_url"),
                score=score,
                display_score=d_score,
                reason=reason_obj,
                meta=meta_info.get("extra", {}),
            )
        )

    return RecommendResponse(
        content_type=type,
        user_id=uid_str,
        mode=serving_mode,
        k=len(results),
        results=results,
        meta={"source": source, "positive_interactions": user_pos_count},
    )
