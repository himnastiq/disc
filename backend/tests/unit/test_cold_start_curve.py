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
