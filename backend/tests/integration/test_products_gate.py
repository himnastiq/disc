"""Phase 4 Gate and 'break your own work' ritual (P4.8).

Rigorous gate checks and adversarial tests for the Products pipeline:
1. String ID and ASIN integrity: String IDs (reviewerID, ASIN) served seamlessly without coercion failure.
2. Metadata fallback robustness: Missing metadata gracefully defaults title=id and category=['General'].
3. Item budget cap invariance: SAR similarity adheres strictly to max_items_in_similarity budget.
4. Future temporal leakage isolation: Future test items never leak into popularity or similarity.
5. Seen items exclusion: Seen items strictly excluded, even under popularity fallback.
6. Real Products artifacts validation: Manifest SHA-256 integrity, R1-R5 invariants, and product-specific checks.
7. Core unchanged invariant: Confirms zero modifications to engine core abstractions across Phase 4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add tools to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from core_unchanged import check_core_unchanged  # noqa: E402

from engine.adapters.amazon import AmazonProductsAdapter  # noqa: E402
from engine.artifacts import load_artifacts, verify_artifacts  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.demo_users import compute_pairwise_jaccard  # noqa: E402
from engine.evaluation.checks import (  # noqa: E402
    check_r1_data_validity,
    check_r2_no_leakage,
    check_r3_model_invariants,
    check_r4_evaluation_validity,
)
from engine.models.baselines import PopularityModel  # noqa: E402
from engine.models.sar import SarModel  # noqa: E402


@pytest.fixture(scope="module")
def products_spec():
    """Load fast products config for gate testing."""
    return load_config("products", fast=True)


@pytest.fixture(scope="module")
def synthetic_products_split():
    """Create a synthetic products dataset with string ASINs and future test items."""
    train_asins = [f"B0000{i:05d}" for i in range(1, 31)]
    future_asins = [f"B0099{i:05d}" for i in range(1, 11)]
    all_asins = train_asins + future_asins

    items_df = pd.DataFrame(
        [
            {
                "item_id": asin,
                "title": f"Musical Instrument {asin}",
                "categories": ["Musical Instruments", "Guitars"],
                "price": 49.99,
                "brand": "Fender",
                "image_url": f"http://ecx.images-amazon.com/images/{asin}.jpg",
            }
            for asin in all_asins
        ]
    )

    base_ts = 1_400_000_000
    train_rows = []
    for u in range(1, 11):
        uid = f"A{u:010d}REV"
        for offset in range(10):
            item_num = ((u - 1) * 3 + offset) % 30 + 1
            asin = f"B0000{item_num:05d}"
            train_rows.append(
                {
                    "user_id": uid,
                    "item_id": asin,
                    "signal": 5.0,
                    "timestamp": base_ts + (u * 1000) + offset,
                }
            )
    train_df = pd.DataFrame(train_rows)

    future_ts = base_ts + 2_000_000
    test_rows = []
    for u in range(1, 11):
        uid = f"A{u:010d}REV"
        for idx in range(1, 11):
            asin = f"B0099{idx:05d}"
            test_rows.append(
                {
                    "user_id": uid,
                    "item_id": asin,
                    "signal": 5.0,
                    "timestamp": future_ts + (u * 1000) + idx,
                }
            )
    test_df = pd.DataFrame(test_rows)

    return train_df, test_df, items_df


@pytest.mark.integration
def test_gate_string_id_and_asin_integrity(
    products_spec,
    synthetic_products_split,
) -> None:
    """RITUAL 1: Verify alphanumeric string IDs (ASINs, reviewer IDs) serve without type distortion."""
    train_df, _, items_df = synthetic_products_split

    sar_model = SarModel(products_spec)
    sar_model.fit(train_df, items_df)

    # Invariants on string IDs
    test_uid = "A0000000001REV"
    recs = sar_model.recommend_user(user_id=test_uid, k=5)
    cat_set = set(items_df["item_id"])
    user_seen = sar_model.user_seen.get(test_uid, set())
    check_r3_model_invariants(recs=recs, k=5, catalogue=cat_set, exclude_ids=user_seen)

    for r in recs:
        assert isinstance(r.item_id, str), f"item_id must be str, got {type(r.item_id)}"
        assert r.item_id.startswith("B0000"), f"Expected ASIN prefix, got {r.item_id}"

    # Cold start with string ASINs as (item_id, signal) tuples
    cold_history = [
        ("B000000001", 5.0),
        ("B000000002", 4.0),
    ]
    cold_recs = sar_model.recommend_history(cold_history, k=5)
    assert len(cold_recs) == 5
    for cr in cold_recs:
        assert isinstance(cr.item_id, str)
        assert cr.item_id not in {"B000000001", "B000000002"}, "History items leaked into cold recs"


@pytest.mark.integration
def test_gate_metadata_fallback_robustness(products_spec) -> None:
    """RITUAL 2: Verify adapter metadata missing fields gracefully fall back without crashes."""
    spec = products_spec.model_copy(deep=True)
    spec.dataset.min_user_interactions = 1
    spec.dataset.min_item_interactions = 1
    adapter = AmazonProductsAdapter(spec)

    # Mock raw loader returning reviews with one item lacking metadata and one with empty title
    mock_reviews = [
        {"user_id": "u1", "item_id": "B00MISSINGMETA", "signal": 5.0, "timestamp": 1000},
        {"user_id": "u1", "item_id": "B00EMPTYTITLE", "signal": 4.0, "timestamp": 1001},
        {"user_id": "u2", "item_id": "B00NORMALITEM", "signal": 5.0, "timestamp": 1002},
    ]
    mock_meta = {
        "B00EMPTYTITLE": {"title": "", "categories": []},
        "B00NORMALITEM": {
            "title": "Normal Acoustic Guitar",
            "categories": ["Musical Instruments", "Guitars"],
        },
    }

    adapter.load_raw = lambda _: {"reviews": mock_reviews, "metadata": mock_meta}  # type: ignore[assignment]
    items = adapter.items()

    item_dict = {row["item_id"]: row for _, row in items.iterrows()}

    # Missing metadata item
    assert "B00MISSINGMETA" in item_dict
    assert item_dict["B00MISSINGMETA"]["title"] == "B00MISSINGMETA"
    assert item_dict["B00MISSINGMETA"]["categories"] == ["General"]

    # Empty title item
    assert "B00EMPTYTITLE" in item_dict
    assert item_dict["B00EMPTYTITLE"]["title"] == "B00EMPTYTITLE"

    # Normal item
    assert "B00NORMALITEM" in item_dict
    assert item_dict["B00NORMALITEM"]["title"] == "Normal Acoustic Guitar"


@pytest.mark.integration
def test_gate_budget_capping_invariance(
    products_spec,
    synthetic_products_split,
) -> None:
    """RITUAL 3: Verify max_items_in_similarity budget cap strictly restricts similarity size."""
    train_df, _, items_df = synthetic_products_split

    # Set aggressive cap of 10 items in serving config
    spec_capped = products_spec.model_copy(deep=True)
    spec_capped.serving.max_items_in_similarity = 10

    sar_model = SarModel(spec_capped)
    sar_model.fit(train_df, items_df)

    assert sar_model.sar is not None
    assert len(sar_model.sar.item2index) == 10
    sim = sar_model.sar.item_similarity
    assert sim.shape == (10, 10)


@pytest.mark.integration
def test_gate_future_temporal_leakage_isolation(
    products_spec,
    synthetic_products_split,
) -> None:
    """RITUAL 4: Verify future viral products never leak into train popularity or similarity."""
    train_df, test_df, items_df = synthetic_products_split
    check_r2_no_leakage(train_df, test_df)

    pop_model = PopularityModel(products_spec)
    pop_model.fit(train_df, items_df)

    sar_model = SarModel(products_spec)
    sar_model.fit(train_df, items_df)

    future_asins = {f"B0099{i:05d}" for i in range(1, 11)}

    pop_recs = {r.item_id for r in pop_model.popular(k=10)}
    sar_recs = {r.item_id for r in sar_model.popular(k=10)}

    assert pop_recs.isdisjoint(future_asins), "Future ASINs leaked into PopularityModel!"
    assert sar_recs.isdisjoint(future_asins), "Future ASINs leaked into SAR popular!"


@pytest.mark.integration
def test_gate_seen_items_never_recommended(
    products_spec,
    synthetic_products_split,
) -> None:
    """RITUAL 5: Verify seen items are never recommended even when history matches top popular items."""
    train_df, _, items_df = synthetic_products_split

    sar_model = SarModel(products_spec)
    sar_model.fit(train_df, items_df)

    # Top popular items
    top_pop_ids = [r.item_id for r in sar_model.popular(k=5)]

    # Inject a history that matches exactly the top popular items
    seen_history = [(iid, 5.0) for iid in top_pop_ids]
    recs = sar_model.recommend_history(seen_history, k=5)

    rec_ids = {r.item_id for r in recs}
    assert rec_ids.isdisjoint(set(top_pop_ids)), "History items recommended under popular fallback!"


@pytest.mark.integration
def test_gate_real_products_artifacts_integrity() -> None:
    """RITUAL 6: Verify real products artifacts pass cryptographic verification and gate checks."""
    artifacts_dir = REPO_ROOT / "artifacts" / "products"
    if not artifacts_dir.exists():
        pytest.skip("artifacts/products directory not found")

    # 1. Cryptographic manifest verification
    manifest = verify_artifacts(artifacts_dir)
    assert manifest["content_type"] == "products"
    assert manifest["model_name"] == "sar"

    # 2. Load artifacts
    loaded = load_artifacts(artifacts_dir)
    assert not loaded.items.empty
    assert not loaded.interactions.empty
    assert not loaded.users.empty

    # 3. R1 report verification on real interactions and items
    check_r1_data_validity(loaded.interactions, loaded.items)

    # 4. R4 metrics verification
    metrics = loaded.metrics
    check_r4_evaluation_validity(metrics)
    assert metrics["content_type"] == "products"
    assert metrics["sanity_checks"]["model_beats_popularity"] is True

    # 5. Product-specific checks verification (P4.6)
    assert "product_specific_checks" in metrics
    p_checks = metrics["product_specific_checks"]
    assert p_checks["sparse_data"]["sparse_user_ratio"] > 0.0
    assert p_checks["long_tail"]["tail_item_count"] == 720
    assert p_checks["category_diversity"]["mean_unique_categories"] > 0.0
    assert p_checks["similar_alternatives_spot_check"]["passed"] is True
    assert p_checks["similar_alternatives_spot_check"]["shared_category_rate"] >= 0.60

    # 6. Diverse demo users pairwise Jaccard < 0.5 (P3.11/P4.5)
    demo_users = loaded.demo_users
    assert len(demo_users) >= 4
    if loaded.topn is not None and not loaded.topn.empty:
        user_top10 = {}
        for uid, grp in loaded.topn.groupby("user_id"):
            user_top10[str(uid)] = set(grp.sort_values(by="rank").head(10)["item_id"].astype(str))

        demo_ids = [d["user_id"] for d in demo_users if d["user_id"] in user_top10]
        for i in range(len(demo_ids)):
            for j in range(i + 1, len(demo_ids)):
                jacc = compute_pairwise_jaccard(user_top10[demo_ids[i]], user_top10[demo_ids[j]])
                assert jacc < 0.5, (
                    f"Pairwise Jaccard >= 0.5 between demo users {demo_ids[i]} and {demo_ids[j]}"
                )


@pytest.mark.integration
def test_gate_core_unchanged_invariant() -> None:
    """RITUAL 7: Verify core engine abstractions remained 100% untouched across Phase 4."""
    passed, disallowed, core_violations = check_core_unchanged()
    assert passed, (
        f"Core unchanged invariant failed! Core violations: {core_violations}, Disallowed: {disallowed}"
    )
    assert core_violations == [], f"Engine core files were modified: {core_violations}"
    assert disallowed == [], f"Non-allowed files modified: {disallowed}"
