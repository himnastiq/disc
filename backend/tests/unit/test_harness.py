"""Unit tests for the EvaluationHarness (P2.8 / R4)."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from engine.config import load_config
from engine.evaluation.harness import EvaluationHarness, get_git_sha
from engine.schema import ContentTypeSpec


@pytest.fixture
def movies_spec() -> ContentTypeSpec:
    return load_config("movies", fast=True)


@pytest.fixture
def synthetic_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    # 20 items
    items_data = [
        {
            "item_id": f"item_{i}",
            "title": f"Movie {i}",
            "categories": ["Action" if i % 2 == 0 else "Drama"],
        }
        for i in range(1, 21)
    ]
    items_df = pd.DataFrame(items_data)

    # 10 users with 15 interactions each (total 150 interactions)
    interactions_rows = []
    for u in range(1, 11):
        user_id = f"user_{u}"
        for i in range(1, 16):
            # item selection has popular items (item_1 to item_5 appear more often)
            item_idx = ((u + i) % 20) + 1
            signal = 5.0 if (i % 3 != 0) else 2.0
            interactions_rows.append(
                {
                    "user_id": user_id,
                    "item_id": f"item_{item_idx}",
                    "signal": signal,
                    "timestamp": 1000 * u + 10 * i,
                    "positive": signal >= 4.0,
                }
            )

    interactions_df = pd.DataFrame(interactions_rows)
    return interactions_df, items_df


def test_get_git_sha() -> None:
    sha = get_git_sha()
    assert isinstance(sha, str)
    assert len(sha) > 0


def test_harness_end_to_end_on_synthetic_data(
    tmp_path: Path,
    movies_spec: ContentTypeSpec,
    synthetic_dataset: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    interactions_df, items_df = synthetic_dataset
    out_file = tmp_path / "test_metrics.json"

    harness = EvaluationHarness(movies_spec)
    metrics = harness.run(
        interactions=interactions_df,
        items=items_df,
        output_path=out_file,
        max_test_users=10,
        cold_start_sample_users=5,
    )

    # 1. Output file exists and parses as valid JSON
    assert out_file.exists()
    file_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert file_data["config_hash"] == metrics["config_hash"]

    # 2. Check top-level keys
    expected_keys = [
        "protocol",
        "seeds",
        "config_hash",
        "git_sha",
        "created_at",
        "content_type",
        "dataset_variant",
        "k_values",
        "models",
        "cold_start_curves",
        "sanity_checks",
    ]
    for key in expected_keys:
        assert key in metrics

    # 3. Protocol section
    assert metrics["content_type"] == "movies"
    assert metrics["protocol"]["split_strategy"] == "chronological"
    assert metrics["protocol"]["total_interactions"] == len(interactions_df)
    assert metrics["protocol"]["total_items"] == len(items_df)

    # 4. Models evaluated
    assert "popularity" in metrics["models"]
    assert "random" in metrics["models"]

    for model_name in ("popularity", "random"):
        model_metrics = metrics["models"][model_name]
        for k in movies_spec.evaluation.k:
            k_str = str(k)
            assert k_str in model_metrics
            k_res = model_metrics[k_str]
            for metric_name in [
                "precision",
                "recall",
                "ndcg",
                "map",
                "hit_rate",
                "coverage",
                "novelty",
                "diversity",
                "personalisation",
            ]:
                assert metric_name in k_res
                assert isinstance(k_res[metric_name], float)
                assert not math.isnan(k_res[metric_name])

    # 5. Cold start curves
    assert "popularity" in metrics["cold_start_curves"]
    pop_cs = metrics["cold_start_curves"]["popularity"]
    for size in movies_spec.evaluation.cold_start_history_sizes:
        assert str(size) in pop_cs

    # 6. Sanity checks
    assert "popularity_beats_random" in metrics["sanity_checks"]
    assert isinstance(metrics["sanity_checks"]["popularity_beats_random"], bool)
