"""Discovery Engine - API request/response schemas."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class MetricsResponse(BaseModel):
    """Schema for /v1/metrics endpoint response."""

    content_type: str = Field(..., description="Content type identifier: 'movies', 'products', or 'articles'")
    dataset_variant: str = Field(..., description="Dataset variant label, e.g. '1m', 'video_games', or 'SYNTHETIC FIXTURE (not MIND)'")
    is_synthetic: bool = Field(default=False, description="Flag indicating if metrics come from synthetic fixture data")
    synthetic_fixture: bool = Field(default=False, description="Flag indicating if metrics come from synthetic fixture data")
    provenance_banner: str | None = Field(
        default=None,
        description="Warning banner when metrics originate from synthetic fixture data",
    )
    metrics: dict[str, Any] = Field(default_factory=dict, description="Complete metrics payload")
