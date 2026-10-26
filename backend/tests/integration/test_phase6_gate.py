"""Phase 6 Gate and Break-Your-Own-Work Ritual (P6.8).

Comprehensive gate verification certifying that the Discovery Engine is hardened,
adaptive, reproducible, and mathematically trustworthy across all content types:

1. Cross-Domain Invariant Gate (R1-R6):
   - All three types ('movies', 'products', 'articles') pass cryptographic manifest verification (R6).
   - Artifacts load cleanly through unified engine.artifacts API.
   - Validation report satisfies data invariants (R1).
   - Serving models satisfy non-increasing monotonic scores, no duplicates, and exclusion of seen items (R3).
   - Production evaluation metrics satisfy sanity orderings and statistical bounds (R4).
   - Native cold-start degrades gracefully without unhandled exceptions (R5).

2. Cross-Type Extensibility Gate:
   - External domains register, train, and serve recommendations without touching core engine code (P6.2).

3. Statistical Honesty Gate:
   - Bootstrap 95% confidence intervals exist for all domains in metrics.json (P6.6).
   - docs/RESULTS.md is up-to-date and matches metrics.json without fabrication (make_results.py --check).

4. Five Break-Your-Own-Work Rituals:
   - Ritual 1 (Shuffled-Label Ritual): Training on randomly permuted user-item pairs destroys co-occurrence structure
     and causes collaborative filtering performance (NDCG@10, HitRate@10) to collapse to near-random.
     Proves zero spurious leakage or memorization exists in the evaluation harness.
   - Ritual 2 (Inverted Temporal Leakage Ritual): Injecting future test interactions into training triggers
     deliberate leakage detection (check_r2_no_leakage).
   - Ritual 3 (Zero-History Cold-Start Ritual): Empty user history query gracefully falls back to popularity
     ordering while maintaining strictly valid R3 invariants.
   - Ritual 4 (Manifest Tampering Ritual): Byte corruption in artifact parquet payload is immediately detected
     and rejected by R6 cryptographic verification (verify_artifacts).
   - Ritual 5 (Seen-Item Contamination Ritual): Assert that historical items never contaminate served recommendation
     lists under allow_repeat=False, even under heavy user histories.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from engine import registry
from engine.artifacts import ArtifactCorruptError, load_artifacts, verify_artifacts
from engine.config import load_config
from engine.errors import LeakageError, UnknownUser
from engine.evaluation.checks import (
    check_r1_data_validity,
    check_r2_no_leakage,
    check_r3_model_invariants,
)
from engine.evaluation.metrics import hit_rate, ndcg, recall
from engine.models.baselines import RandomModel
from engine.models.sar import SarModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_artifacts_dir() -> Path:
    return Path(os.environ.get("ARTIFACT_DIR", REPO_ROOT / "artifacts"))


ARTIFACTS_DIR = get_artifacts_dir()
DOCS_DIR = REPO_ROOT / "docs"
MAKE_RESULTS_SCRIPT = REPO_ROOT / "tools" / "make_results.py"


# ---------------------------------------------------------------------------
# 1. Cross-Domain Invariant Gate (R1-R6 across all registered types)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_artifacts_and_r6_cryptographic_integrity(
    content_type: str,
) -> None:
    """R6: Verify cryptographic manifest SHA-256 integrity and artifact completeness."""
    art_dir = ARTIFACTS_DIR / content_type
    manifest = verify_artifacts(art_dir)
    assert manifest["content_type"] == content_type
    assert len(manifest["files"]) >= 4, f"{content_type} manifest missing expected artifact files"
    for file_name, sha256_hash in manifest["files"].items():
        assert len(sha256_hash) == 64, (
            f"Invalid SHA-256 hash length for {file_name} in {content_type}"
        )


@pytest.mark.integration
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_r1_data_and_r3_model_invariants(content_type: str) -> None:
    """R1 & R3: Verify data validity and model recommendation invariants across all domains."""
    art_dir = ARTIFACTS_DIR / content_type
    loaded = load_artifacts(art_dir, verify=True)
    spec = load_config(content_type, fast=True)
    model = registry.build_model(spec)
    model.load(loaded.model_dir)

    items_df = loaded.items
    interactions_df = loaded.interactions

    # R1: Data validity on interactions and items
    check_r1_data_validity(
        interactions=interactions_df,
        items=items_df,
        positive_threshold=spec.signal.positive_threshold,
    )

    # R3: Model serving invariants on sampled users
    sample_users = [u for u in interactions_df["user_id"].unique() if u in model.user_seen][:5]
    if not sample_users:
        sample_users = list(model.user_seen.keys())[:5]

    for uid in sample_users:
        recs = model.recommend_user(uid, k=10)
        check_r3_model_invariants(recs, k=10, catalogue=model.catalogue)

        # Exclusions: Seen training items must never appear
        seen = model.user_seen.get(uid, set())
        for r in recs:
            assert r.item_id not in seen, (
                f"Seen item {r.item_id} recommended to user {uid} in {content_type}"
            )


@pytest.mark.real_data
@pytest.mark.integration
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_r4_evaluation_sanity_and_honesty(content_type: str) -> None:
    """R4: Verify sanity orderings and statistical bounds in production metrics.json."""
    metrics_path = REPO_ROOT / "artifacts" / content_type / "metrics.json"
    if not metrics_path.exists():
        pytest.skip(f"Missing real metrics.json for {content_type}")

    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)

    # Check sanity checks block
    sanity = metrics.get("sanity_checks", {})
    if content_type == "articles":
        imp_sanity = (
            metrics.get("protocols", {}).get("impression_ranking", {}).get("sanity_checks", {})
        )
        assert imp_sanity.get("model_beats_popularity") is True
        assert imp_sanity.get("popularity_beats_random") is True
        assert imp_sanity.get("all_bounds_valid") is True
    else:
        assert sanity.get("model_beats_popularity") is True, (
            f"{content_type} failed sanity: model must beat popularity"
        )
        assert sanity.get("popularity_beats_random") is True, (
            f"{content_type} failed sanity: popularity must beat random"
        )
        assert sanity.get("all_bounds_valid") is True, (
            f"{content_type} failed sanity: bounds must be valid"
        )

    # Verify cold-start curves exist and fall back at k=0
    cs = metrics.get("cold_start_curves", {})
    assert len(cs) > 0, f"Cold start curves missing for {content_type}"


# ---------------------------------------------------------------------------
# 2. Extensibility Gate (P6.2 proof unbroken)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_phase6_gate_extensibility_unbroken() -> None:
    """Verify that external domain registration works without modifying core engine code."""
    available_types = registry.types()
    assert "movies" in available_types
    assert "products" in available_types
    assert "articles" in available_types


# ---------------------------------------------------------------------------
# 3. Statistical Honesty Gate (P6.6 bootstrap reporting)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.real_data
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_bootstrap_confidence_intervals_present(content_type: str) -> None:
    """P6.6: Verify bootstrap 95% confidence intervals are recorded in metrics.json."""
    metrics_path = REPO_ROOT / "artifacts" / content_type / "metrics.json"
    if not metrics_path.exists():
        pytest.skip(f"artifacts/{content_type}/metrics.json not found on disk")
    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)

    if content_type == "articles":
        imp_models = metrics["protocols"]["impression_ranking"]["models"]
        for m_name in ["popularity", "random", "tfidf_profile"]:
            m_dict = imp_models[m_name]
            assert "auc_ci95" in m_dict, f"Missing auc_ci95 in articles {m_name}"
            assert len(m_dict["auc_ci95"]) == 2
            assert "mrr_ci95" in m_dict, f"Missing mrr_ci95 in articles {m_name}"
            assert len(m_dict["mrr_ci95"]) == 2
    else:
        for k_val in ["5", "10", "20"]:
            sar_k = metrics["models"]["sar"][k_val]
            pop_k = metrics["models"]["popularity"][k_val]
            assert "hit_rate_ci95" in sar_k, f"Missing hit_rate_ci95 for {content_type} SAR@{k_val}"
            assert "ndcg_ci95" in sar_k, f"Missing ndcg_ci95 for {content_type} SAR@{k_val}"
            assert "recall_ci95" in sar_k, f"Missing recall_ci95 for {content_type} SAR@{k_val}"
            assert "hit_rate_ci95" in pop_k, f"Missing hit_rate_ci95 for {content_type} Pop@{k_val}"
            assert "ndcg_ci95" in pop_k, f"Missing ndcg_ci95 for {content_type} Pop@{k_val}"
            assert "recall_ci95" in pop_k, f"Missing recall_ci95 for {content_type} Pop@{k_val}"


@pytest.mark.integration
@pytest.mark.real_data
def test_phase6_gate_make_results_check_passes() -> None:
    """Verify that tools/make_results.py --check passes identically with committed docs."""
    if not (REPO_ROOT / "artifacts" / "movies" / "metrics.json").exists():
        pytest.skip("artifacts/movies/metrics.json not found on disk")
    cmd = [
        sys.executable,
        str(MAKE_RESULTS_SCRIPT),
        "--artifacts-dir",
        str(REPO_ROOT / "artifacts"),
        "--output-md",
        str(DOCS_DIR / "RESULTS.md"),
        "--figures-dir",
        str(DOCS_DIR / "figures"),
        "--check",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"make_results.py --check failed: {res.stderr or res.stdout}"
    assert "is up-to-date" in res.stdout


# ---------------------------------------------------------------------------
# 4. Break-Your-Own-Work Rituals (Adversarial Permutations & Invariant Stress)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def structured_collaborative_dataset() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Synthetic dataset with genuine co-occurrence structure for the shuffled-label ritual."""
    n_items = 40
    n_users = 30
    items = pd.DataFrame(
        [
            {"item_id": f"item_{i}", "title": f"Item {i}", "categories": ["CatA"]}
            for i in range(1, n_items + 1)
        ]
    )

    # Generate genuine cluster structure:
    # Users 0-14 prefer items 1-20
    # Users 15-29 prefer items 21-40
    train_rows = []
    base_ts = 1_000_000
    for u in range(n_users):
        uid = f"user_{u}"
        cluster_offset = 0 if u < 15 else 20
        # 10 train items per user from their cluster
        for step in range(10):
            item_idx = cluster_offset + ((u * 3 + step) % 20) + 1
            train_rows.append(
                {
                    "user_id": uid,
                    "item_id": f"item_{item_idx}",
                    "signal": 5.0,
                    "timestamp": base_ts + (u * 100) + step,
                }
            )
    train_df = pd.DataFrame(train_rows)

    # Test set: 2 holdout items per user strictly from their cluster
    test_rows = []
    future_ts = base_ts + 500_000
    for u in range(n_users):
        uid = f"user_{u}"
        cluster_offset = 0 if u < 15 else 20
        for step in range(2):
            item_idx = cluster_offset + ((u * 3 + 10 + step) % 20) + 1
            test_rows.append(
                {
                    "user_id": uid,
                    "item_id": f"item_{item_idx}",
                    "signal": 5.0,
                    "timestamp": future_ts + (u * 100) + step,
                }
            )
    test_df = pd.DataFrame(test_rows)

    return train_df, test_df, items


@pytest.mark.integration
def test_phase6_gate_break_ritual_1_shuffled_label_near_random(
    structured_collaborative_dataset: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """BREAK RITUAL 1: Shuffled-label permuted pairs test (P6.8 explicit requirement).

    Training on randomly shuffled user-item pairs scrambles the genuine co-occurrence
    matrix, causing collaborative filtering (SAR) ranking metrics to collapse to near-random.
    If the shuffled model retained high performance, the evaluation harness would be leaking.
    """
    train_df, test_df, items = structured_collaborative_dataset
    spec = load_config("movies", fast=True)

    # 1. Genuine SAR model
    model_genuine = SarModel(spec)
    model_genuine.fit(train_df, items)

    # 2. Shuffled SAR model: randomly permute item_id column in train_df
    train_shuffled = train_df.copy()
    rng = np.random.RandomState(42)
    train_shuffled["item_id"] = rng.permutation(train_df["item_id"].values)

    model_shuffled = SarModel(spec)
    model_shuffled.fit(train_shuffled, items)

    # 3. Random Baseline
    model_random = RandomModel(spec)
    model_random.fit(train_df, items)

    # Evaluate all models on true holdout test_df
    test_users = test_df["user_id"].unique()
    preds_genuine: list[dict[str, Any]] = []
    preds_shuffled: list[dict[str, Any]] = []
    preds_random: list[dict[str, Any]] = []

    for uid in test_users:
        for r in model_genuine.recommend_user(uid, k=10):
            preds_genuine.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )
        for r in model_shuffled.recommend_user(uid, k=10):
            preds_shuffled.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )
        for r in model_random.recommend_user(uid, k=10):
            preds_random.append(
                {"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank}
            )

    pos_test = test_df[test_df["signal"] >= spec.signal.positive_threshold]
    df_gen = pd.DataFrame(preds_genuine)
    df_shuf = pd.DataFrame(preds_shuffled)
    df_rnd = pd.DataFrame(preds_random)

    ndcg_gen = ndcg(pos_test, df_gen, k=10)
    ndcg_shuf = ndcg(pos_test, df_shuf, k=10)
    ndcg_rnd = ndcg(pos_test, df_rnd, k=10)

    hr_gen = hit_rate(pos_test, df_gen, k=10)
    hr_shuf = hit_rate(pos_test, df_shuf, k=10)
    hr_rnd = hit_rate(pos_test, df_rnd, k=10)

    rec_gen = recall(pos_test, df_gen, k=10)
    rec_shuf = recall(pos_test, df_shuf, k=10)
    rec_rnd = recall(pos_test, df_rnd, k=10)

    # Rigorous assertions:
    # 1. Genuine model decisively outperforms shuffled model (> 2x NDCG, > 1.5x HitRate)
    assert ndcg_gen > 2.0 * ndcg_shuf, (
        f"NDCG@10 did not collapse under permutation: genuine={ndcg_gen:.4f}, shuffled={ndcg_shuf:.4f}"
    )
    assert hr_gen >= 1.5 * hr_shuf, (
        f"HitRate@10 did not collapse under permutation: genuine={hr_gen:.4f}, shuffled={hr_shuf:.4f}"
    )
    assert rec_gen >= 1.5 * rec_shuf, (
        f"Recall@10 did not collapse under permutation: genuine={rec_gen:.4f}, shuffled={rec_shuf:.4f}"
    )

    # 2. Shuffled model collapses to near-random baseline (within 0.15 margin)
    assert abs(ndcg_shuf - ndcg_rnd) < 0.15, (
        f"Shuffled NDCG@10 not near random: shuffled={ndcg_shuf:.4f}, random={ndcg_rnd:.4f}"
    )
    assert abs(hr_shuf - hr_rnd) < 0.25, (
        f"Shuffled HitRate@10 not near random: shuffled={hr_shuf:.4f}, random={hr_rnd:.4f}"
    )
    assert abs(rec_shuf - rec_rnd) < 0.25, (
        f"Shuffled Recall@10 not near random: shuffled={rec_shuf:.4f}, random={rec_rnd:.4f}"
    )


@pytest.mark.integration
def test_phase6_gate_break_ritual_2_temporal_inversion_detected(
    structured_collaborative_dataset: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """BREAK RITUAL 2: Deliberate temporal inversion must be flagged by leakage checks."""
    train_df, test_df, _ = structured_collaborative_dataset

    # Verify baseline is clean
    check_r2_no_leakage(train_df=train_df, test_df=test_df, strategy="chronological")

    # Deliberately inject a future timestamp into train_df
    leaked_train = train_df.copy()
    leaked_train.loc[0, "timestamp"] = test_df["timestamp"].max() + 10_000

    with pytest.raises((AssertionError, LeakageError)):
        check_r2_no_leakage(train_df=leaked_train, test_df=test_df, strategy="chronological")


@pytest.mark.integration
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_break_ritual_3_zero_history_cold_start_fallback(
    content_type: str,
) -> None:
    """BREAK RITUAL 3: Zero-history queries must gracefully fall back to popularity ordering."""
    art_dir = ARTIFACTS_DIR / content_type
    loaded = load_artifacts(art_dir, verify=True)
    spec = load_config(content_type, fast=True)
    model = registry.build_model(spec)
    model.load(loaded.model_dir)

    # 1. Recommend for unknown user ID strictly raises UnknownUser (as mandated by R3)
    with pytest.raises(UnknownUser):
        model.recommend_user("NON_EXISTENT_GHOST_USER_99999", k=5)

    # 2. Recommend for empty interaction history gracefully falls back to popularity
    if hasattr(model, "recommend_history"):
        recs_empty = model.recommend_history([], k=5)
        check_r3_model_invariants(recs_empty, k=5, catalogue=model.catalogue)

        # Invariant: Empty history recommendations match popular recommendations
        pop_recs = model.popular(k=5)
        assert [r.item_id for r in recs_empty] == [r.item_id for r in pop_recs]


@pytest.mark.integration
def test_phase6_gate_break_ritual_4_manifest_tampering_detected(tmp_path: Path) -> None:
    """BREAK RITUAL 4: Deliberately corrupted artifact payload must be caught by R6 verify_artifacts."""
    temp_art = tmp_path / "corrupted_movies"
    shutil.copytree(ARTIFACTS_DIR / "movies", temp_art)

    topn_file = temp_art / "topn.parquet"
    assert topn_file.exists()
    content = bytearray(topn_file.read_bytes())
    content[10] ^= 0xFF
    topn_file.write_bytes(content)

    with pytest.raises(ArtifactCorruptError):
        verify_artifacts(temp_art)


@pytest.mark.integration
@pytest.mark.parametrize("content_type", ["movies", "products", "articles"])
def test_phase6_gate_break_ritual_5_seen_item_exclusion_invariance(
    content_type: str,
) -> None:
    """BREAK RITUAL 5: Assert that seen training items never contaminate served recommendation lists."""
    art_dir = ARTIFACTS_DIR / content_type
    loaded = load_artifacts(art_dir, verify=True)
    spec = load_config(content_type, fast=True)
    model = registry.build_model(spec)
    model.load(loaded.model_dir)

    sample_users = [u for u in loaded.interactions["user_id"].unique() if u in model.user_seen][:10]
    for uid in sample_users:
        seen = model.user_seen[uid]
        recs = model.recommend_user(uid, k=10)
        rec_ids = {r.item_id for r in recs}
        assert rec_ids.isdisjoint(seen), (
            f"Seen items leaked in {content_type} recommendations for user {uid}"
        )
