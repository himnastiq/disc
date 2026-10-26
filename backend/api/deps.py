"""Discovery Engine - API dependency injection and artifact resolvers (Phase 7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Query, Request

from api.errors import ContentTypeUnavailableError
from engine import registry
from engine.errors import UnknownType

if TYPE_CHECKING:
    from api.lookups import TypeLookups
    from engine.artifacts import LoadedArtifacts
    from engine.models.base import RecommenderModel
    from engine.schema import ContentTypeSpec


def resolve_loaded_artifacts(request: Request, content_type: str) -> LoadedArtifacts:
    """Validate content type existence and availability, returning loaded artifacts."""
    ctype = content_type.strip().lower()
    available_types = registry.public_types()
    if ctype not in available_types:
        raise UnknownType(ctype, available=available_types)

    if not request.app.state.availability.get(ctype, False):
        reason = request.app.state.unavailable_reasons.get(
            ctype, "Artifacts failed to load on startup."
        )
        raise ContentTypeUnavailableError(ctype, reason=reason)

    artifacts: LoadedArtifacts = request.app.state.artifacts[ctype]
    return artifacts


def resolve_model(request: Request, content_type: str) -> RecommenderModel:
    """Validate content type and return reconstituted serving model."""
    resolve_loaded_artifacts(request, content_type)
    ctype = content_type.strip().lower()
    model: RecommenderModel = request.app.state.models[ctype]
    return model


def get_artifacts_from_query(
    request: Request,
    type: str = Query(
        ...,
        description="Content type identifier: 'movies', 'products', or 'articles'",
        max_length=50,
    ),
) -> LoadedArtifacts:
    """FastAPI query dependency returning loaded artifacts for a validated content type."""
    return resolve_loaded_artifacts(request, type)


def resolve_type_lookups(request: Request, content_type: str) -> TypeLookups:
    """Validate content type and return precomputed TypeLookups."""
    resolve_loaded_artifacts(request, content_type)
    ctype = content_type.strip().lower()
    lookups: TypeLookups = request.app.state.lookups[ctype]
    return lookups


def resolve_config(request: Request, content_type: str) -> ContentTypeSpec:
    """Validate content type and return cached ContentTypeSpec from app.state."""
    resolve_loaded_artifacts(request, content_type)
    ctype = content_type.strip().lower()
    spec: ContentTypeSpec = request.app.state.configs[ctype]
    return spec
