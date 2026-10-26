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

    def test_fast_off_is_unchanged(self):
        spec = load_config("movies", fast=False)
        assert spec.dataset.variant == "1m"
        assert spec.dataset.min_user_interactions == 5
        assert spec.evaluation.cold_start_history_sizes == [0, 1, 2, 3, 5, 10, 20]

    def test_fast_on_applies_yaml_overrides(self):
        spec = load_config("movies", fast=True)
        assert spec.dataset.variant == "100k"
        assert spec.dataset.min_user_interactions == 3
        assert spec.dataset.min_item_interactions == 3
        assert spec.evaluation.cold_start_history_sizes == [0, 1, 3, 5]

    def test_type_with_no_fast_section(self, tmp_path):
        no_fast_yaml = tmp_path / "nofast.yaml"
        content = """
type: nofast
display_name: No Fast
card_type: movie
dataset:
  adapter: movielens
  variant: "custom"
  min_user_interactions: 5
signal:
  positive_threshold: 4.0
split:
  strategy: chronological
  ratio: 0.8
model:
  name: sar
"""
        no_fast_yaml.write_text(content, encoding="utf-8")
        spec_off = load_config(no_fast_yaml, fast=False)
        spec_on = load_config(no_fast_yaml, fast=True)
        assert spec_off.dataset.variant == "custom"
        assert spec_on.dataset.variant == "custom"
        assert spec_off.dataset.min_user_interactions == spec_on.dataset.min_user_interactions

    def test_fast_section_bad_value_gives_config_error(self, tmp_path):
        # Case A: fast section is not a dict
        bad_fast_yaml = tmp_path / "bad_fast.yaml"
        content = """
type: badfast
display_name: Bad Fast
card_type: movie
dataset:
  adapter: movielens
signal:
  positive_threshold: 4.0
split:
  strategy: chronological
  ratio: 0.8
model:
  name: sar
fast: "not_a_mapping"
"""
        bad_fast_yaml.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError) as exc_info:
            load_config(bad_fast_yaml, fast=True)
        assert "must be a mapping/dict" in str(exc_info.value)

        # Case B: fast overrides break schema validation
        broken_override_yaml = tmp_path / "broken_override.yaml"
        content_b = """
type: brokenoverride
display_name: Broken Override
card_type: movie
dataset:
  adapter: movielens
signal:
  positive_threshold: 4.0
split:
  strategy: chronological
  ratio: 0.8
model:
  name: sar
fast:
  signal:
    positive_threshold: "invalid_float"
"""
        broken_override_yaml.write_text(content_b, encoding="utf-8")
        with pytest.raises(ConfigError) as exc_info_b:
            load_config(broken_override_yaml, fast=True)
        assert "Configuration validation failed" in str(exc_info_b.value)

    def test_resolve_serving_config_hash_mismatch_raises(self, tmp_path):
        import json

        from engine.config import resolve_serving_config

        type_dir = tmp_path / "fake_movies"
        type_dir.mkdir()

        manifest = {
            "artifact_schema_version": "1.0.0",
            "content_type": "movies",
            "dataset_variant": "1m",
            "config_hash": "deadbeef" * 8,
        }
        (type_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            resolve_serving_config("movies", type_dir)
        assert "Serving config hash mismatch" in str(exc_info.value)
        assert "deadbeef" in str(exc_info.value)

    def test_resolve_serving_config_agrees_with_manifest_across_all_types(self):
        import json
        from pathlib import Path

        from engine.config import compute_config_hash, resolve_serving_config

        for ctype in ["movies", "products", "articles"]:
            art_dir = Path("artifacts") / ctype
            if art_dir.exists() and (art_dir / "manifest.json").exists():
                spec = resolve_serving_config(ctype, art_dir)
                manifest = json.loads((art_dir / "manifest.json").read_text(encoding="utf-8"))
                assert compute_config_hash(spec) == manifest["config_hash"]

    def test_resolve_serving_config_reconstructs_tuned_similarity_and_timedecay(self, tmp_path):
        """F-010: resolve_serving_config must reconstruct tuned similarity_type and timedecay_formula."""
        import json

        from engine.config import compute_config_hash, load_config, resolve_serving_config

        type_dir = tmp_path / "tuned_movies"
        type_dir.mkdir()

        # Build expected spec matching tuned parameters
        tuned_spec = load_config("movies", fast=True)
        tuned_spec.model.params["similarity_type"] = "lift"
        tuned_spec.model.params["timedecay_formula"] = False
        tuned_spec.model.params["time_decay_coefficient"] = None
        tuned_spec.signal.positive_threshold = 3.5
        tuned_spec.serving.top_neighbors_per_item = 50
        expected_hash = compute_config_hash(tuned_spec)

        manifest = {
            "artifact_schema_version": "1.0.0",
            "content_type": "movies",
            "dataset_variant": "100k",
            "config_hash": expected_hash,
        }
        (type_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        tuning_data = {
            "best_params": {
                "similarity_type": "lift",
                "timedecay_formula": False,
                "time_decay_coefficient": None,
                "positive_threshold": 3.5,
                "top_neighbors_per_item": 50,
            }
        }
        (type_dir / "tuning.json").write_text(json.dumps(tuning_data), encoding="utf-8")

        reconstructed = resolve_serving_config("movies", type_dir)
        assert reconstructed.model.params["similarity_type"] == "lift"
        assert reconstructed.model.params["timedecay_formula"] is False
        assert compute_config_hash(reconstructed) == expected_hash

    def test_resolve_serving_config_corrupt_tuning_json_raises_loudly(self, tmp_path):
        """F-010: Corrupt tuning.json must fail loudly with ConfigError instead of silent pass."""
        import json

        from engine.config import resolve_serving_config

        type_dir = tmp_path / "corrupt_tuning_movies"
        type_dir.mkdir()

        manifest = {
            "artifact_schema_version": "1.0.0",
            "content_type": "movies",
            "dataset_variant": "100k",
            "config_hash": "deadbeef" * 8,
        }
        (type_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (type_dir / "tuning.json").write_text("NOT_VALID_JSON{", encoding="utf-8")

        with pytest.raises(ConfigError, match=r"Failed to parse tuning\.json"):
            resolve_serving_config("movies", type_dir)
