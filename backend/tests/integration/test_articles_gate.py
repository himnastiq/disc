"""Discovery Engine - Phase 5 Gate and Break-Your-Own-Work Ritual (P5.12).

Asserts all Phase 5 Gate invariants for news articles:
- R1 Data validity: validation report matches dataset properties.
- R2 No leakage: impression time split strictly preserves temporal boundaries.
- R3 Model invariants: monotonic score order, no duplicate items, seen items excluded, fresh window compliance.
- R4 Dual-protocol evaluation validity: impression ranking (MIND) + retrieval pool.
- R5 Cold start: native cold-start consistency and faithful attribution.
- R6 Reproducibility: SHA-256 cryptographic manifest verified on disk.
- Break-your-own-work ritual:
  1. Leaked test impression isolation: unobserved test articles do not leak into train vocabulary.
  2. Freshness recency window boundary: articles outside active window are never recommended.
  3. Multilingual and malformed text resilience: zero crashes on non-English scripts.
  4. Ghost history items isolation: unknown catalogue IDs dropped cleanly without crashing.
  5. Core engine unchanged check: core abstractions preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.artifacts import load_artifacts
from engine.config import load_config
from engine.evaluation.checks import (
    check_r1_data_validity,
    check_r2_no_leakage,
    check_r3_model_invariants,
)
from engine.models.tfidf import TfidfProfileModel
from engine.registry import get_adapter

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "articles"


@pytest.mark.integration
def test_gate_r1_data_validity_and_report() -> None:
    """R1: Verify articles dataset validation report conforming to schema."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    report = adapter.validate()

    assert report.total_interactions > 0
    assert report.unique_users > 0
    assert report.unique_items > 0
    assert 0.0 <= report.sparsity <= 1.0
    assert report.max_timestamp >= report.min_timestamp

    inter = adapter.interactions()
    items = adapter.items()
    check_r1_data_validity(
        interactions=inter,
        items=items,
        positive_threshold=spec.signal.positive_threshold,
    )


@pytest.mark.integration
def test_gate_r2_no_leakage_impression_time_split() -> None:
    """R2: Verify impression time split enforces max(train.timestamp) <= min(test.timestamp)."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    train_df, valid_df, test_df = adapter.split()

    check_r2_no_leakage(
        train_df=train_df,
        valid_df=valid_df,
        test_df=test_df,
        strategy="impression_time",
    )

    t_max = train_df["timestamp"].max()
    t_min_test = test_df["timestamp"].min()
    assert t_max <= t_min_test, f"Temporal leakage: train max {t_max} > test min {t_min_test}"


@pytest.mark.integration
def test_gate_r3_model_invariants_and_freshness() -> None:
    """R3: Verify monotonic scores, seen exclusion, and freshness window compliance."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    train_df, _, _ = adapter.split()
    items = adapter.items()

    model = TfidfProfileModel(spec)
    model.fit(train_df, items)

    for uid in list(model.user_history.keys())[:5]:
        recs = model.recommend_user(uid, k=5)
        check_r3_model_invariants(recs, k=5, catalogue=model.catalogue)

        # Freshness invariant: all recommendations must belong to fresh window
        if model.fresh_candidates is not None:
            for r in recs:
                assert r.item_id in model.fresh_candidates, (
                    f"Recommended item {r.item_id} is outside fresh recency window"
                )

        # Seen items invariant: seen items never recommended
        seen = model.user_seen.get(uid, set())
        for r in recs:
            assert r.item_id not in seen, f"Seen item {r.item_id} recommended to user {uid}"


@pytest.mark.integration
@pytest.mark.real_data
def test_gate_r4_dual_protocol_evaluation_validity() -> None:
    """R4: Verify both impression ranking and window retrieval protocols in metrics.json."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("Missing artifacts/articles/metrics.json")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    # Assert dual protocol architecture
    assert "protocols" in metrics
    assert "impression_ranking" in metrics["protocols"]
    assert "retrieval" in metrics["protocols"]

    # Protocol (a) Impression Ranking checks
    imp_eval = metrics["protocols"]["impression_ranking"]
    assert imp_eval["evaluated_impressions"] > 0
    tfidf_imp = imp_eval["models"]["tfidf_profile"]
    pop_imp = imp_eval["models"]["popularity"]
    rand_imp = imp_eval["models"]["random"]

    # TFIDF profile model must decisively beat Popularity and Random in impression ranking
    assert tfidf_imp["auc"] >= pop_imp["auc"], "TF-IDF model failed to beat popularity AUC"
    assert tfidf_imp["mrr"] >= pop_imp["mrr"], "TF-IDF model failed to beat popularity MRR"
    assert tfidf_imp["auc"] >= rand_imp["auc"], "TF-IDF model failed to beat random AUC"
    assert imp_eval["sanity_checks"]["model_beats_popularity"] is True

    # Protocol (b) Window Retrieval checks
    ret_eval = metrics["protocols"]["retrieval"]
    assert ret_eval["candidate_pool_size"] > 0
    assert "tfidf_profile" in ret_eval["models"]
    assert "popularity" in ret_eval["models"]
    assert "random" in ret_eval["models"]
    assert ret_eval["sanity_checks"]["all_bounds_valid"] is True
    assert ret_eval["sanity_checks"]["popularity_beats_random"] is True


@pytest.mark.integration
@pytest.mark.real_data
def test_gate_r5_cold_start_consistency_and_attribution() -> None:
    """R5: Verify cold start degradation curve and faithful attribution."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("Missing artifacts/articles/metrics.json")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert "cold_start_curves" in metrics
    assert "tfidf_profile" in metrics["cold_start_curves"]

    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    train_df, _, _ = adapter.split()
    items = adapter.items()

    model = TfidfProfileModel(spec)
    model.fit(train_df, items)

    # Cold-start attribution reason test
    first_user = next(iter(model.user_history.keys()))
    user_hist = model.user_history[first_user]
    recs = model.recommend_user(first_user, k=3)

    if recs:
        target_item = recs[0].item_id
        hist_pairs = [(iid, sig) for iid, sig, _ in user_hist]
        reason = model.explain(recommended_item_id=target_item, history=hist_pairs)
        if reason is not None:
            assert reason.item_id in {iid for iid, _ in hist_pairs}, (
                "Reason item must be a member of user history"
            )
            assert "topics:" in reason.text or "Recommended based on" in reason.text


@pytest.mark.integration
@pytest.mark.real_data
def test_gate_r6_real_articles_artifacts_integrity() -> None:
    """R6: Verify cryptographic SHA-256 manifest and complete artifact set on disk."""
    if not (ARTIFACTS_DIR / "manifest.json").exists():
        pytest.skip("Missing artifacts/articles/manifest.json")
    loaded = load_artifacts(ARTIFACTS_DIR)

    assert len(loaded.items) > 0
    assert len(loaded.interactions) > 0
    assert len(loaded.users) > 0
    assert len(loaded.demo_users) >= 4
    assert loaded.topn is not None and len(loaded.topn) > 0
    assert loaded.metrics is not None


# =========================================================================
# BREAK-YOUR-OWN-WORK RITUAL (Phase 5)
# =========================================================================


@pytest.mark.integration
def test_ritual_1_leaked_test_articles_isolation() -> None:
    """RITUAL 1: Verify test-period articles never leak into training TF-IDF vocabulary."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    inter = adapter.interactions()
    items = adapter.items()
    train_df, _, _test_df = adapter.split(inter)

    # Injected unobserved test item with unique future topic
    future_item_id = "N_FUTURE_LEAK"
    future_text = "QuantumSupercomputingLeapX999 Breakthrough Announced"
    future_row = pd.DataFrame(
        [
            {
                "item_id": future_item_id,
                "title": "Quantum Leap Future",
                "categories": ["futuretech"],
                "text": future_text,
            }
        ]
    )
    items_with_future = pd.concat([items, future_row], ignore_index=True)

    # Fit model on training split only
    model = TfidfProfileModel(spec)
    model.fit(train_df, items_with_future)

    # Unique token from future article must NOT exist in model vocabulary
    vocab = model.vectorizer.vocabulary_
    assert "quantumsupercomputingleapx999" not in vocab, (
        "Future test vocabulary leaked into train model!"
    )


@pytest.mark.integration
def test_ritual_2_freshness_recency_window_boundary() -> None:
    """RITUAL 2: Adversarially inject old viral article; verify recency window prevents recommendation."""
    spec = load_config("articles", fast=True)
    items_df = pd.DataFrame(
        [
            {
                "item_id": "N_OLD_VIRAL",
                "title": "Viral Old News",
                "categories": ["news"],
                "text": "Viral Old News",
            },
            {
                "item_id": "N_FRESH_1",
                "title": "Fresh Today News 1",
                "categories": ["news"],
                "text": "Fresh Today News 1",
            },
            {
                "item_id": "N_FRESH_2",
                "title": "Fresh Today News 2",
                "categories": ["news"],
                "text": "Fresh Today News 2",
            },
        ]
    )
    # Old viral article has 100 clicks 10 days ago (outside 24h window)
    now_ts = 1000000
    interactions_df = pd.DataFrame(
        [
            {
                "user_id": f"U_OLD_{i}",
                "item_id": "N_OLD_VIRAL",
                "signal": 1.0,
                "timestamp": now_ts - 200000,
            }
            for i in range(100)
        ]
        + [
            {"user_id": "U_ACTIVE", "item_id": "N_FRESH_1", "signal": 1.0, "timestamp": now_ts},
            {"user_id": "U_ACTIVE", "item_id": "N_FRESH_2", "signal": 1.0, "timestamp": now_ts},
        ]
    )

    model = TfidfProfileModel(spec)
    model.fit(interactions_df, items_df)

    # Fresh candidates must strictly exclude the old viral article
    assert model.fresh_candidates is not None
    assert "N_OLD_VIRAL" not in model.fresh_candidates

    # Recommendations for new user must never include the old viral article
    recs = model.recommend_history([("N_FRESH_1", 1.0)], k=3)
    assert all(r.item_id != "N_OLD_VIRAL" for r in recs)


@pytest.mark.integration
def test_ritual_3_multilingual_and_malformed_text_resilience() -> None:
    """RITUAL 3: Adversarially feed malformed, non-ASCII, and symbol-only articles."""
    spec = load_config("articles", fast=True)
    items_df = pd.DataFrame(
        [
            {"item_id": "N_EMOJI", "title": "🚀🔥🎉", "categories": ["news"], "text": "🚀🔥🎉"},
            {"item_id": "N_PUNCT", "title": "?!@#$%", "categories": ["news"], "text": "?!@#$%"},
            {
                "item_id": "N_ARABIC",
                "title": "مرحبا بالعالم",
                "categories": ["عربي"],
                "text": "مرحبا بالعالم",
            },
        ]
    )
    inter_df = pd.DataFrame(
        [
            {"user_id": "U1", "item_id": "N_EMOJI", "signal": 1.0, "timestamp": 100},
            {"user_id": "U1", "item_id": "N_PUNCT", "signal": 1.0, "timestamp": 200},
            {"user_id": "U2", "item_id": "N_ARABIC", "signal": 1.0, "timestamp": 300},
        ]
    )

    model = TfidfProfileModel(spec)
    # Must fit cleanly without crashing
    model.fit(inter_df, items_df)

    # Must score and recommend cleanly
    recs = model.recommend_user("U1", k=2)
    assert len(recs) > 0


@pytest.mark.integration
def test_ritual_4_ghost_history_isolation() -> None:
    """RITUAL 4: Adversarially query cold start with 100% ghost/non-existent IDs."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    train_df, _, _ = adapter.split()
    items = adapter.items()

    model = TfidfProfileModel(spec)
    model.fit(train_df, items)

    # 100% unknown ghost history
    ghost_history = [("GHOST_ITEM_XYZ_999", 1.0), ("NON_EXISTENT_ARTICLE_123", 1.0)]
    recs = model.recommend_history(ghost_history, k=5)

    assert len(recs) > 0
    # Must fall back gracefully to popular fresh catalogue items
    assert all(r.item_id in model.catalogue for r in recs)


@pytest.mark.integration
def test_ritual_5_core_unchanged_check() -> None:
    """RITUAL 5: Assert that tools/core_unchanged.py succeeds across the entire repository."""
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("Not inside a git repository")
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from core_unchanged import GitHistoryUnavailable, check_core_unchanged

    try:
        passed, disallowed, core_violations = check_core_unchanged()
    except GitHistoryUnavailable as exc:
        pytest.skip(str(exc))

    assert passed, (
        f"Core unchanged check failed: disallowed={disallowed}, violations={core_violations}"
    )
    assert disallowed == []
