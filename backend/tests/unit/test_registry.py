"""Tests for adapter and model registry (P2.5)."""

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from engine.adapters.base import DatasetAdapter
from engine.config import load_config
from engine.errors import ConfigError, ModelNotFoundError, UnknownType
from engine.models.base import RecommenderModel
from engine.models.baselines import PopularityModel, RandomModel
from engine.registry import (
    build_model,
    get_adapter,
    get_adapter_class,
    get_model_class,
    list_available_content_types,
    list_registered_adapters,
    list_registered_models,
    register_adapter,
    register_model,
)
from engine.schema import Reason, ScoredItem, ValidationReport


@register_adapter("dummy_test_adapter")
class DummyTestAdapter(DatasetAdapter):
    def download(self, raw_dir: Path) -> None:
        pass

    def load_raw(self, raw_dir: Path) -> Any:
        return {}

    def interactions(self) -> pd.DataFrame:
        return pd.DataFrame()

    def items(self) -> pd.DataFrame:
        return pd.DataFrame()

    def validate(self) -> ValidationReport:
        return ValidationReport(
            total_interactions=0,
            unique_users=0,
            unique_items=0,
            sparsity=0.0,
        )

    def split(self, interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        empty = pd.DataFrame()
        return empty, empty, empty


@register_model("dummy_test_model")
class DummyTestModel(RecommenderModel):
    @property
    def supports_cold_start(self) -> bool:
        return False

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        pass

    def recommend_user(
        self, user_id: str, k: int, exclude_ids: Collection[str] = ()
    ) -> list[ScoredItem]:
        return []

    def recommend_history(
        self, history: list[tuple[str, float]], k: int, exclude_ids: Collection[str] = ()
    ) -> list[ScoredItem]:
        return []

    def similar_items(self, item_id: str, k: int) -> list[ScoredItem]:
        return []

    def popular(self, k: int, exclude_ids: Collection[str] = ()) -> list[ScoredItem]:
        return []

    def explain(self, history_item_ids: list[str], recommended_item_id: str) -> Reason | None:
        return None

    def save(self, dir_path: Path) -> None:
        pass

    def load(self, dir_path: Path) -> None:
        pass


def test_builtin_models_registered() -> None:
    models = list_registered_models()
    assert "popularity" in models
    assert "random" in models
    assert get_model_class("popularity") is PopularityModel
    assert get_model_class("random") is RandomModel


def test_custom_registration_works_without_editing_core() -> None:
    assert "dummy_test_adapter" in list_registered_adapters()
    assert get_adapter_class("dummy_test_adapter") is DummyTestAdapter

    assert "dummy_test_model" in list_registered_models()
    assert get_model_class("dummy_test_model") is DummyTestModel


def test_list_available_content_types() -> None:
    types = list_available_content_types()
    assert "movies" in types
    assert "products" in types
    assert "articles" in types


def test_get_adapter_by_spec() -> None:
    spec = load_config("movies")
    # Change adapter to our registered dummy adapter
    spec.dataset.adapter = "dummy_test_adapter"
    adapter = get_adapter(spec)
    assert isinstance(adapter, DummyTestAdapter)
    assert adapter.spec.type == "movies"


def test_build_model_by_spec_and_override() -> None:
    spec = load_config("movies")
    # Build baseline model via override
    model_pop = build_model(spec, model_name="popularity")
    assert isinstance(model_pop, PopularityModel)

    model_dummy = build_model(spec, model_name="dummy_test_model")
    assert isinstance(model_dummy, DummyTestModel)


def test_unregistered_adapter_raises_clear_error() -> None:
    with pytest.raises(ConfigError) as exc_info:
        get_adapter_class("non_existent_adapter")
    assert "non_existent_adapter" in str(exc_info.value)
    assert "Available adapters:" in str(exc_info.value)


def test_unregistered_model_raises_model_not_found_error() -> None:
    with pytest.raises(ModelNotFoundError) as exc_info:
        get_model_class("non_existent_model")
    assert exc_info.value.model_name == "non_existent_model"
    assert "popularity" in exc_info.value.available


def test_unknown_type_in_get_adapter_and_build_model() -> None:
    with pytest.raises(UnknownType) as exc_adapter:
        get_adapter("non_existent_type_xyz")
    assert exc_adapter.value.content_type == "non_existent_type_xyz"

    with pytest.raises(UnknownType) as exc_model:
        build_model("non_existent_type_xyz")
    assert exc_model.value.content_type == "non_existent_type_xyz"


def test_empty_registration_name_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        register_adapter("   ")(DummyTestAdapter)

    with pytest.raises(ValueError, match="cannot be empty"):
        register_model("")(DummyTestModel)
