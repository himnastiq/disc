"""Discovery Engine - Recommendation endpoints (Phase 7, P7.5, P7.6, P7.7, FIX-34)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Request

from api.deps import resolve_model, resolve_type_lookups
from api.errors import DuplicateIDsError
from api.schemas import (
    ColdStartRequest,
    ColdStartResponse,
    PopularResponse,
    RecommendationReason,
    RecommendResponse,
    ScoredItemResponse,
    SimilarResponse,
)
from engine.errors import UnknownItem, UnknownUser
from engine.logging_utils import get_logger

if TYPE_CHECKING:
    from engine.models.base import RecommenderModel

logger = get_logger("api.routes.recommend")
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
    k: int = Query(
        default=10, ge=1, le=50, description="Number of recommendations requested [1, 50]"
    ),
    exclude: list[str] = Query(default_factory=list, description="Item IDs to explicitly exclude"),
) -> RecommendResponse:
    """Serve personalized recommendations from precomputed topn.parquet when possible, or compute live."""
    t0 = time.perf_counter()
    lookups = resolve_type_lookups(request, type)
    model: RecommenderModel = resolve_model(request, type)
    spec = lookups.spec

    uid_str = str(user_id)

    # 1. Verify user exists via O(1) in-memory index
    if uid_str not in lookups.user_ids:
        raise UnknownUser(user_id=uid_str, content_type=type)

    # 2. Exclusions: user-supplied + past interactions (if allow_repeat is False)
    exclusions = parse_exclusions(exclude)
    if not spec.model.allow_repeat:
        exclusions.update(lookups.user_seen_items.get(uid_str, set()))

    # 3. Check user's positive interactions to determine mode
    user_pos_count = lookups.user_positive_count.get(uid_str, 0)
    min_pos_for_pers = spec.serving.min_positive_items_for_personalization
    serving_mode = "popularity" if user_pos_count < min_pos_for_pers else "personalized"

    # 4. Attempt precomputed topn retrieval
    scored_items: list[tuple[str, float]] = []
    source = "live_model"

    if serving_mode == "popularity":
        source = "popularity"
        pop_results = model.popular(k=k, exclude_ids=exclusions)
        for item in pop_results:
            scored_items.append((str(item.item_id), float(item.score)))
    else:
        # Personalized mode: attempt precomputed topn retrieval
        user_topn_tuples = lookups.user_topn.get(uid_str, [])
        if user_topn_tuples:
            filtered_topn = [
                (iid, score) for iid, score in user_topn_tuples if iid not in exclusions
            ]
            if len(filtered_topn) >= k:
                source = "topn_parquet"
                scored_items.extend(filtered_topn[:k])

        # Live computation fallback if topn was insufficient
        if not scored_items:
            source = "live_model"
            model_results = model.recommend_user(user_id=uid_str, k=k, exclude_ids=exclusions)
            for item in model_results:
                scored_items.append((str(item.item_id), float(item.score)))

    # Ensure k items returned
    scored_items = scored_items[:k]

    # 5. Hydrate items metadata and calculate display scores
    raw_scores = [s for _, s in scored_items]
    display_scores = compute_display_scores(raw_scores)

    explanation_errors = 0
    results: list[ScoredItemResponse] = []
    for (iid, score), d_score in zip(scored_items, display_scores, strict=False):
        meta_info = lookups.item_metadata.get(iid, {})

        # Compute faithful explanation reason if applicable (personalized only)
        reason_obj: RecommendationReason | None = None
        if serving_mode == "personalized":
            try:
                exp = model.explain(recommended_item_id=iid, user_id=uid_str)
                if exp is not None:
                    reason_obj = RecommendationReason(
                        kind=exp.kind,
                        item_id=exp.item_id,
                        text=exp.text,
                        similarity_score=getattr(exp, "score", None),
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to compute explanation for item '%s', user '%s' (%s): %s",
                    iid,
                    uid_str,
                    type,
                    exc,
                )
                explanation_errors += 1
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

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return RecommendResponse(
        content_type=type,
        user_id=uid_str,
        mode=serving_mode,
        k=len(results),
        results=results,
        meta={
            "type": type,
            "model": spec.model.name,
            "artifact_version": lookups.artifact_version,
            "latency_ms": latency_ms,
            "source": source,
            "positive_interactions": user_pos_count,
            "explanation_errors": explanation_errors,
        },
    )


@router.post("/recommend/cold-start", response_model=ColdStartResponse)
def recommend_cold_start(
    request: Request,
    body: ColdStartRequest,
) -> ColdStartResponse:
    """Generate recommendations from hypothetical user history (cold-start)."""
    t0 = time.perf_counter()
    lookups = resolve_type_lookups(request, body.type)
    model: RecommenderModel = resolve_model(request, body.type)
    spec = lookups.spec

    # 1. Enforce unique item IDs in history (duplicates produce 422 duplicate_ids)
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for h in body.history:
        iid = str(h.item_id).strip()
        if iid in seen_ids:
            duplicate_ids.add(iid)
        else:
            seen_ids.add(iid)

    if duplicate_ids:
        raise DuplicateIDsError(
            message=f"Duplicate item IDs found in cold-start history: {sorted(duplicate_ids)}",
            duplicates=sorted(duplicate_ids),
        )

    # 2. Filter history: valid catalogue items vs ignored items via O(1) lookup
    catalogue = lookups.catalogue_ids
    valid_history: list[tuple[str, float]] = []
    ignored_item_ids: list[str] = []

    for h in body.history:
        iid = str(h.item_id).strip()
        if iid not in catalogue:
            ignored_item_ids.append(iid)
        else:
            sig = float(h.signal) if h.signal is not None else float(spec.signal.positive_threshold)
            valid_history.append((iid, sig))

    # 3. Determine serving mode based on positive items count in valid history
    threshold = spec.signal.positive_threshold
    pos_items_count = sum(1 for _, sig in valid_history if sig >= threshold)
    min_pos_required = spec.serving.min_positive_items_for_personalization

    # Exclusions include body.exclude and all history items (valid and ignored)
    exclusions = parse_exclusions(body.exclude) | {str(h.item_id).strip() for h in body.history}

    scored_items: list[tuple[str, float]] = []

    if pos_items_count < min_pos_required or not valid_history:
        serving_mode = "popularity"
        pop_results = model.popular(k=body.k, exclude_ids=exclusions)
        for item in pop_results:
            scored_items.append((str(item.item_id), float(item.score)))
    else:
        serving_mode = "personalized"
        model_results = model.recommend_history(
            history=valid_history,
            k=body.k,
            exclude_ids=exclusions,
        )
        for item in model_results:
            scored_items.append((str(item.item_id), float(item.score)))

    # Ensure k items returned
    scored_items = scored_items[: body.k]

    # 4. Hydrate item metadata and compute display scores
    raw_scores = [s for _, s in scored_items]
    display_scores = compute_display_scores(raw_scores)

    explanation_errors = 0
    results: list[ScoredItemResponse] = []
    for (iid, score), d_score in zip(scored_items, display_scores, strict=False):
        meta_info = lookups.item_metadata.get(iid, {})

        # Compute faithful explanation reason if applicable
        reason_obj: RecommendationReason | None = None
        if serving_mode == "personalized" and valid_history:
            try:
                exp = model.explain(recommended_item_id=iid, history=valid_history)
                if exp is not None:
                    reason_obj = RecommendationReason(
                        kind=exp.kind,
                        item_id=exp.item_id,
                        text=exp.text,
                        similarity_score=getattr(exp, "score", None),
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to compute cold-start explanation for item '%s' (%s): %s",
                    iid,
                    body.type,
                    exc,
                )
                explanation_errors += 1
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

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return ColdStartResponse(
        content_type=body.type,
        mode=serving_mode,
        k=len(results),
        ignored_item_ids=ignored_item_ids,
        results=results,
        meta={
            "type": body.type,
            "model": spec.model.name,
            "artifact_version": lookups.artifact_version,
            "latency_ms": latency_ms,
            "history_size": len(body.history),
            "valid_history_length": len(valid_history),
            "positive_items_count": pos_items_count,
            "explanation_errors": explanation_errors,
        },
    )


@router.get("/popular", response_model=PopularResponse)
def get_popular(
    request: Request,
    type: str = Query(..., max_length=50, description="Content type identifier"),
    k: int = Query(
        default=10, ge=1, le=50, description="Number of popular items requested [1, 50]"
    ),
) -> PopularResponse:
    """Return top-k overall popular items for content type."""
    t0 = time.perf_counter()
    lookups = resolve_type_lookups(request, type)
    model: RecommenderModel = resolve_model(request, type)

    pop_items = model.popular(k=k)
    pop_items = pop_items[:k]

    raw_scores = [float(item.score) for item in pop_items]
    display_scores = compute_display_scores(raw_scores)

    results: list[ScoredItemResponse] = []
    for item, d_score in zip(pop_items, display_scores, strict=False):
        iid = str(item.item_id)
        meta_info = lookups.item_metadata.get(iid, {})
        reason_obj = RecommendationReason(
            kind="popular",
            item_id=None,
            text="Popular across all users in the catalog",
            similarity_score=None,
        )
        results.append(
            ScoredItemResponse(
                item_id=iid,
                title=meta_info.get("title", iid),
                subtitle=meta_info.get("subtitle"),
                categories=meta_info.get("categories", []),
                year=meta_info.get("year"),
                image_url=meta_info.get("image_url"),
                score=float(item.score),
                display_score=d_score,
                reason=reason_obj,
                meta=meta_info.get("extra", {}),
            )
        )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return PopularResponse(
        content_type=type,
        k=len(results),
        results=results,
        meta={
            "type": type,
            "model": lookups.spec.model.name,
            "artifact_version": lookups.artifact_version,
            "latency_ms": latency_ms,
            "k": k,
        },
    )


@router.get("/similar", response_model=SimilarResponse)
def get_similar(
    request: Request,
    type: str = Query(..., max_length=50, description="Content type identifier"),
    item_id: str = Query(
        ..., max_length=100, description="Catalogue item identifier to find similar items for"
    ),
    k: int = Query(
        default=10, ge=1, le=50, description="Number of similar items requested [1, 50]"
    ),
) -> SimilarResponse:
    """Return top-k items similar to query item."""
    t0 = time.perf_counter()
    lookups = resolve_type_lookups(request, type)
    model: RecommenderModel = resolve_model(request, type)

    clean_item_id = str(item_id).strip()
    if clean_item_id not in lookups.catalogue_ids:
        raise UnknownItem(clean_item_id, type)

    similar_items = model.similar_items(item_id=clean_item_id, k=k)
    filtered_items = [it for it in similar_items if str(it.item_id) != clean_item_id][:k]

    query_meta = lookups.item_metadata.get(clean_item_id, {})
    query_title = query_meta.get("title", clean_item_id)

    raw_scores = [float(it.score) for it in filtered_items]
    display_scores = compute_display_scores(raw_scores)

    results: list[ScoredItemResponse] = []
    for it, d_score in zip(filtered_items, display_scores, strict=False):
        iid = str(it.item_id)
        meta_info = lookups.item_metadata.get(iid, {})
        reason_obj = RecommendationReason(
            kind="similar_item",
            item_id=clean_item_id,
            text=f"Similar to {query_title}",
            similarity_score=float(it.score),
        )
        results.append(
            ScoredItemResponse(
                item_id=iid,
                title=meta_info.get("title", iid),
                subtitle=meta_info.get("subtitle"),
                categories=meta_info.get("categories", []),
                year=meta_info.get("year"),
                image_url=meta_info.get("image_url"),
                score=float(it.score),
                display_score=d_score,
                reason=reason_obj,
                meta=meta_info.get("extra", {}),
            )
        )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return SimilarResponse(
        content_type=type,
        query_item_id=clean_item_id,
        k=len(results),
        results=results,
        meta={
            "type": type,
            "model": lookups.spec.model.name,
            "artifact_version": lookups.artifact_version,
            "latency_ms": latency_ms,
            "k": k,
        },
    )
