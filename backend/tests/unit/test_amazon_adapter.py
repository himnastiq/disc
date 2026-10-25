"""Unit tests for AmazonProductsAdapter (P4.2).

Tests:
1. Metadata joining (title, brand, price, categories, image URL).
2. Missing metadata and missing title fallback (title = item_id, flagged and counted).
3. Minimum interaction filtering (users and items).
4. Item budget cap by popularity to respect max_items_in_similarity.
5. R1 validation report and R2 chronological split invariance on small fixture.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from engine.adapters.amazon import AmazonProductsAdapter
from engine.config import load_config
from engine.evaluation.checks import check_r1_data_validity, check_r2_no_leakage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def amazon_fixture_dir(tmp_path: Path) -> Path:
    """Create a self-contained small fixture directory with reviews and metadata."""
    fixture_dir = tmp_path / "amazon_fixture" / "instruments"
    fixture_dir.mkdir(parents=True)

    metadata_lines = [
        {
            "asin": "item_1",
            "title": "Acoustic Guitar Strings",
            "brand": "D'Addario",
            "price": 12.99,
            "imUrl": "http://img.amazon.com/item1.jpg",
            "categories": [["Musical Instruments", "Guitars", "Strings"]],
        },
        {
            "asin": "item_2",
            "title": "Clip-On Digital Tuner",
            "brand": "Snark",
            "price": 15.50,
            "imUrl": "http://img.amazon.com/item2.jpg",
            "categories": [["Musical Instruments", "Accessories", "Tuners"]],
        },
        {
            "asin": "item_3",
            "title": "Guitar Capo Pro",
            "brand": "Kyser",
            "price": 19.95,
            "imUrl": "http://img.amazon.com/item3.jpg",
            "categories": [["Musical Instruments", "Accessories", "Capos"]],
        },
        {
            "asin": "item_4",
            "title": "Guitar Picks 12-Pack",
            "brand": "Dunlop",
            "price": 5.99,
            "imUrl": "http://img.amazon.com/item4.jpg",
            "categories": [["Musical Instruments", "Guitars", "Picks"]],
        },
        # item_5 intentionally omitted from metadata to test fallback
        {
            "asin": "item_6",
            "title": "",  # Empty title to test fallback
            "brand": "Generic",
            "price": 3.50,
            "categories": [["Musical Instruments"]],
        },
    ]

    meta_file = fixture_dir / "meta_Musical_Instruments.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        for m in metadata_lines:
            f.write(json.dumps(m) + "\n")

    # Reviews: 4 users with 10 interactions each (timestamps ordered per user)
    # Plus user_5 with only 2 reviews to test min_user_interactions filtering
    base_ts = 1_400_000_000
    reviews = []
    items_cycle = ["item_1", "item_2", "item_3", "item_4", "item_5", "item_6"]

    # 4 active users with 10 interactions each
    for u_idx in range(1, 5):
        uid = f"user_{u_idx}"
        for offset in range(10):
            if offset < len(items_cycle):
                iid = items_cycle[offset]
            elif offset % 2 == 0:
                iid = "item_1"
            else:
                iid = "item_2"

            ts = base_ts + (u_idx * 100_000) + (offset * 1000)
            reviews.append(
                {
                    "reviewerID": uid,
                    "asin": iid,
                    "overall": 4.0 if offset % 2 == 0 else 5.0,
                    "unixReviewTime": ts,
                }
            )

    # Inactive user with only 2 interactions
    reviews.append(
        {
            "reviewerID": "user_inactive",
            "asin": "item_1",
            "overall": 5.0,
            "unixReviewTime": base_ts + 10,
        }
    )
    reviews.append(
        {
            "reviewerID": "user_inactive",
            "asin": "item_2",
            "overall": 5.0,
            "unixReviewTime": base_ts + 20,
        }
    )

    rev_file = fixture_dir / "reviews_Musical_Instruments_5.json"
    with open(rev_file, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r) + "\n")

    return fixture_dir.parent


def test_amazon_adapter_metadata_join_and_fallbacks(amazon_fixture_dir: Path) -> None:
    """Verify metadata joining, type coercions, and fallback handling."""
    spec = load_config("products", fast=True)
    adapter = AmazonProductsAdapter(spec, raw_dir=amazon_fixture_dir)

    items = adapter.items()
    interactions = adapter.interactions()

    # Schema column verification
    assert "item_id" in items.columns
    assert "title" in items.columns
    assert "categories" in items.columns
    assert "price" in items.columns
    assert "image_url" in items.columns

    # Verify item_1 joined correctly with metadata
    item_1 = items[items["item_id"] == "item_1"].iloc[0]
    assert item_1["title"] == "Acoustic Guitar Strings"
    assert item_1["brand"] == "D'Addario"
    assert item_1["price"] == 12.99
    assert item_1["image_url"] == "http://img.amazon.com/item1.jpg"
    assert "Guitars" in item_1["categories"]

    # Verify item_5 missing-metadata fallback
    assert adapter.missing_metadata_count >= 1
    item_5 = items[items["item_id"] == "item_5"].iloc[0]
    assert item_5["title"] == "item_5"  # Fallback: title = item_id

    # Verify item_6 empty-title fallback
    assert adapter.missing_titles_count >= 1
    item_6 = items[items["item_id"] == "item_6"].iloc[0]
    assert item_6["title"] == "item_6"

    # Verify interactions format
    assert len(interactions) > 0
    assert pd.api.types.is_string_dtype(interactions["user_id"])
    assert pd.api.types.is_string_dtype(interactions["item_id"])
    assert pd.api.types.is_float_dtype(interactions["signal"])
    assert pd.api.types.is_integer_dtype(interactions["timestamp"])


def test_amazon_adapter_item_cap_by_popularity(amazon_fixture_dir: Path) -> None:
    """Verify max_items_in_similarity item cap keeps top items by popularity (P4.2)."""
    spec = load_config("products", fast=True)
    # Configure tight cap of 2 items
    spec.serving.max_items_in_similarity = 2

    adapter = AmazonProductsAdapter(spec, raw_dir=amazon_fixture_dir)
    items = adapter.items()
    interactions = adapter.interactions()

    # Must be capped at exactly 2 items
    assert len(items) == 2
    assert set(interactions["item_id"].unique()) == set(items["item_id"])

    # item_1 and item_2 have the most reviews by construction
    expected_top2 = {"item_1", "item_2"}
    assert set(items["item_id"]) == expected_top2


def test_amazon_adapter_filtering_and_validation(amazon_fixture_dir: Path) -> None:
    """Verify min_user_interactions and min_item_interactions filtering and R1 validity."""
    spec = load_config("products", fast=True)
    spec.dataset.min_user_interactions = 3  # Inactive user only has 2 interactions

    adapter = AmazonProductsAdapter(spec, raw_dir=amazon_fixture_dir)
    interactions = adapter.interactions()
    items = adapter.items()

    # Inactive user should be filtered out
    assert "user_inactive" not in interactions["user_id"].unique()

    # Validation report
    report = adapter.validate()
    assert report.details["content_type"] == "products"
    assert report.total_interactions == len(interactions)
    assert report.unique_users == interactions["user_id"].nunique()
    assert report.unique_items == len(items)
    assert report.filtered_users >= 1

    # R1 check passes
    check_r1_data_validity(interactions, items)


def test_amazon_adapter_chronological_split_no_leakage(amazon_fixture_dir: Path) -> None:
    """Verify chronological split on Amazon data satisfies R2 no-leakage."""
    spec = load_config("products", fast=True)
    adapter = AmazonProductsAdapter(spec, raw_dir=amazon_fixture_dir)

    train_df, valid_df, test_df = adapter.split()
    assert len(train_df) > 0
    assert len(test_df) > 0

    # R2 no leakage check
    check_r2_no_leakage(train_df, test_df)
    check_r2_no_leakage(train_df, valid_df)
    check_r2_no_leakage(valid_df, test_df)
