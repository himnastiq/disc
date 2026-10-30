"""Discovery Engine - Registry for dataset adapters and recommender models (P2.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from engine.config import DEFAULT_CONFIGS_DIR, load_config
from engine.errors import ConfigError, ModelNotFoundError, UnknownType

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from engine.adapters.base import DatasetAdapter
    from engine.models.base import RecommenderModel
    from engine.schema import ContentTypeSpec

A = TypeVar("A", bound="DatasetAdapter")
M = TypeVar("M", bound="RecommenderModel")

_ADAPTER_REGISTRY: dict[str, type[DatasetAdapter]] = {}
_MODEL_REGISTRY: dict[str, type[RecommenderModel]] = {}
_POST_TRAIN_HOOK_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def register_post_train_hook(
    name: str,
) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    """Decorator to register a post-train evaluation hook function under a unique name."""

    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        key = name.strip().lower()
        if not key:
            raise ValueError("Post-train hook name cannot be empty")
        _POST_TRAIN_HOOK_REGISTRY[key] = fn
        return fn

    return decorator


def register_adapter(name: str) -> Callable[[type[A]], type[A]]:
    """Decorator to register a DatasetAdapter subclass under a unique name."""

    def decorator(cls: type[A]) -> type[A]:
        key = name.strip().lower()
        if not key:
            raise ValueError("Adapter name cannot be empty")
        _ADAPTER_REGISTRY[key] = cls
        return cls

    return decorator


def register_model(name: str) -> Callable[[type[M]], type[M]]:
    """Decorator to register a RecommenderModel subclass under a unique name."""

    def decorator(cls: type[M]) -> type[M]:
        key = name.strip().lower()
        if not key:
            raise ValueError("Model name cannot be empty")
        _MODEL_REGISTRY[key] = cls
        return cls

    return decorator


def _ensure_default_adapters() -> None:
    """Ensure baseline and core adapters are registered without eager module-load circular imports."""
    if "movielens" not in _ADAPTER_REGISTRY:
        from engine.adapters import movielens  # noqa: F401
    if "amazon_products" not in _ADAPTER_REGISTRY:
        from engine.adapters import amazon  # noqa: F401
    if "mind_articles" not in _ADAPTER_REGISTRY:
        from engine.adapters import mind  # noqa: F401
    if "toy" not in _ADAPTER_REGISTRY:
        import contextlib

        with contextlib.suppress(Exception):
            from engine.adapters import toy  # noqa: F401


def list_registered_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    _ensure_default_adapters()
    return sorted(_ADAPTER_REGISTRY.keys())


def _ensure_default_models() -> None:
    """Ensure baseline and core models are registered without eager module-load circular imports."""
    if "popularity" not in _MODEL_REGISTRY or "random" not in _MODEL_REGISTRY:
        from engine.models.baselines import PopularityModel, RandomModel

        _MODEL_REGISTRY["popularity"] = PopularityModel
        _MODEL_REGISTRY["random"] = RandomModel

    if "sar" not in _MODEL_REGISTRY:
        from engine.models.sar import SarModel

        _MODEL_REGISTRY["sar"] = SarModel

    if "tfidf_profile" not in _MODEL_REGISTRY:
        from engine.models.tfidf import TfidfProfileModel

        _MODEL_REGISTRY["tfidf_profile"] = TfidfProfileModel


def list_registered_models() -> list[str]:
    """Return sorted list of registered model names."""
    _ensure_default_models()
    return sorted(_MODEL_REGISTRY.keys())


def _ensure_default_hooks() -> None:
    """Ensure standard post-train hooks are registered without circular imports."""
    if "product_checks" not in _POST_TRAIN_HOOK_REGISTRY:
        from engine.evaluation.product_checks import run_product_checks_hook  # noqa: F401


def get_post_train_hook(name: str) -> Callable[..., dict[str, Any]]:
    """Retrieve a post-train hook function by name."""
    _ensure_default_hooks()
    key = name.strip().lower()
    if key not in _POST_TRAIN_HOOK_REGISTRY:
        raise ConfigError(
            f"Post-train hook '{name}' is not registered. Available hooks: {list_registered_post_train_hooks()}"
        )
    return _POST_TRAIN_HOOK_REGISTRY[key]


def list_registered_post_train_hooks() -> list[str]:
    """Return sorted list of registered post-train hook names."""
    _ensure_default_hooks()
    return sorted(_POST_TRAIN_HOOK_REGISTRY.keys())


def list_available_content_types(
    configs_dir: Path | None = None, include_test_only: bool = False
) -> list[str]:
    """Discover available content types from YAML configs in configs_dir.

    By default, ignores test-only / hidden configs where spec.test_only is True.
    """
    target_dir = configs_dir or DEFAULT_CONFIGS_DIR
    if not target_dir.exists():
        return []
    types_found: list[str] = []
    candidates = sorted(list(target_dir.glob("*.yaml")) + list(target_dir.glob("*.yml")))
    for f in candidates:
        if f.stem not in types_found:
            if include_test_only:
                types_found.append(f.stem)
            else:
                try:
                    spec = load_config(f.stem, configs_dir=target_dir)
                    if not spec.test_only:
                        types_found.append(f.stem)
                except Exception:
                    pass
    return sorted(types_found)


def public_types(configs_dir: Path | None = None) -> list[str]:
    """Return public content types excluding test_only / hidden ones."""
    return list_available_content_types(configs_dir=configs_dir, include_test_only=False)


# Alias for list_available_content_types (P6.5)
types = list_available_content_types


def get_adapter_class(name: str) -> type[DatasetAdapter]:
    """Retrieve an adapter class by its registered name."""
    _ensure_default_adapters()
    key = name.strip().lower()
    if key not in _ADAPTER_REGISTRY:
        raise ConfigError(
            f"Adapter '{name}' is not registered. Available adapters: {list_registered_adapters()}"
        )
    return _ADAPTER_REGISTRY[key]


def get_adapter(
    spec_or_type: str | ContentTypeSpec,
    fast: bool = False,
    configs_dir: Path | None = None,
) -> DatasetAdapter:
    """Instantiate and return a configured DatasetAdapter.

    Args:
        spec_or_type: Content type name (e.g. 'media') or a validated ContentTypeSpec.
        fast: Whether to apply fast developer overrides if loading from string type.
        configs_dir: Optional custom configs directory.

    Returns:
        DatasetAdapter instance configured with the spec.
    """
    if isinstance(spec_or_type, str):
        available_types = list_available_content_types(configs_dir)
        try:
            spec = load_config(spec_or_type, fast=fast, configs_dir=configs_dir)
        except ConfigError as err:
            raise UnknownType(content_type=spec_or_type, available=available_types) from err
    else:
        spec = spec_or_type

    adapter_name = spec.dataset.adapter
    adapter_cls = get_adapter_class(adapter_name)
    return adapter_cls(spec)


def get_model_class(name: str) -> type[RecommenderModel]:
    """Retrieve a model class by its registered name."""
    _ensure_default_models()
    key = name.strip().lower()
    if key not in _MODEL_REGISTRY:
        raise ModelNotFoundError(model_name=name, available=list_registered_models())
    return _MODEL_REGISTRY[key]


def build_model(
    spec_or_type: str | ContentTypeSpec,
    model_name: str | None = None,
    fast: bool = False,
    configs_dir: Path | None = None,
    **kwargs: Any,
) -> RecommenderModel:
    """Build and instantiate a RecommenderModel according to config or explicit model name.

    Args:
        spec_or_type: Content type name (e.g. 'media') or a validated ContentTypeSpec.
        model_name: Optional explicit model name (e.g. 'popularity'). Defaults to spec.model.name.
        fast: Whether to apply fast developer overrides if loading from string type.
        configs_dir: Optional custom configs directory.
        **kwargs: Additional parameters passed to the model constructor.

    Returns:
        RecommenderModel instance.
    """
    if isinstance(spec_or_type, str):
        available_types = list_available_content_types(configs_dir)
        try:
            spec = load_config(spec_or_type, fast=fast, configs_dir=configs_dir)
        except ConfigError as err:
            raise UnknownType(content_type=spec_or_type, available=available_types) from err
    else:
        spec = spec_or_type

    chosen_model_name = model_name or spec.model.name
    model_cls = get_model_class(chosen_model_name)
    return model_cls(spec, **kwargs)
