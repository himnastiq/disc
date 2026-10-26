"""Unit tests for tools/product_checks.py (P4.6).

Verifies product-specific metrics computation on synthetic fixtures and
confirms presence and integrity of product-specific checks in saved artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

# Add tools to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from product_checks import (  # noqa: E402
    compute_category_diversity_metrics,
    compute_long_tail_metrics,
    compute_similar_alternatives_spot_check,
    compute_sparse_data_metrics,
    extract_item_categories,
)

from engine.schema import ScoredItem  # noqa: E402


class MockProductModel:
    """Mock model returning controlled recommendations and similar items."""

    def __init__(self, item_ids: list[str]) -> None:
        self.item_ids = item_ids

    def recommend_user(self, user_id: str, k: int = 10, **kwargs: Any) -> list[ScoredItem]:
        # Return first k items
        return [
            ScoredItem(item_id=iid, score=1.0 / (idx + 1), rank=idx + 1)
            for idx, iid in enumerate(self.item_ids[:k])
        ]

    def similar_items(self, item_id: str, k: int = 5, **kwargs: Any) -> list[ScoredItem]:
        # Return subsequent items in item_ids excluding self
        others = [i for i in self.item_ids if i != item_id]
        return [
            ScoredItem(item_id=iid, score=0.9 - idx * 0.1, rank=idx + 1)
            for idx, iid in enumerate(others[:k])
        ]


def test_sparse_data_metrics_on_synthetic_df() -> None:
    """Test sparse user detection and summary statistics."""
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u2", "u2", "u3", "u4"]
            + ["u4"] * 9,  # u1: 2, u2: 3, u3: 1, u4: 10
            "item_id": ["i1", "i2", "i1", "i3", "i4", "i1", "i2"] + ["i5"] * 9,
        }
    )
    metrics = compute_sparse_data_metrics(df, threshold=5)

    assert metrics["total_users"] == 4
    assert metrics["sparse_user_count"] == 3  # u1, u2, u3
    assert metrics["sparse_user_ratio"] == 0.75
    assert metrics["threshold_interactions"] == 5
    assert metrics["mean_interactions_per_user"] == 4.0


def test_long_tail_metrics_on_synthetic_df() -> None:
    """Test bottom-80% item tail volume and recommendation share."""
    # 5 items total: i1 (10), i2 (6), i3 (2), i4 (1), i5 (1) -> 20 interactions total
    # Bottom 80% is bottom 4 items: i2, i3, i4, i5 -> volume is 6 + 2 + 1 + 1 = 10 (50%)
    rows = []
    rows.extend([{"user_id": f"u_{idx}", "item_id": "i1"} for idx in range(10)])
    rows.extend([{"user_id": f"u_{idx}", "item_id": "i2"} for idx in range(6)])
    rows.extend([{"user_id": f"u_{idx}", "item_id": "i3"} for idx in range(2)])
    rows.extend([{"user_id": "u_99", "item_id": "i4"}])
    rows.extend([{"user_id": "u_99", "item_id": "i5"}])
    df = pd.DataFrame(rows)

    mock_model = MockProductModel(item_ids=["i1", "i2", "i3", "i4", "i5"])
    res = compute_long_tail_metrics(
        df, mock_model, eval_users=["u_1", "u_2"], tail_percentile=0.8, k=5
    )

    assert res["total_items"] == 5
    assert res["tail_item_count"] == 4
    assert res["tail_interaction_volume_share"] == 0.50
    # In mock model, top 5 recs are [i1, i2, i3, i4, i5] -> 4 out of 5 in tail (80%)
    assert res["tail_recommendation_share_at_k"] == 0.80


def test_extract_item_categories_handles_diverse_formats() -> None:
    """Verify category extraction across arrays, lists, strings, and missing values."""
    items = pd.DataFrame(
        [
            {"item_id": "i1", "categories": ["Guitars", "Acoustic"]},
            {"item_id": "i2", "categories": ("Drums", "Cymbals")},
            {"item_id": "i3", "categories": "Synthesizers"},
            {"item_id": "i4", "categories": []},
            {"item_id": "i5", "categories": None},
        ]
    )
    cats = extract_item_categories(items)
    assert cats["i1"] == {"Guitars", "Acoustic"}
    assert cats["i2"] == {"Drums", "Cymbals"}
    assert cats["i3"] == {"Synthesizers"}
    assert cats["i4"] == set()
    assert cats["i5"] == set()


def test_category_diversity_metrics() -> None:
    """Verify mean unique categories computation for top-k recommendations."""
    items = pd.DataFrame(
        [
            {"item_id": "i1", "categories": ["CatA", "CatB"]},
            {"item_id": "i2", "categories": ["CatB", "CatC"]},
            {"item_id": "i3", "categories": ["CatD"]},
        ]
    )
    mock_model = MockProductModel(item_ids=["i1", "i2", "i3"])
    div = compute_category_diversity_metrics(mock_model, items, eval_users=["u1", "u2"], k=3)

    assert div["k"] == 3
    # Both users get [i1, i2, i3] -> categories are {CatA, CatB, CatC, CatD} -> 4 unique
    assert div["mean_unique_categories"] == 4.0
    assert div["min_unique_categories"] == 4
    assert div["max_unique_categories"] == 4


def test_similar_alternatives_spot_check_passes_on_shared_categories() -> None:
    """Verify spot check passes when similar items share category."""
    items = pd.DataFrame(
        [
            {"item_id": "i1", "categories": ["Guitars", "Acoustic"]},
            {"item_id": "i2", "categories": ["Guitars", "Electric"]},
            {"item_id": "i3", "categories": ["Guitars", "Accessories"]},
        ]
    )
    mock_model = MockProductModel(item_ids=["i1", "i2", "i3"])
    check = compute_similar_alternatives_spot_check(
        mock_model, items, num_query_products=2, k_similar=2, target_threshold=0.60
    )

    assert check["passed"] is True
    assert check["shared_category_rate"] == 1.0


def test_similar_alternatives_spot_check_fails_on_disjoint_categories() -> None:
    """Verify spot check fails when similar items share zero categories."""
    items = pd.DataFrame(
        [
            {"item_id": "i1", "categories": ["Guitars"]},
            {"item_id": "i2", "categories": ["Flutes"]},
            {"item_id": "i3", "categories": ["Drums"]},
        ]
    )
    mock_model = MockProductModel(item_ids=["i1", "i2", "i3"])
    check = compute_similar_alternatives_spot_check(
        mock_model, items, num_query_products=2, k_similar=2, target_threshold=0.60
    )

    assert check["passed"] is False
    assert check["shared_category_rate"] == 0.0


@pytest.mark.real_data
def test_real_products_artifacts_contain_valid_checks() -> None:
    """Verify saved products metrics.json contains product_specific_checks meeting all gates."""
    import json

    metrics_p = REPO_ROOT / "artifacts" / "products" / "metrics.json"
    if not metrics_p.exists():
        pytest.skip("artifacts/products/metrics.json not generated yet")

    metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
    assert "product_specific_checks" in metrics, (
        "Missing product_specific_checks key in metrics.json"
    )

    checks = metrics["product_specific_checks"]
    assert "sparse_data" in checks
    assert "long_tail" in checks
    assert "category_diversity" in checks
    assert "similar_alternatives_spot_check" in checks

    sd = checks["sparse_data"]
    assert sd["total_users"] > 0
    assert 0.0 < sd["sparse_user_ratio"] < 1.0

    lt = checks["long_tail"]
    assert lt["total_items"] > 0
    assert 0.0 < lt["tail_interaction_volume_share"] < 1.0

    cd = checks["category_diversity"]
    assert cd["mean_unique_categories"] > 0.0

    sa = checks["similar_alternatives_spot_check"]
    assert sa["passed"] is True
    assert sa["shared_category_rate"] >= 0.60
