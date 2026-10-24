"""Discovery Engine - Configuration loading, validation, hashing, and overrides (P2.2)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from engine.errors import ConfigError
from engine.schema import ContentTypeSpec

# Default configs directory relative to this file: backend/engine/configs
DEFAULT_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def compute_config_hash(data: dict[str, Any] | ContentTypeSpec) -> str:
    """Compute a deterministic SHA-256 hash for a configuration dictionary or ContentTypeSpec."""
    raw_dict = data.model_dump() if isinstance(data, ContentTypeSpec) else copy.deepcopy(data)

    # Serialize canonical JSON with sorted keys
    canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def get_config_path(path_or_type: str | Path, configs_dir: Path | None = None) -> Path:
    """Resolve a config path from an explicit file path or content type slug."""
    p = Path(path_or_type)
    if p.exists() and p.is_file():
        return p.resolve()

    base_dir = configs_dir or DEFAULT_CONFIGS_DIR
    slug_path = base_dir / f"{path_or_type}.yaml"
    if slug_path.exists() and slug_path.is_file():
        return slug_path.resolve()

    slug_yml_path = base_dir / f"{path_or_type}.yml"
    if slug_yml_path.exists() and slug_yml_path.is_file():
        return slug_yml_path.resolve()

    raise ConfigError(
        f"Configuration file not found for '{path_or_type}'. Searched: {p} and {slug_path}"
    )


def apply_fast_overrides(raw_dict: dict[str, Any]) -> dict[str, Any]:
    """Apply --fast overrides to dataset variant and search parameters for quick developer runs."""
    config = copy.deepcopy(raw_dict)
    content_type = config.get("type", "")

    dataset = config.setdefault("dataset", {})
    if content_type == "movies":
        dataset["variant"] = "100k"
        dataset["min_user_interactions"] = min(dataset.get("min_user_interactions", 5), 3)
        dataset["min_item_interactions"] = min(dataset.get("min_item_interactions", 5), 3)
    elif content_type == "articles":
        dataset["variant"] = "small"
        if "model" in config and "params" in config["model"]:
            params = config["model"]["params"]
            if "max_features" in params:
                params["max_features"] = min(params["max_features"], 2000)
    elif content_type == "products":
        dataset["variant"] = dataset.get("variant", "default")
        if "serving" in config:
            config["serving"]["max_items_in_similarity"] = min(
                config["serving"].get("max_items_in_similarity", 8000), 2000
            )

    # Limit cold-start history sizes for fast test evaluation
    if "evaluation" in config:
        eval_cfg = config["evaluation"]
        if "cold_start_history_sizes" in eval_cfg:
            eval_cfg["cold_start_history_sizes"] = [0, 1, 3, 5]

    return config


def load_config(
    path_or_type: str | Path,
    fast: bool = False,
    configs_dir: Path | None = None,
) -> ContentTypeSpec:
    """Load, validate, optionally override, and return a ContentTypeSpec.

    Args:
        path_or_type: File path or content type identifier (e.g. 'movies').
        fast: If True, applies faster settings (smaller dataset variants).
        configs_dir: Optional custom directory to look for config YAMLs.

    Returns:
        Validated ContentTypeSpec instance.

    Raises:
        ConfigError: If file is missing, YAML is invalid, or schema validation fails.
    """
    config_file = get_config_path(path_or_type, configs_dir)

    try:
        content = config_file.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"Failed to read config file '{config_file}': {e}") from e

    try:
        raw_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file '{config_file}': {e}") from e

    if not isinstance(raw_data, dict):
        raise ConfigError(
            f"Config file '{config_file}' must define a mapping/dictionary, got {type(raw_data).__name__}"
        )

    if fast:
        raw_data = apply_fast_overrides(raw_data)

    try:
        spec = ContentTypeSpec.model_validate(raw_data)
    except ValidationError as e:
        errors_summary = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            errors_summary.append(f"Field '{loc}': {msg}")
        readable_errors = "\n  - " + "\n  - ".join(errors_summary)
        raise ConfigError(
            f"Configuration validation failed for '{config_file}':{readable_errors}"
        ) from e

    return spec
