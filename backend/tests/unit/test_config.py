"""Unit tests for engine/config.py (P2.2)."""

import pytest

from engine.config import compute_config_hash, load_config
from engine.errors import ConfigError


class TestConfigLoading:
    @pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
    def test_load_standard_configs(self, content_type):
        spec = load_config(content_type)
        assert spec.type == content_type
        assert spec.card_type in ["movie", "product", "article"]
        assert spec.dataset.adapter != ""
        assert spec.signal.positive_threshold > 0

    def test_fast_overrides_movies(self):
        standard = load_config("movies", fast=False)
        assert standard.dataset.variant == "1m"

        fast = load_config("movies", fast=True)
        assert fast.dataset.variant == "100k"
        assert fast.dataset.min_user_interactions <= standard.dataset.min_user_interactions

    def test_fast_overrides_articles(self):
        fast = load_config("articles", fast=True)
        assert fast.dataset.variant == "small"
        assert fast.model.params.get("max_features", 0) <= 2000

    def test_config_hash_deterministic(self):
        spec1 = load_config("movies")
        spec2 = load_config("movies")
        hash1 = compute_config_hash(spec1)
        hash2 = compute_config_hash(spec2)
        assert hash1 == hash2
        assert len(hash1) == 64

        # Fast override produces different hash
        fast_spec = load_config("movies", fast=True)
        fast_hash = compute_config_hash(fast_spec)
        assert fast_hash != hash1

    def test_missing_config_file_raises_readable_error(self):
        with pytest.raises(ConfigError) as exc_info:
            load_config("non_existent_type")
        assert "Configuration file not found" in str(exc_info.value)
        assert "non_existent_type" in str(exc_info.value)

    def test_invalid_yaml_syntax_raises_readable_error(self, tmp_path):
        bad_yaml = tmp_path / "broken.yaml"
        bad_yaml.write_text("type: [unclosed list", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            load_config(bad_yaml)
        assert "Invalid YAML" in str(exc_info.value)

    def test_non_dict_yaml_raises_readable_error(self, tmp_path):
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            load_config(list_yaml)
        assert "must define a mapping/dictionary" in str(exc_info.value)

    def test_missing_required_fields_raises_readable_error(self, tmp_path):
        incomplete_yaml = tmp_path / "incomplete.yaml"
        incomplete_yaml.write_text("type: movies\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            load_config(incomplete_yaml)
        msg = str(exc_info.value)
        assert "Configuration validation failed" in msg
        assert "display_name" in msg or "dataset" in msg

    def test_wrong_types_raises_readable_error(self, tmp_path):
        bad_types_yaml = tmp_path / "bad_types.yaml"
        bad_types_content = """
type: movies
display_name: Movies
card_type: movie
dataset:
  adapter: movielens
  variant: 100k
signal:
  positive_threshold: "not_a_float"
split:
  strategy: chronological
  ratio: 0.8
model:
  name: sar
"""
        bad_types_yaml.write_text(bad_types_content, encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            load_config(bad_types_yaml)
        msg = str(exc_info.value)
        assert "Configuration validation failed" in msg
        assert "positive_threshold" in msg
