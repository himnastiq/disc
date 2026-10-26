"""Discovery Engine - FastAPI application (Phase 7, P7.1)."""

from __future__ import annotations

import os

# Critical performance and thread isolation: Set thread limits before importing numpy
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import register_error_handlers
from api.routes.metadata import router as metadata_router
from api.routes.recommend import router as recommend_router
from api.routes.users import router as users_router
from api.search import ItemSearchIndex
from api.security import SecurityMiddleware
from engine import registry
from engine.artifacts import load_artifacts, verify_artifacts
from engine.config import load_config
from engine.logging_utils import configure_logging, get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def get_env_config() -> dict[str, Any]:
    """Load configuration from environment variables."""
    art_dir_str = os.environ.get("ARTIFACT_DIR")
    artifact_dir = Path(art_dir_str) if art_dir_str else DEFAULT_ARTIFACTS_DIR

    api_key = os.environ.get("RECOMMENDER_API_KEY")

    cors_str = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    cors_origins = [o.strip() for o in cors_str.split(",") if o.strip()]

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    return {
        "artifact_dir": artifact_dir,
        "api_key": api_key,
        "cors_origins": cors_origins,
        "log_level": log_level,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager: loads artifacts on startup."""
    config = get_env_config()
    configure_logging(level=getattr(logging, config["log_level"], logging.INFO))
    logger = get_logger("api.main")

    app.state.artifact_dir = config["artifact_dir"]
    app.state.api_key = config["api_key"]
    app.state.artifacts = {}
    app.state.models = {}
    app.state.search_indexes = {}
    app.state.availability = {}
    app.state.unavailable_reasons = {}

    artifact_root = config["artifact_dir"]
    logger.info("Initializing Discovery Engine API from artifacts: %s", artifact_root)

    available_types = [t for t in registry.types() if t != "toy"]
    for content_type in available_types:
        if content_type == "toy":
            continue
        type_dir = artifact_root / content_type
        if not type_dir.exists():
            reason = f"Artifact directory not found at {type_dir}"
            app.state.availability[content_type] = False
            app.state.unavailable_reasons[content_type] = reason
            logger.warning("Content type '%s' unavailable: %s", content_type, reason)
            continue

        try:
            # 1. Cryptographic verification & artifact bundle loading
            verify_artifacts(type_dir)
            loaded = load_artifacts(type_dir, verify=False)

            # 2. Recommender model reconstitution
            spec = load_config(content_type, fast=True)
            model = registry.build_model(spec)
            model.load(loaded.model_dir)

            # 3. Build text search index
            search_index = ItemSearchIndex(loaded.items, loaded.interactions)

            app.state.artifacts[content_type] = loaded
            app.state.models[content_type] = model
            app.state.search_indexes[content_type] = search_index
            app.state.availability[content_type] = True
            logger.info("Content type '%s' loaded successfully.", content_type)
        except Exception as exc:
            reason = f"Failed to load artifacts for '{content_type}': {exc}"
            app.state.availability[content_type] = False
            app.state.unavailable_reasons[content_type] = reason
            logger.warning(
                "Content type '%s' failed to load (marking unavailable): %s", content_type, reason
            )

    yield

    logger.info("Discovery Engine API shutting down.")


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    config = get_env_config()
    app = FastAPI(
        title="Discovery Engine",
        version="1.0.0",
        debug=False,
        lifespan=lifespan,
    )

    # Security middleware (API key check & body size limit)
    app.add_middleware(SecurityMiddleware)

    # CORS Middleware configuration (outermost so CORS headers apply to all responses)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["cors_origins"],
        allow_credentials="*" not in config["cors_origins"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error handlers (P7.2)
    register_error_handlers(app)

    # Register routers (P7.3, P7.4, P7.5)
    app.include_router(metadata_router)
    app.include_router(users_router)
    app.include_router(recommend_router)

    return app


app = create_app()
