"""Discovery Engine - API request/response schemas (Phase 7, P7.2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Unified Error Response Schema
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured error payload format adhering to Discovery Engine contract."""

    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Any | None = Field(
        default=None, description="Optional diagnostic details or validation errors"
    )


class ErrorResponse(BaseModel):
    """Standardized error wrapper returned on all non-2xx responses."""

    error: ErrorDetail


# ---------------------------------------------------------------------------
# Metadata & Health Schemas (P7.3)
# ---------------------------------------------------------------------------


class HealthTypeStatus(BaseModel):
    """Per-content-type availability status."""

    available: bool = Field(..., description="Whether content type is ready for serving")
    version: str | None = Field(default=None, description="Artifact schema version")
    reason: str | None = Field(default=None, description="Failure reason if unavailable")


class HealthResponse(BaseModel):
    """Response schema for /v1/health."""

    status: str = Field(..., description="Overall health status: 'ok', 'degraded', or 'error'")
    types: dict[str, HealthTypeStatus] = Field(
        default_factory=dict, description="Status of each registered content type"
    )
    version: str = Field(default="1.0.0", description="API engine version")


class TypeInfo(BaseModel):
    """Summary description of a registered content type."""

    id: str = Field(..., description="Content type identifier, e.g. 'movies'")
    display_name: str = Field(..., description="Human-readable title")
    card_type: str = Field(..., description="UI card template: 'media', 'product', or 'article'")
    supports_cold_start: bool = Field(
        ..., description="Whether model supports cold-start recommendation"
    )
    user_count: int = Field(default=0, description="Total unique users in training/evaluation")
    item_count: int = Field(default=0, description="Total items in catalogue")
    interaction_count: int = Field(default=0, description="Total interactions processed")


class TypesResponse(BaseModel):
    """Response schema for /v1/types."""

    types: list[TypeInfo] = Field(..., description="List of registered content types")


class UserSummary(BaseModel):
    """User summary for user selection lists."""

    user_id: str = Field(..., description="User unique identifier")
    persona: str | None = Field(default=None, description="Descriptive taste persona label")
    interaction_count: int = Field(default=0, description="Total interaction count")
    is_demo: bool = Field(default=False, description="Whether selected as a curated demo user")
    top_categories: list[str] = Field(default_factory=list, description="Top preferred categories")


class UsersResponse(BaseModel):
    """Response schema for /v1/types/{type}/users."""

    content_type: str = Field(..., description="Content type identifier")
    total: int = Field(..., description="Total users matching query")
    users: list[UserSummary] = Field(..., description="List of user profiles")


class ItemDetail(BaseModel):
    """Full detail view for a catalogue item."""

    item_id: str = Field(..., description="Item unique identifier")
    title: str = Field(..., description="Display title")
    subtitle: str | None = Field(default=None, description="Optional subtitle or brand")
    categories: list[str] = Field(
        default_factory=list, description="Associated categories or genres"
    )
    year: int | None = Field(default=None, description="Release year if known")
    image_url: str | None = Field(default=None, description="Cover or product image URL")
    text: str | None = Field(default=None, description="Description or abstract text")
    popularity_rank: int | None = Field(default=None, description="Catalog popularity rank")
    meta: dict[str, Any] = Field(default_factory=dict, description="Type-specific metadata")


class SearchItem(BaseModel):
    """Item result returned by search query."""

    item_id: str = Field(..., description="Item unique identifier")
    title: str = Field(..., description="Item title")
    subtitle: str | None = Field(default=None, description="Optional subtitle or brand")
    categories: list[str] = Field(default_factory=list, description="Associated categories")
    year: int | None = Field(default=None, description="Release year")
    image_url: str | None = Field(default=None, description="Thumbnail image URL")
    popularity_rank: int | None = Field(
        default=None, description="Popularity rank for tie-breaking"
    )
    match_type: str | None = Field(
        default=None, description="Match rank: exact, prefix, word_start, or contains"
    )


class SearchResponse(BaseModel):
    """Response schema for /v1/items/search."""

    content_type: str = Field(..., description="Content type searched")
    query: str = Field(..., description="Normalized search term")
    total_matches: int = Field(..., description="Total number of matches")
    results: list[SearchItem] = Field(..., description="Ranked search results")


class DatasetAttribution(BaseModel):
    """Attribution citation and provenance information for a dataset."""

    name: str = Field(..., description="Dataset name")
    citation: str = Field(..., description="Official academic citation")
    license: str = Field(..., description="Dataset license terms")
    source_url: str = Field(..., description="Upstream download or project URL")
    original_vs_derived: str = Field(
        ..., description="Explanation of original vs derived transformations"
    )


class AboutResponse(BaseModel):
    """Response schema for /v1/about."""

    title: str = Field(default="Discovery Engine", description="System title")
    version: str = Field(default="1.0.0", description="System version")
    description: str = Field(..., description="Architectural overview and purpose")
    attributions: list[DatasetAttribution] = Field(
        ..., description="Attribution records for all upstream data sources"
    )
    non_commercial_notice: str = Field(
        ..., description="Notice regarding research and non-commercial educational use"
    )


class MetricsResponse(BaseModel):
    """Schema for /v1/metrics endpoint response."""

    content_type: str = Field(
        ..., description="Content type identifier: 'movies', 'products', or 'articles'"
    )
    dataset_variant: str = Field(
        ...,
        description="Dataset variant label, e.g. '1m', 'video_games', or 'SYNTHETIC DEMO (not MIND)'",
    )
    is_synthetic: bool = Field(
        default=False, description="Flag indicating if metrics come from synthetic fixture data"
    )
    synthetic_fixture: bool = Field(
        default=False, description="Flag indicating if metrics come from synthetic fixture data"
    )
    synthetic_demo: bool = Field(
        default=False, description="Flag indicating if metrics come from synthetic demo data"
    )
    provenance_banner: str | None = Field(
        default=None,
        description="Warning banner when metrics originate from synthetic fixture data",
    )
    metrics: dict[str, Any] = Field(default_factory=dict, description="Complete metrics payload")


# ---------------------------------------------------------------------------
# User Profile Schemas (P7.4)
# ---------------------------------------------------------------------------


class RecentInteraction(BaseModel):
    """Summary of a past user interaction."""

    item_id: str = Field(..., description="Interacted item identifier")
    title: str = Field(..., description="Item display title")
    signal: float | None = Field(default=None, description="Rating or interaction strength")
    timestamp: int | str | None = Field(default=None, description="Interaction timestamp")


class CategoryShare(BaseModel):
    """Category preference breakdown item."""

    category: str = Field(..., description="Category label")
    count: int = Field(..., description="Number of interactions in this category")
    share: float = Field(..., ge=0.0, le=1.0, description="Fraction of total user interactions")


class UserProfileResponse(BaseModel):
    """Response schema for /v1/users/{user_id}/profile."""

    user_id: str = Field(..., description="User unique identifier")
    content_type: str = Field(..., description="Content type identifier")
    persona: str | None = Field(default=None, description="Assigned behavioral persona label")
    interaction_count: int = Field(..., description="Total historical interactions")
    positive_count: int = Field(..., description="Positive / high-signal interactions")
    first_activity: int | str | None = Field(
        default=None, description="Earliest interaction timestamp"
    )
    last_activity: int | str | None = Field(
        default=None, description="Latest interaction timestamp"
    )
    top_categories: list[CategoryShare] = Field(
        default_factory=list, description="Ranked category preferences"
    )
    recent_items: list[RecentInteraction] = Field(
        default_factory=list, description="Most recent interactions (up to 10)"
    )


# ---------------------------------------------------------------------------
# Recommendation Schemas (P7.5, P7.6, P7.7)
# ---------------------------------------------------------------------------


class RecommendationReason(BaseModel):
    """Faithful attribution reason for a recommended item."""

    kind: str = Field(
        ..., description="Attribution strategy: 'history_item', 'popular', or 'term_overlap'"
    )
    item_id: str | None = Field(
        default=None, description="Associated history item ID if applicable"
    )
    text: str | None = Field(default=None, description="Human-readable explanation clause")
    similarity_score: float | None = Field(
        default=None, description="Attribution affinity or similarity score"
    )


class ScoredItemResponse(BaseModel):
    """Recommended item with scoring, normalization, and attribution."""

    item_id: str = Field(..., description="Catalogue item identifier")
    title: str = Field(..., description="Item title")
    subtitle: str | None = Field(default=None, description="Brand, author, or subtitle")
    categories: list[str] = Field(default_factory=list, description="Categories or genres")
    year: int | None = Field(default=None, description="Release year")
    image_url: str | None = Field(default=None, description="Image URL")
    score: float = Field(..., description="Raw model recommendation score")
    display_score: float = Field(
        ..., ge=0.0, le=1.0, description="Min-max normalized score within recommended list [0, 1]"
    )
    reason: RecommendationReason | None = Field(
        default=None, description="Attribution reason explaining why recommended"
    )
    meta: dict[str, Any] = Field(default_factory=dict, description="Extra type-specific metadata")


class RecommendResponse(BaseModel):
    """Response schema for /v1/recommend."""

    content_type: str = Field(..., description="Content type identifier")
    user_id: str | None = Field(default=None, description="User identifier if known user")
    mode: str = Field(..., description="Serving mode: 'personalized' or 'popularity'")
    k: int = Field(..., description="Number of items requested")
    results: list[ScoredItemResponse] = Field(..., description="Ranked recommended items")
    meta: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic and serving metadata"
    )


class HistoryItemInput(BaseModel):
    """Single item interaction supplied in cold-start history."""

    item_id: str = Field(..., max_length=100, description="Catalogue item identifier")
    signal: float | None = Field(
        default=None, ge=0.0, le=5.0, description="Optional interaction strength or rating [0, 5]"
    )


class ColdStartRequest(BaseModel):
    """Request schema for POST /v1/recommend/cold-start."""

    type: str = Field(..., max_length=50, description="Content type identifier")
    history: list[HistoryItemInput] = Field(
        ..., max_length=200, description="Hypothetical user history (max 200 items)"
    )
    exclude: list[str] = Field(
        default_factory=list, max_length=500, description="Item IDs to explicitly exclude"
    )
    k: int = Field(
        default=10, ge=1, le=100, description="Number of recommendations requested [1, 100]"
    )


class ColdStartResponse(BaseModel):
    """Response schema for POST /v1/recommend/cold-start."""

    content_type: str = Field(..., description="Content type identifier")
    mode: str = Field(..., description="Serving mode: 'personalized' or 'popularity'")
    k: int = Field(..., description="Number of recommendations returned")
    ignored_item_ids: list[str] = Field(
        default_factory=list, description="History items that were not found in catalogue"
    )
    results: list[ScoredItemResponse] = Field(..., description="Ranked recommended items")
    meta: dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata")


class PopularResponse(BaseModel):
    """Response schema for /v1/popular."""

    content_type: str = Field(..., description="Content type identifier")
    k: int = Field(..., description="Number of popular items returned")
    results: list[ScoredItemResponse] = Field(..., description="Top popular items")


class SimilarResponse(BaseModel):
    """Response schema for /v1/similar."""

    content_type: str = Field(..., description="Content type identifier")
    query_item_id: str = Field(..., description="Query item identifier")
    k: int = Field(..., description="Number of similar items returned")
    results: list[ScoredItemResponse] = Field(..., description="Top similar items")
