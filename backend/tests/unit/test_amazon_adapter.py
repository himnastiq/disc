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
    """Verify max_items_in_similarity item cap keeps top items by train popularity post-split (P4.2 / F-002)."""
    spec = load_config("products", fast=True)
    # Configure tight cap of 2 items
    spec.serving.max_items_in_similarity = 2

    adapter = AmazonProductsAdapter(spec, raw_dir=amazon_fixture_dir)
    train_df, _valid_df, _test_df = adapter.split()

    # Train split must be capped at exactly 2 items by train popularity
    assert len(train_df["item_id"].unique()) == 2

    # item_1 and item_2 have the most reviews by construction
    expected_top2 = {"item_1", "item_2"}
    assert set(train_df["item_id"].unique()) == expected_top2


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


def test_parse_dict_line_rejects_arbitrary_code_execution(tmp_path: Path) -> None:
    """F-001: Assert that _parse_dict_line never executes arbitrary Python code."""
    from engine.adapters.amazon import _parse_dict_line

    marker_file = tmp_path / "pwned_marker.txt"
    # Construct an exploit string that tries to create marker_file
    escaped_path = str(marker_file).replace("\\", "\\\\")
    malicious_payload = f"__import__('pathlib').Path('{escaped_path}').write_text('PWNED')"

    result = _parse_dict_line(malicious_payload)

    # Must be safely rejected/ignored and return None
    assert result is None
    # CRITICAL: The code must NOT have executed, so marker_file must NOT exist!
    assert not marker_file.exists(), "SECURITY VULNERABILITY: eval() executed malicious payload!"

    # Break-your-own-fix edge cases:
    # 1. Malicious lambda embedded in dictionary
    assert _parse_dict_line("{'asin': (lambda: 'B002')()}") is None
    # 2. Empty or whitespace line
    assert _parse_dict_line("") is None
    assert _parse_dict_line("   \n\t  ") is None
    # 3. Valid JSON with unicode characters
    parsed_json = _parse_dict_line('{"asin": "B001", "title": "Guitar \u2014 Caf\u00e9"}')
    assert parsed_json == {"asin": "B001", "title": "Guitar — Café"}
    # 4. Valid single-quoted dict literal with unicode
    parsed_single = _parse_dict_line("{'asin': 'B001', 'title': 'Guitar — Café'}")
    assert parsed_single == {"asin": "B001", "title": "Guitar — Café"}


def test_amazon_adapter_item_cap_does_not_leak_test_interactions(tmp_path: Path) -> None:
    """F-002: Assert that item cap is determined strictly by train interactions, not test interactions."""
    fixture_dir = tmp_path / "leakage_fixture" / "instruments"
    fixture_dir.mkdir(parents=True)

    meta_file = fixture_dir / "meta_Musical_Instruments.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"asin": "item_train_heavy", "title": "Train Heavy Item"}) + "\n")
        f.write(json.dumps({"asin": "item_test_heavy", "title": "Test Heavy Item"}) + "\n")

    # Reviews: 5 users with 20 interactions each.
    # For each user:
    # First 10 interactions (early ts): item_train_heavy (appears in train split)
    # Next 10 interactions (late ts): item_test_heavy (split between late train and valid/test)
    # With 80% ratio (16 train, 2 valid, 2 test):
    # Train has: 10 item_train_heavy and 6 item_test_heavy per user.
    # Across all 5 users in TRAIN: item_train_heavy has 50 reviews, item_test_heavy has 30 reviews.
    # In VALID+TEST: item_train_heavy has 0 reviews, item_test_heavy has 20 reviews.
    # In addition, we add 10 more late test interactions for item_test_heavy (total 30 in test).
    # Thus:
    # OVERALL: item_test_heavy has 60 reviews, item_train_heavy has 50 reviews.
    # TRAIN-ONLY: item_train_heavy has 50 reviews, item_test_heavy has 30 reviews.
    reviews = []
    base_ts = 1_400_000_000
    for u in range(1, 6):
        uid = f"user_{u}"
        for step in range(20):
            ts = base_ts + (u * 100_000) + (step * 1000)
            iid = "item_train_heavy" if step < 10 else "item_test_heavy"
            reviews.append(
                {
                    "reviewerID": uid,
                    "asin": iid,
                    "overall": 5.0,
                    "unixReviewTime": ts,
                }
            )

    reviews_file = fixture_dir / "reviews_Musical_Instruments_5.json"
    with open(reviews_file, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r) + "\n")

    spec = load_config("products", fast=True)
    spec.serving.max_items_in_similarity = 1
    spec.split.ratio = 0.8

    adapter = AmazonProductsAdapter(spec, raw_dir=fixture_dir.parent)
    train_df, _valid_df, _test_df = adapter.split()

    # The retained item in train_df MUST be item_train_heavy (most popular in train: 50 vs 30)
    # NOT item_test_heavy (which is only popular due to future/test interactions: 60 vs 50 overall)
    retained_train_items = set(train_df["item_id"].unique())
    assert retained_train_items == {"item_train_heavy"}, (
        f"DATA LEAKAGE: item cap selected {retained_train_items} using test interactions instead of train interactions"
    )


def test_amazon_adapter_item_cap_perturbation_invariance(tmp_path: Path) -> None:
    """F-002: Perturbation test - altering/removing test interactions must NOT affect retained train items."""
    d1 = tmp_path / "d1" / "instruments"
    d2 = tmp_path / "d2" / "instruments"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)

    metadata = [
        {"asin": "item_A", "title": "Item A"},
        {"asin": "item_B", "title": "Item B"},
        {"asin": "item_C", "title": "Item C"},
    ]
    for d in (d1, d2):
        meta_file = d / "meta_Musical_Instruments.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            for m in metadata:
                f.write(json.dumps(m) + "\n")

    # Common base reviews: 5 users with 10 reviews in train (0..7) and 2 in test (8..9)
    base_reviews = []
    base_ts = 1_400_000_000
    for u in range(1, 6):
        uid = f"user_{u}"
        for step in range(10):
            ts = base_ts + (u * 100_000) + (step * 1000)
            iid = "item_A" if step < 5 else "item_B"
            base_reviews.append(
                {"reviewerID": uid, "asin": iid, "overall": 5.0, "unixReviewTime": ts}
            )

    # D1 base reviews
    with open(d1 / "reviews_Musical_Instruments_5.json", "w", encoding="utf-8") as f:
        for r in base_reviews:
            f.write(json.dumps(r) + "\n")

    # D2 has perturbed test interactions (the test-period interactions at step 9 are replaced/perturbed with item_C)
    perturbed_reviews = []
    for r in base_reviews:
        r_copy = dict(r)
        # step 9 is the last interaction per user (strictly in the test partition)
        # Perturb it to item_C in D2
        if r["unixReviewTime"] % 100_000 == 9000:
            r_copy["asin"] = "item_C"
        perturbed_reviews.append(r_copy)

    with open(d2 / "reviews_Musical_Instruments_5.json", "w", encoding="utf-8") as f:
        for r in perturbed_reviews:
            f.write(json.dumps(r) + "\n")

    spec = load_config("products", fast=True)
    spec.serving.max_items_in_similarity = 2
    spec.split.ratio = 0.8

    adapter1 = AmazonProductsAdapter(spec, raw_dir=d1.parent)
    train1, _, _ = adapter1.split()

    adapter2 = AmazonProductsAdapter(spec, raw_dir=d2.parent)
    train2, _, _ = adapter2.split()

    # The retained item set in train split must be IDENTICAL between D1 and D2
    items_d1 = set(train1["item_id"].unique())
    items_d2 = set(train2["item_id"].unique())
    assert items_d1 == items_d2, (
        f"Perturbation leak: D1 retained {items_d1} but D2 retained {items_d2}"
    )
