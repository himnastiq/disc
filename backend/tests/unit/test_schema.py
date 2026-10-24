"""Unit tests for engine/schema.py (P2.1)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.schema import (
    ContentTypeSpec,
    Interaction,
    Item,
    Reason,
    ScoredItem,
    ValidationReport,
)


class TestInteraction:
    def test_valid_interaction(self):
        interaction = Interaction(
            user_id="u123",
            item_id="i456",
            signal=4.5,
            timestamp=1609459200,
            positive=True,
        )
        assert interaction.user_id == "u123"
        assert interaction.item_id == "i456"
        assert interaction.signal == 4.5
        assert interaction.timestamp == 1609459200
        assert interaction.positive is True

    def test_coerces_int_id_to_string(self):
        interaction = Interaction(
            user_id=123,  # type: ignore[arg-type]
            item_id=456,  # type: ignore[arg-type]
            signal=1.0,
            timestamp=100,
            positive=True,
        )
        assert interaction.user_id == "123"
        assert interaction.item_id == "456"

    def test_rejects_empty_user_id(self):
        with pytest.raises(ValidationError):
            Interaction(user_id="", item_id="item1", signal=1.0, timestamp=100, positive=True)

    def test_rejects_empty_item_id(self):
        with pytest.raises(ValidationError):
            Interaction(user_id="u1", item_id="   ", signal=1.0, timestamp=100, positive=True)

    def test_rejects_negative_timestamp(self):
        with pytest.raises(ValidationError):
            Interaction(user_id="u1", item_id="i1", signal=1.0, timestamp=-1, positive=True)

    def test_rejects_nan_or_inf_signal(self):
        with pytest.raises(ValidationError):
            Interaction(
                user_id="u1", item_id="i1", signal=float("nan"), timestamp=100, positive=True
            )
        with pytest.raises(ValidationError):
            Interaction(
                user_id="u1", item_id="i1", signal=float("inf"), timestamp=100, positive=True
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Interaction(
                user_id="u1",
                item_id="i1",
                signal=1.0,
                timestamp=100,
                positive=True,
                extra_field="disallowed",  # type: ignore[call-arg]
            )


class TestItem:
    def test_valid_minimal_item(self):
        item = Item(item_id="m1", title="The Matrix")
        assert item.item_id == "m1"
        assert item.title == "The Matrix"
        assert item.categories == []
        assert item.extra == {}
        assert item.subtitle is None
        assert item.year is None

    def test_valid_full_item(self):
        item = Item(
            item_id="m1",
            title="The Matrix",
            subtitle="Sci-Fi Classic",
            categories=["Action", "Sci-Fi"],
            text="A computer hacker learns about the true nature of reality.",
            year=1999,
            image_url="http://example.com/matrix.jpg",
            extra={"director": "Wachowskis"},
        )
        assert item.year == 1999
        assert len(item.categories) == 2
        assert item.extra["director"] == "Wachowskis"

    def test_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            Item(item_id="m1", title="  ")

    def test_rejects_invalid_year(self):
        with pytest.raises(ValidationError):
            Item(item_id="m1", title="Old", year=1750)
        with pytest.raises(ValidationError):
            Item(item_id="m1", title="Future", year=2150)


class TestScoredItem:
    def test_valid_scored_item(self):
        si = ScoredItem(item_id="item_42", score=0.875, rank=1)
        assert si.item_id == "item_42"
        assert si.score == 0.875
        assert si.rank == 1

    def test_rejects_zero_or_negative_rank(self):
        with pytest.raises(ValidationError):
            ScoredItem(item_id="i1", score=1.0, rank=0)
        with pytest.raises(ValidationError):
            ScoredItem(item_id="i1", score=1.0, rank=-1)

    def test_rejects_nan_score(self):
        with pytest.raises(ValidationError):
            ScoredItem(item_id="i1", score=float("nan"), rank=1)


class TestReason:
    def test_valid_reason(self):
        r = Reason(kind="similar_item", item_id="h1", text="Because you watched Inception")
        assert r.kind == "similar_item"
        assert r.item_id == "h1"
        assert r.text == "Because you watched Inception"

    def test_reason_without_item_id(self):
        r = Reason(kind="popularity", text="Popular across all users")
        assert r.item_id is None

    def test_rejects_empty_kind_or_text(self):
        with pytest.raises(ValidationError):
            Reason(kind="", text="Valid")
        with pytest.raises(ValidationError):
            Reason(kind="valid", text="")


class TestValidationReport:
    def test_valid_report(self):
        report = ValidationReport(
            total_interactions=1000,
            unique_users=100,
            unique_items=50,
            sparsity=0.8,
            min_timestamp=1000,
            max_timestamp=2000,
            positive_interactions=600,
            filtered_users=5,
            filtered_items=2,
        )
        assert report.total_interactions == 1000
        assert report.sparsity == 0.8

    def test_rejects_invalid_sparsity(self):
        with pytest.raises(ValidationError):
            ValidationReport(
                total_interactions=10,
                unique_users=2,
                unique_items=5,
                sparsity=1.5,
            )

    def test_rejects_max_timestamp_less_than_min(self):
        with pytest.raises(ValidationError):
            ValidationReport(
                total_interactions=10,
                unique_users=2,
                unique_items=5,
                sparsity=0.5,
                min_timestamp=2000,
                max_timestamp=1000,
            )


class TestContentTypeSpec:
    @pytest.mark.parametrize("config_name", ["movies.yaml", "products.yaml", "articles.yaml"])
    def test_loads_existing_configs_successfully(self, config_name):
        config_path = (
            Path(__file__).resolve().parent.parent.parent / "engine" / "configs" / config_name
        )
        assert config_path.exists(), f"Config file missing: {config_path}"
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        spec = ContentTypeSpec.model_validate(raw)
        assert spec.type in ["movies", "products", "articles"]
        assert spec.card_type in ["movie", "product", "article"]

    def test_rejects_invalid_card_type(self):
        data = {
            "type": "audio",
            "display_name": "Audio",
            "card_type": "podcast",  # invalid
            "dataset": {"adapter": "toy", "variant": "1"},
            "signal": {"positive_threshold": 1.0},
            "split": {"strategy": "chronological", "ratio": 0.8},
            "model": {"name": "sar"},
        }
        with pytest.raises(ValidationError):
            ContentTypeSpec.model_validate(data)

    def test_rejects_invalid_split_ratio(self):
        data = {
            "type": "movies",
            "display_name": "Movies",
            "card_type": "movie",
            "dataset": {"adapter": "movielens", "variant": "100k"},
            "signal": {"positive_threshold": 4.0},
            "split": {"strategy": "chronological", "ratio": 1.5},  # invalid
            "model": {"name": "sar"},
        }
        with pytest.raises(ValidationError):
            ContentTypeSpec.model_validate(data)

    def test_serving_config_defaults(self):
        data = {
            "type": "movies",
            "display_name": "Movies",
            "card_type": "movie",
            "dataset": {"adapter": "movielens", "variant": "100k"},
            "signal": {"positive_threshold": 4.0},
            "split": {"strategy": "chronological", "ratio": 0.8},
            "model": {"name": "sar"},
        }
        spec = ContentTypeSpec.model_validate(data)
        assert spec.serving.min_positive_items_for_personalization == 3
        assert spec.serving.explanation_min_threshold == 0.2

    def test_serving_config_custom_values(self):
        data = {
            "type": "movies",
            "display_name": "Movies",
            "card_type": "movie",
            "dataset": {"adapter": "movielens", "variant": "100k"},
            "signal": {"positive_threshold": 4.0},
            "split": {"strategy": "chronological", "ratio": 0.8},
            "model": {"name": "sar"},
            "serving": {
                "min_positive_items_for_personalization": 5,
                "explanation_min_threshold": 0.35,
            },
        }
        spec = ContentTypeSpec.model_validate(data)
        assert spec.serving.min_positive_items_for_personalization == 5
        assert spec.serving.explanation_min_threshold == 0.35

    def test_serving_config_invalid_values(self):
        base_data = {
            "type": "movies",
            "display_name": "Movies",
            "card_type": "movie",
            "dataset": {"adapter": "movielens", "variant": "100k"},
            "signal": {"positive_threshold": 4.0},
            "split": {"strategy": "chronological", "ratio": 0.8},
            "model": {"name": "sar"},
        }

        # min_positive_items_for_personalization < 1
        data1 = dict(base_data, serving={"min_positive_items_for_personalization": 0})
        with pytest.raises(ValidationError):
            ContentTypeSpec.model_validate(data1)

        # explanation_min_threshold < 0.0
        data2 = dict(base_data, serving={"explanation_min_threshold": -0.1})
        with pytest.raises(ValidationError):
            ContentTypeSpec.model_validate(data2)

        # explanation_min_threshold > 1.0
        data3 = dict(base_data, serving={"explanation_min_threshold": 1.1})
        with pytest.raises(ValidationError):
            ContentTypeSpec.model_validate(data3)
