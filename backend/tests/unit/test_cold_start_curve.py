"""Tests for SAR cold-start history degradation curves (P3.10)."""

from __future__ import annotations

import json
from pathlib import Path


def test_movies_metrics_cold_start_curve() -> None:
    """Verify that artifacts/movies/metrics.json contains validated cold_start_curves."""
    metrics_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "artifacts"
        / "movies"
        / "metrics.json"
    )
    assert metrics_path.exists(), "artifacts/movies/metrics.json must exist"

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "cold_start_curves" in data, "metrics.json must have cold_start_curves"
    curves = data["cold_start_curves"]
    assert "sar" in curves, "SAR model must have cold_start_curves"

    sar_curve = curves["sar"]
    history_sizes = sorted([int(k) for k in sar_curve])
    assert 0 in history_sizes, "Must include history size 0 (cold baseline)"
    assert max(history_sizes) >= 5, "Must evaluate multi-item histories"

    # Verify metric structure per size
    for metrics_dict in sar_curve.values():
        assert "hit_rate@10" in metrics_dict
        assert "ndcg@10" in metrics_dict
        assert "recall@10" in metrics_dict
        for val in metrics_dict.values():
            assert 0.0 <= val <= 1.0

    # Verify overall improvement from cold start (0) to warm history (max size)
    max_size_key = str(max(history_sizes))
    assert sar_curve[max_size_key]["recall@10"] >= sar_curve["0"]["recall@10"]
    assert sar_curve[max_size_key]["ndcg@10"] >= sar_curve["0"]["ndcg@10"]


def test_cold_start_at_zero_likes_equals_popularity_baseline() -> None:
    """Verify that at 0 likes, SAR recommendation exactly equals popularity baseline (FIX-18)."""
    import pandas as pd
    from engine.config import load_config
    from engine.evaluation.metrics import hit_rate, ndcg, recall
    from engine.models.baselines import PopularityModel
    from engine.models.sar import SarModel

    spec = load_config("movies", fast=True)
    items_df = pd.DataFrame(
        [{"item_id": f"m{i}", "title": f"Movie {i}", "genres": ["Action"]} for i in range(1, 21)]
    )
    # Train interactions: m1 has 10 hits, m2 has 8, m3 has 6, etc.
    train_rows = []
    for u in range(1, 11):
        uid = f"u{u}"
        for i in range(1, 4):
            train_rows.append({"user_id": uid, "item_id": f"m{i}", "signal": 5.0, "timestamp": 100})
    # Extra train interactions for item popularity
    for u in range(11, 21):
        uid = f"u{u}"
        train_rows.append({"user_id": uid, "item_id": "m1", "signal": 5.0, "timestamp": 100})
        train_rows.append({"user_id": uid, "item_id": "m2", "signal": 5.0, "timestamp": 100})
    train_df = pd.DataFrame(train_rows)

    # Test interactions: u1 has m4 (pos), u2 has m5 (pos)
    test_df = pd.DataFrame(
        [
            {"user_id": "u1", "item_id": "m4", "signal": 5.0, "timestamp": 200},
            {"user_id": "u2", "item_id": "m5", "signal": 5.0, "timestamp": 200},
            {"user_id": "u3", "item_id": "m1", "signal": 5.0, "timestamp": 200},
        ]
    )

    pop = PopularityModel(spec)
    pop.fit(train_df, items_df)
    sar = SarModel(spec)
    sar.fit(train_df, items_df)

    eval_users = ["u1", "u2", "u3"]
    pop_preds = []
    sar_zero_preds = []

    for uid in eval_users:
        user_seen = pop.user_seen.get(uid, set())
        p_recs = pop.recommend_user(uid, k=5)
        s_recs = sar.recommend_history([], k=5, exclude_ids=user_seen)

        # Bit-for-bit identical recommendations
        assert [r.item_id for r in p_recs] == [r.item_id for r in s_recs]
        for r in p_recs:
            pop_preds.append({"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank})
        for r in s_recs:
            sar_zero_preds.append({"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank})

    pos_test = test_df[test_df["signal"] >= 4.0]
    df_pop = pd.DataFrame(pop_preds)
    df_sar0 = pd.DataFrame(sar_zero_preds)

    r_pop = recall(pos_test, df_pop, k=5)
    r_sar0 = recall(pos_test, df_sar0, k=5)
    n_pop = ndcg(pos_test, df_pop, k=5)
    n_sar0 = ndcg(pos_test, df_sar0, k=5)
    h_pop = hit_rate(pos_test, df_pop, k=5)
    h_sar0 = hit_rate(pos_test, df_sar0, k=5)

    assert r_pop == r_sar0
    assert n_pop == n_sar0
    assert h_pop == h_sar0

