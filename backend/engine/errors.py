"""Discovery Engine - Custom exception hierarchy."""

from __future__ import annotations

from typing import Any


class DiscoveryEngineError(Exception):
    """Base exception for all Discovery Engine errors."""


class ConfigError(DiscoveryEngineError):
    """Raised when configuration loading or validation fails."""


class DataValidationError(DiscoveryEngineError):
    """Raised when dataset input does not satisfy schema or quality constraints."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ModelNotFoundError(DiscoveryEngineError):
    """Raised when a model architecture is not recognized in registry."""

    def __init__(self, model_name: str, available: list[str] | None = None) -> None:
        msg = f"Model '{model_name}' not found."
        if available:
            msg += f" Available models: {', '.join(sorted(available))}."
        super().__init__(msg)
        self.model_name = model_name
        self.available = available or []


class ArtifactError(DiscoveryEngineError):
    """Raised when model or precomputed artifacts cannot be loaded or accessed."""


class ArtifactCorruptError(ArtifactError):
    """Raised when an artifact checksum, manifest, or schema version check fails."""

    def __init__(self, artifact_path: str, reason: str) -> None:
        super().__init__(f"Artifact corrupted at '{artifact_path}': {reason}")
        self.artifact_path = artifact_path
        self.reason = reason


class UnknownType(DiscoveryEngineError):  # noqa: N818
    """Raised when an unknown content type is requested."""

    def __init__(self, content_type: str, available: list[str] | None = None) -> None:
        msg = f"Unknown content type: '{content_type}'."
        if available:
            msg += f" Available types: {', '.join(sorted(available))}."
        super().__init__(msg)
        self.content_type = content_type
        self.available = available or []


class UnknownUser(DiscoveryEngineError):  # noqa: N818
    """Raised when a requested user ID is not found in the dataset/artifacts."""

    def __init__(self, user_id: str, content_type: str | None = None) -> None:
        msg = f"Unknown user ID: '{user_id}'"
        if content_type:
            msg += f" for content type '{content_type}'"
        super().__init__(msg)
        self.user_id = user_id
        self.content_type = content_type


class UnknownItem(DiscoveryEngineError):  # noqa: N818
    """Raised when a requested item ID is not found in the catalogue."""

    def __init__(self, item_id: str, content_type: str | None = None) -> None:
        msg = f"Unknown item ID: '{item_id}'"
        if content_type:
            msg += f" for content type '{content_type}'"
        super().__init__(msg)
        self.item_id = item_id
        self.content_type = content_type


class ColdStartUnsupported(DiscoveryEngineError):  # noqa: N818
    """Raised when cold-start history recommendation is not supported by the model."""

    def __init__(self, model_name: str) -> None:
        super().__init__(f"Model '{model_name}' does not support cold-start recommendation.")
        self.model_name = model_name
