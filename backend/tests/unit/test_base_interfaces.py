"""Tests for DatasetAdapter and RecommenderModel abstract base interfaces (P2.3)."""

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from engine.adapters.base import DatasetAdapter
from engine.config import load_config
from engine.errors import (
    ColdStartUnsupported,
    UnknownItem,
    UnknownUser,
)
from engine.models.base import RecommenderModel
from engine.schema import ContentTypeSpec, Reason, ScoredItem, ValidationReport


@pytest.fixture
def sample_spec() -> ContentTypeSpec:
    return load_config("movies")


def test_cannot_instantiate_abstract_adapter(sample_spec: ContentTypeSpec) -> None:
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        DatasetAdapter(sample_spec)  # type: ignore[abstract]


def test_cannot_instantiate_abstract_model(sample_spec: ContentTypeSpec) -> None:
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        RecommenderModel(sample_spec)  # type: ignore[abstract]


class ConcreteTestAdapter(DatasetAdapter):
    def download(self, raw_dir: Path) -> None:
        pass

    def load_raw(self, raw_dir: Path) -> Any:
        return {}

    def interactions(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["user_id", "item_id", "signal", "timestamp", "positive"])

    def items(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "item_id",
                "title",
                "subtitle",
                "categories",
                "text",
                "year",
                "image_url",
                "extra",
            ]
        )

    def validate(self) -> ValidationReport:
        return ValidationReport(
            total_interactions=0,
            unique_users=0,
            unique_items=0,
            sparsity=0.0,
            min_timestamp=0,
            max_timestamp=0,
            filtered_users=0,
            filtered_items=0,
        )

    def split(self, interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        empty = pd.DataFrame()
        return empty, empty, empty


class ConcreteTestModel(RecommenderModel):
    @property
    def supports_cold_start(self) -> bool:
        return True

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        pass

    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        if user_id == "unknown_user":
            raise UnknownUser(user_id=user_id, content_type="test")
        return [ScoredItem(item_id="item_1", score=1.0, rank=1)]

    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        if not self.supports_cold_start:
            raise ColdStartUnsupported("ConcreteTestModel")
        return [ScoredItem(item_id="item_2", score=0.9, rank=1)]

    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        if item_id == "unknown_item":
            raise UnknownItem(item_id=item_id, content_type="test")
        return [ScoredItem(item_id="item_3", score=0.8, rank=1)]

    def popular(
        self,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        return [ScoredItem(item_id="item_popular", score=10.0, rank=1)]

    def explain(
        self,
        history_item_ids: list[str],
        recommended_item_id: str,
    ) -> Reason | None:
        if history_item_ids:
            return Reason(
                item_id=history_item_ids[0],
                kind="co_occurrence",
                text=f"Because you interacted with {history_item_ids[0]}",
            )
        return None

    def save(self, dir_path: Path) -> None:
        pass

    def load(self, dir_path: Path) -> None:
        pass


def test_concrete_adapter_instantiation(sample_spec: ContentTypeSpec) -> None:
    adapter = ConcreteTestAdapter(sample_spec)
    assert adapter.spec.type == "movies"
    inter = adapter.interactions()
    assert list(inter.columns) == [
        "user_id",
        "item_id",
        "signal",
        "timestamp",
        "positive",
    ]
    report = adapter.validate()
    assert report.total_interactions == 0


def test_concrete_model_execution_and_errors(sample_spec: ContentTypeSpec) -> None:
    model = ConcreteTestModel(sample_spec)
    assert model.supports_cold_start is True

    # Check successful recommendation
    recs = model.recommend_user("u1", k=5)
    assert len(recs) == 1
    assert recs[0].item_id == "item_1"

    # Check unknown user error
    with pytest.raises(UnknownUser) as exc_info:
        model.recommend_user("unknown_user", k=5)
    assert exc_info.value.user_id == "unknown_user"

    # Check unknown item error
    with pytest.raises(UnknownItem) as exc_item_info:
        model.similar_items("unknown_item", k=5)
    assert exc_item_info.value.item_id == "unknown_item"

    # Check explain
    reason = model.explain(["history_1"], "item_1")
    assert reason is not None
    assert reason.item_id == "history_1"
