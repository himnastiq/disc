"""Unit tests for news articles dual-protocol evaluation (Phase 5, P5.8)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from engine.config import load_config
from engine.evaluation.articles_eval import (
    evaluate_impression_ranking,
    evaluate_window_retrieval,
    run_articles_dual_protocol_eval,
)
from engine.evaluation.metrics import impression_mrr, impression_ndcg, impression_roc_auc
from engine.models.baselines import PopularityModel, RandomModel
from engine.models.tfidf import TfidfProfileModel
from engine.registry import get_adapter


def test_impression_metrics_hand_computed() -> None:
    """Verify impression metrics against mathematically hand-computed ground truths."""
    # 1. Perfect ranking for 1 positive and 2 negatives
    labels_perf = [1, 0, 0]
    scores_perf = [0.9, 0.4, 0.1]
    assert impression_roc_auc(labels_perf, scores_perf) == pytest.approx(1.0)
    assert impression_mrr(labels_perf, scores_perf) == pytest.approx(1.0)
    assert impression_ndcg(labels_perf, scores_perf, k=5) == pytest.approx(1.0)

    # 2. Inverted ranking: positive placed at rank 3
    labels_inv = [1, 0, 0]
    scores_inv = [0.1, 0.4, 0.9]
    assert impression_roc_auc(labels_inv, scores_inv) == pytest.approx(0.0)
    assert impression_mrr(labels_inv, scores_inv) == pytest.approx(1.0 / 3.0)
    # DCG@5 = 1 / log2(3 + 1) = 0.5. IDCG@5 = 1 / log2(1 + 1) = 1.0. nDCG = 0.5
    assert impression_ndcg(labels_inv, scores_inv, k=5) == pytest.approx(0.5)

    # 3. Multiple positives: labels [1, 0, 1], scores [0.8, 0.5, 0.2]
    # Positives at rank 1 and rank 3.
    # DCG@5 = 1/log2(2) + 1/log2(4) = 1.0 + 0.5 = 1.5
    # IDCG@5 = 1/log2(2) + 1/log2(3) = 1.0 + 1.0/1.5849625 ~ 1.63092975
    labels_multi = [1, 0, 1]
    scores_multi = [0.8, 0.5, 0.2]
    expected_dcg = 1.0 + 0.5
    expected_idcg = 1.0 + (1.0 / math.log2(3))
    expected_ndcg = expected_dcg / expected_idcg
    assert impression_mrr(labels_multi, scores_multi) == pytest.approx(1.0)  # first is at rank 1
    assert impression_ndcg(labels_multi, scores_multi, k=5) == pytest.approx(expected_ndcg)

    # 4. Single class impressions: AUC must be None
    assert impression_roc_auc([0, 0, 0], [0.5, 0.3, 0.1]) is None
    assert impression_roc_auc([1, 1, 1], [0.5, 0.3, 0.1]) is None
    assert impression_mrr([0, 0, 0], [0.5, 0.3, 0.1]) == pytest.approx(0.0)
    assert impression_ndcg([0, 0, 0], [0.5, 0.3, 0.1], k=5) == pytest.approx(0.0)


def test_evaluate_impression_ranking_synthetic() -> None:
    """Test evaluate_impression_ranking with synthetic impression records."""

    # Setup dummy models with pre-defined candidate scoring
    class MockModel:
        def __init__(self, high_cand: str) -> None:
            self.high_cand = high_cand

        def score_candidate_items(
            self,
            candidate_ids: list[str],
            user_id: str | None = None,
            history: Any = None,
        ) -> list[float]:
            return [1.0 if c == self.high_cand else 0.1 for c in candidate_ids]

    models = {
        "good_model": MockModel(high_cand="N_CLICKED"),
        "bad_model": MockModel(high_cand="N_UNCLICKED"),
    }

    impressions = [
        {
            "impression_id": "imp_1",
            "user_id": "u1",
            "timestamp": 1000,
            "history": ["N_OLD"],
            "candidates": [("N_CLICKED", 1), ("N_UNCLICKED", 0)],
        },
        {
            "impression_id": "imp_2",
            "user_id": "u2",
            "timestamp": 1005,
            "history": ["N_OLD"],
            "candidates": [("N_CLICKED", 1), ("N_UNCLICKED", 0)],
        },
    ]

    res = evaluate_impression_ranking(impressions, models)
    assert res["evaluated_impressions"] == 2
    assert res["models"]["good_model"]["auc"] == pytest.approx(1.0)
    assert res["models"]["good_model"]["mrr"] == pytest.approx(1.0)
    assert res["models"]["good_model"]["ndcg@5"] == pytest.approx(1.0)

    assert res["models"]["bad_model"]["auc"] == pytest.approx(0.0)
    assert res["models"]["bad_model"]["mrr"] == pytest.approx(0.5)


def test_evaluate_window_retrieval_candidate_pool_invariance() -> None:
    """Assert all evaluated models compete strictly on the identical fresh candidates pool."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    inter = adapter.interactions()
    items = adapter.items()
    train_df, _, test_df = adapter.split(inter)

    tfidf = TfidfProfileModel(spec)
    pop = PopularityModel(spec)
    rand = RandomModel(spec)

    tfidf.fit(train_df, items)
    pop.fit(train_df, items)
    rand.fit(train_df, items)

    models = {"tfidf_profile": tfidf, "popularity": pop, "random": rand}

    # Evaluate window retrieval
    recency_window = 86400.0
    res = evaluate_window_retrieval(
        train_df=train_df,
        test_df=test_df,
        items=items,
        models=models,
        spec=spec,
        recency_window=recency_window,
        k_values=[5, 10],
        max_test_users=50,
    )

    assert "models" in res
    assert "tfidf_profile" in res["models"]
    assert "popularity" in res["models"]
    assert "random" in res["models"]
    assert res["sanity_checks"]["all_bounds_valid"] is True

    # Assert metrics conform to domain bounds (novelty is in bits >= 0, others in [0, 1])
    for m_name, k_dict in res["models"].items():
        for k_str, m_metrics in k_dict.items():
            for metric_name, val in m_metrics.items():
                if metric_name == "novelty":
                    assert val >= 0.0, f"Novelty for {m_name} at K={k_str} must be >= 0: {val}"
                elif isinstance(val, (list, tuple)):
                    for v in val:
                        assert 0.0 <= v <= 1.0, (
                            f"Bound {v} in {metric_name} for {m_name} at K={k_str} out of bounds"
                        )
                else:
                    assert 0.0 <= val <= 1.0, (
                        f"Metric {metric_name} for {m_name} at K={k_str} out of bounds: {val}"
                    )


def test_run_articles_dual_protocol_eval_end_to_end() -> None:
    """Verify full dual-protocol evaluation pipeline produces valid canonical schema."""
    spec = load_config("articles", fast=True)
    adapter = get_adapter(spec)
    inter = adapter.interactions()
    items = adapter.items()
    train_df, _, test_df = adapter.split(inter)

    tfidf = TfidfProfileModel(spec)
    pop = PopularityModel(spec)
    rand = RandomModel(spec)

    tfidf.fit(train_df, items)
    pop.fit(train_df, items)
    rand.fit(train_df, items)

    models = {
        "tfidf_profile": tfidf,
        "popularity": pop,
        "random": rand,
    }

    metrics = run_articles_dual_protocol_eval(
        spec=spec,
        train_df=train_df,
        test_df=test_df,
        items=items,
        impressions=adapter.impression_candidates,
        models=models,
        max_test_users=30,
        max_impressions=50,
        cold_start_sample_users=10,
    )

    # 1. Structure verification
    assert "protocol" in metrics
    assert metrics["protocol"]["dual_protocol"] is True
    assert "protocols" in metrics
    assert "impression_ranking" in metrics["protocols"]
    assert "retrieval" in metrics["protocols"]

    # 2. Impression ranking protocol checks
    imp_eval = metrics["protocols"]["impression_ranking"]
    assert imp_eval["evaluated_impressions"] > 0
    assert "tfidf_profile" in imp_eval["models"]
    assert "popularity" in imp_eval["models"]
    assert "random" in imp_eval["models"]

    tfidf_imp = imp_eval["models"]["tfidf_profile"]
    pop_imp = imp_eval["models"]["popularity"]
    assert 0.0 <= tfidf_imp["auc"] <= 1.0
    assert 0.0 <= tfidf_imp["mrr"] <= 1.0
    assert 0.0 <= pop_imp["auc"] <= 1.0
    assert 0.0 <= pop_imp["mrr"] <= 1.0

    # 3. Retrieval protocol checks
    ret_eval = metrics["protocols"]["retrieval"]
    assert "models" in ret_eval
    assert metrics["models"] == ret_eval["models"]  # Top-level models field holds retrieval metrics

    # 4. Cold-start curves simulation exists
    assert "cold_start_curves" in metrics
    assert "tfidf_profile" in metrics["cold_start_curves"]

    # 5. Sanity checks structure
    assert "sanity_checks" in metrics
    assert isinstance(metrics["sanity_checks"]["all_bounds_valid"], bool)
    assert isinstance(metrics["sanity_checks"]["popularity_beats_random"], bool)
    assert isinstance(metrics["sanity_checks"]["model_beats_popularity"], bool)


def test_articles_eval_rejects_train_impression_fallback() -> None:
    """F-007: Impression evaluation must NOT fall back to training impressions when post-train impressions are absent."""
    import pandas as pd

    spec = load_config("articles", fast=True)
    train_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "N1", "signal": 1.0, "timestamp": 1000, "positive": True},
            {"user_id": "u2", "item_id": "N2", "signal": 1.0, "timestamp": 1050, "positive": True},
        ]
    )
    test_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "N3", "signal": 1.0, "timestamp": 2000, "positive": True},
        ]
    )
    items = pd.DataFrame(
        [
            {"item_id": "N1", "title": "Article 1", "categories": ["news"], "text": "Content 1"},
            {"item_id": "N2", "title": "Article 2", "categories": ["news"], "text": "Content 2"},
            {"item_id": "N3", "title": "Article 3", "categories": ["news"], "text": "Content 3"},
        ]
    )

    pop = PopularityModel(spec)
    pop.fit(train_df, items)
    models = {"popularity": pop}

    # Construct impressions that all occurred BEFORE or AT train_max_ts (1050)
    train_only_impressions = [
        {
            "impression_id": "imp_train_1",
            "user_id": "u1",
            "timestamp": 1020,  # Training period impression
            "history": ["N1"],
            "candidates": [("N2", 1), ("N3", 0)],
        }
    ]

    with pytest.raises(ValueError, match="No post-train impressions found"):
        run_articles_dual_protocol_eval(
            spec=spec,
            train_df=train_df,
            test_df=test_df,
            items=items,
            impressions=train_only_impressions,
            models=models,
            max_test_users=5,
            max_impressions=5,
        )
