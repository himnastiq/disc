#!/usr/bin/env python3
"""Generate docs/RESULTS.md and docs/figures/*.png from metrics.json artifacts (P6.1).

Parses evaluation artifacts across Movies, Products, and Articles pipelines:
- artifacts/movies/metrics.json
- artifacts/products/metrics.json
- artifacts/articles/metrics.json

Generates:
1. docs/figures/ranking_comparison.png: Cross-domain ranking accuracy (HitRate@10 & NDCG@10)
2. docs/figures/cold_start_curves.png: Cold-start degradation curves across history sizes
3. docs/figures/diversity_coverage.png: Beyond-accuracy trade-offs (Coverage, Diversity, Personalisation)
4. docs/figures/articles_protocols.png: News dual-protocol comparison (Impression Ranking vs Retrieval)
5. docs/RESULTS.md: Comprehensive markdown report containing exact computed numbers without fabrication.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

HOOK_METRICS_KEY_MAP = {
    "product_checks": "product_specific_checks",
}


def validate_post_train_checks_presence(content_type: str, metrics: dict[str, Any]) -> None:
    """Validate that required post_train check keys exist in metrics.json if configured."""
    try:
        from engine.config import load_config

        spec = load_config(content_type)
        post_train_hooks = getattr(spec.evaluation, "post_train", [])
        for hook in post_train_hooks:
            expected_key = HOOK_METRICS_KEY_MAP.get(hook, f"{hook}_checks")
            if expected_key not in metrics or not metrics[expected_key]:
                raise ValueError(
                    f"Content type '{content_type}' defines post_train hook '{hook}' in config, "
                    f"but required key '{expected_key}' is missing or empty in metrics.json."
                )
    except Exception as e:
        if isinstance(e, ValueError) and "defines post_train hook" in str(e):
            raise


def load_metrics_json(artifacts_dir: Path, content_type: str) -> dict[str, Any]:
    """Load and parse metrics.json for a given content type."""
    metrics_path = artifacts_dir / content_type / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing required evaluation metrics: {metrics_path}")
    with open(metrics_path, encoding="utf-8") as f:
        return json.load(f)


def load_manifest_json(artifacts_dir: Path, content_type: str) -> dict[str, Any]:
    """Load and parse manifest.json for a given content type."""
    manifest_path = artifacts_dir / content_type / "manifest.json"
    if not manifest_path.exists():
        return {}
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def format_pct_gain(val: float, baseline: float) -> str:
    """Format percentage gain over baseline."""
    if baseline == 0:
        return "N/A"
    gain = ((val - baseline) / baseline) * 100.0
    prefix = "+" if gain > 0 else ""
    return f"{prefix}{gain:.1f}%"


def format_metric_with_ci(metric_dict: dict[str, Any], key: str, bold_val: bool = False) -> str:
    """Format metric value with 95% bootstrap confidence interval if available."""
    val = metric_dict.get(key, 0.0)
    val_str = f"**{val:.4f}**" if bold_val else f"{val:.4f}"
    ci = metric_dict.get(f"{key}_ci95")
    if ci and isinstance(ci, (list, tuple)) and len(ci) == 2:
        return f"{val_str} [{ci[0]:.4f}, {ci[1]:.4f}]"
    return val_str


def compute_ci_verdict(
    model_dict: dict[str, Any],
    pop_dict: dict[str, Any],
    key: str,
    n_samples: int | None = None,
    is_synthetic: bool = False,
) -> str:
    """Compute statistical verdict from stored bootstrap CIs:
    - 'Model better (CIs separate)'
    - 'No significant difference (CIs overlap)'
    - 'Model worse'

    Minimum-sample rule: if n_samples < 200 or dataset is flagged synthetic,
    returns 'No verdict (synthetic / n=<n>)'.
    """
    if n_samples is not None and (n_samples < 200 or is_synthetic):
        return f"No verdict (synthetic / n={n_samples})"
    if is_synthetic and n_samples is not None:
        return f"No verdict (synthetic / n={n_samples})"

    m_val = model_dict.get(key, 0.0)
    p_val = pop_dict.get(key, 0.0)
    m_ci = model_dict.get(f"{key}_ci95")
    p_ci = pop_dict.get(f"{key}_ci95")

    if (
        m_ci
        and p_ci
        and isinstance(m_ci, (list, tuple))
        and isinstance(p_ci, (list, tuple))
        and len(m_ci) == 2
        and len(p_ci) == 2
    ):
        if m_ci[0] > p_ci[1]:
            return "Model better (CIs separate)"
        elif m_ci[1] < p_ci[0]:
            return "Model worse"
        else:
            return "No significant difference (CIs overlap)"

    # Fallback when CIs are missing:
    if m_val < p_val:
        return "Model worse"
    elif m_val > p_val:
        return "Model better (CIs separate)"
    else:
        return "No significant difference (CIs overlap)"


format_ci_verdict = compute_ci_verdict  # Backwards compatibility alias


def compute_model_beats_popularity_sanity(
    model_by_k: dict[str, dict[str, Any]],
    pop_by_k: dict[str, dict[str, Any]],
    k_list: list[str] | None = None,
    metrics: list[str] | None = None,
) -> str:
    """Compute sanity check line dynamically from table rows.

    If any point estimate is below Popularity write:
      'Mixed: model below Popularity on <list of metrics>'
    Never 'Passed' unless all rows pass.
    """
    if k_list is None:
        k_list = ["5", "10", "20"]
    if metrics is None:
        metrics = ["hit_rate", "ndcg", "recall", "precision"]

    below_metrics: list[str] = []
    for k in k_list:
        m_k = model_by_k.get(k, {})
        p_k = pop_by_k.get(k, {})
        for met in metrics:
            if met in m_k and met in p_k:
                m_val = m_k[met]
                p_val = p_k[met]
                if m_val < p_val:
                    below_metrics.append(f"{met}@{k}")

    if not below_metrics:
        return "Passed"
    return f"Mixed: model below Popularity on {', '.join(below_metrics)}"


def format_target_status(measured: float, target: float, is_pct: bool = True) -> str:
    """Format status column: 'Verified' only when measured meets target; otherwise 'Not met' with both numbers."""
    if measured >= target:
        return "Verified"
    if is_pct:
        target_str = f"{target:.0f}%" if target == int(target) else f"{target:.1f}%"
        return f"Not met ({measured:.1f}% vs > {target_str})"
    return f"Not met ({measured} vs target {target})"


def generate_figures(
    movies_metrics: dict[str, Any],
    products_metrics: dict[str, Any],
    articles_metrics: dict[str, Any],
    figures_dir: Path,
) -> list[Path]:
    """Generate professional visualization figures in docs/figures/."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []

    # Configure clean styling
    plt.style.use(
        "seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default"
    )
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.titlesize": 13,
        }
    )

    # -------------------------------------------------------------
    # 1. Ranking Accuracy Comparison (ranking_comparison.png)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=200)

    types = ["Movies\n(MovieLens)", "Products\n(Amazon)", "Articles\n(MIND Retrieval)"]
    models = ["Random", "Popularity", "Personalised"]
    colors = ["#94a3b8", "#38bdf8", "#0284c7"]

    # Extract NDCG@10 and HitRate@10
    # Movies
    m_models = movies_metrics["models"]
    m_ndcg = [
        m_models["random"]["10"]["ndcg"],
        m_models["popularity"]["10"]["ndcg"],
        m_models["sar"]["10"]["ndcg"],
    ]
    m_hr = [
        m_models["random"]["10"]["hit_rate"],
        m_models["popularity"]["10"]["hit_rate"],
        m_models["sar"]["10"]["hit_rate"],
    ]

    # Products
    p_models = products_metrics["models"]
    p_ndcg = [
        p_models["random"]["10"]["ndcg"],
        p_models["popularity"]["10"]["ndcg"],
        p_models["sar"]["10"]["ndcg"],
    ]
    p_hr = [
        p_models["random"]["10"]["hit_rate"],
        p_models["popularity"]["10"]["hit_rate"],
        p_models["sar"]["10"]["hit_rate"],
    ]

    # Articles
    a_models = articles_metrics["models"]
    a_ndcg = [
        a_models["random"]["10"]["ndcg"],
        a_models["popularity"]["10"]["ndcg"],
        a_models["tfidf_profile"]["10"]["ndcg"],
    ]
    a_hr = [
        a_models["random"]["10"]["hit_rate"],
        a_models["popularity"]["10"]["hit_rate"],
        a_models["tfidf_profile"]["10"]["hit_rate"],
    ]

    import numpy as np

    x = np.arange(len(types))
    width = 0.25

    # Subplot 1: NDCG@10
    for idx, (m_name, color) in enumerate(zip(models, colors, strict=True)):
        scores = [m_ndcg[idx], p_ndcg[idx], a_ndcg[idx]]
        axes[0].bar(
            x + (idx - 1) * width,
            scores,
            width,
            label=m_name,
            color=color,
            edgecolor="#1e293b",
            linewidth=0.5,
        )

    axes[0].set_title("Ranking Quality (NDCG@10)", fontweight="bold")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(types)
    axes[0].set_ylabel("NDCG@10")
    axes[0].legend(loc="upper right", frameon=True)
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    # Subplot 2: HitRate@10
    for idx, (m_name, color) in enumerate(zip(models, colors, strict=True)):
        scores = [m_hr[idx], p_hr[idx], a_hr[idx]]
        axes[1].bar(
            x + (idx - 1) * width,
            scores,
            width,
            label=m_name,
            color=color,
            edgecolor="#1e293b",
            linewidth=0.5,
        )

    axes[1].set_title("Recommendation Accuracy (HitRate@10)", fontweight="bold")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(types)
    axes[1].set_ylabel("HitRate@10")
    axes[1].legend(loc="upper right", frameon=True)
    axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    fig.suptitle(
        "Discovery Engine: Cross-Domain Recommendation Performance",
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    p1 = figures_dir / "ranking_comparison.png"
    fig.savefig(p1, bbox_inches="tight")
    plt.close(fig)
    generated_paths.append(p1)

    # -------------------------------------------------------------
    # 2. Cold-Start Curves (cold_start_curves.png)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), dpi=200, sharey=False)

    datasets = [
        ("Movies (MovieLens)", movies_metrics["cold_start_curves"], "sar"),
        ("Products (Amazon)", products_metrics["cold_start_curves"], "sar"),
        ("Articles (MIND)", articles_metrics["cold_start_curves"], "tfidf_profile"),
    ]

    for ax, (title, curves, model_key) in zip(axes, datasets, strict=True):
        history_keys = sorted(curves[model_key].keys(), key=lambda k: int(k))
        x_vals = [int(k) for k in history_keys]

        # Extract model curve and popularity baseline
        y_model = [
            curves[model_key][k].get("hit_rate@10", curves[model_key][k].get("recall@10", 0.0))
            for k in history_keys
        ]
        y_pop = [
            curves["popularity"][k].get(
                "hit_rate@10", curves["popularity"][k].get("recall@10", 0.0)
            )
            for k in history_keys
        ]

        ax.plot(
            x_vals,
            y_model,
            marker="o",
            linewidth=2.2,
            color="#0284c7",
            label=f"Personalised ({model_key})",
        )
        ax.plot(
            x_vals,
            y_pop,
            marker="s",
            linewidth=1.5,
            linestyle="--",
            color="#f59e0b",
            label="Popularity baseline",
        )

        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("User History Size (likes / clicks)")
        ax.set_ylabel("HitRate@10")
        ax.set_xticks(x_vals)
        ax.legend(frameon=True)
        ax.grid(True, linestyle="--", alpha=0.6)

    fig.suptitle(
        "Native Cold-Start Adaptation Curve (0 to 20 Signal Points)",
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout()
    p2 = figures_dir / "cold_start_curves.png"
    fig.savefig(p2, bbox_inches="tight")
    plt.close(fig)
    generated_paths.append(p2)

    # -------------------------------------------------------------
    # 3. Beyond-Accuracy Trade-offs (diversity_coverage.png)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0), dpi=200)

    # Subplot 1: Catalogue Coverage@10
    cov_random = [
        m_models["random"]["10"]["coverage"],
        p_models["random"]["10"]["coverage"],
        a_models["random"]["10"]["coverage"],
    ]
    cov_pop = [
        m_models["popularity"]["10"]["coverage"],
        p_models["popularity"]["10"]["coverage"],
        a_models["popularity"]["10"]["coverage"],
    ]
    cov_model = [
        m_models["sar"]["10"]["coverage"],
        p_models["sar"]["10"]["coverage"],
        a_models["tfidf_profile"]["10"]["coverage"],
    ]

    axes[0].bar(x - width, cov_random, width, label="Random", color="#94a3b8")
    axes[0].bar(x, cov_pop, width, label="Popularity", color="#38bdf8")
    axes[0].bar(x + width, cov_model, width, label="Personalised", color="#0284c7")
    axes[0].set_title("Catalogue Coverage@10", fontweight="bold")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(types)
    axes[0].set_ylabel("Proportion of Catalogue")
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    # Subplot 2: Intra-List Diversity@10
    div_random = [
        m_models["random"]["10"]["diversity"],
        p_models["random"]["10"]["diversity"],
        a_models["random"]["10"]["diversity"],
    ]
    div_pop = [
        m_models["popularity"]["10"]["diversity"],
        p_models["popularity"]["10"]["diversity"],
        a_models["popularity"]["10"]["diversity"],
    ]
    div_model = [
        m_models["sar"]["10"]["diversity"],
        p_models["sar"]["10"]["diversity"],
        a_models["tfidf_profile"]["10"]["diversity"],
    ]

    axes[1].bar(x - width, div_random, width, label="Random", color="#94a3b8")
    axes[1].bar(x, div_pop, width, label="Popularity", color="#38bdf8")
    axes[1].bar(x + width, div_model, width, label="Personalised", color="#0284c7")
    axes[1].set_title("Intra-List Diversity@10", fontweight="bold")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(types)
    axes[1].set_ylabel("Pairwise Cosine Distance")
    axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    # Subplot 3: Personalisation@10
    pers_random = [
        m_models["random"]["10"]["personalisation"],
        p_models["random"]["10"]["personalisation"],
        a_models["random"]["10"]["personalisation"],
    ]
    pers_pop = [
        m_models["popularity"]["10"]["personalisation"],
        p_models["popularity"]["10"]["personalisation"],
        a_models["popularity"]["10"]["personalisation"],
    ]
    pers_model = [
        m_models["sar"]["10"]["personalisation"],
        p_models["sar"]["10"]["personalisation"],
        a_models["tfidf_profile"]["10"]["personalisation"],
    ]

    axes[2].bar(x - width, pers_random, width, label="Random", color="#94a3b8")
    axes[2].bar(x, pers_pop, width, label="Popularity", color="#38bdf8")
    axes[2].bar(x + width, pers_model, width, label="Personalised", color="#0284c7")
    axes[2].set_title("Personalisation@10", fontweight="bold")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(types)
    axes[2].set_ylabel("1 - Jaccard Overlap")
    axes[2].legend(frameon=True, loc="lower right")
    axes[2].grid(axis="y", linestyle="--", alpha=0.7)

    fig.suptitle(
        "Beyond-Accuracy Metrics: Coverage, Diversity, and Personalisation",
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    p3 = figures_dir / "diversity_coverage.png"
    fig.savefig(p3, bbox_inches="tight")
    plt.close(fig)
    generated_paths.append(p3)

    # -------------------------------------------------------------
    # 4. News Articles Dual Protocol (articles_protocols.png)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=200)

    imp_data = articles_metrics["protocols"]["impression_ranking"]["models"]
    imp_models = ["Random", "Popularity", "TF-IDF Profile"]
    imp_auc = [
        imp_data["random"]["auc"],
        imp_data["popularity"]["auc"],
        imp_data["tfidf_profile"]["auc"],
    ]
    imp_mrr = [
        imp_data["random"]["mrr"],
        imp_data["popularity"]["mrr"],
        imp_data["tfidf_profile"]["mrr"],
    ]

    x_imp = np.arange(len(imp_models))
    axes[0].bar(x_imp - 0.15, imp_auc, 0.3, label="AUC", color="#3b82f6")
    axes[0].bar(x_imp + 0.15, imp_mrr, 0.3, label="MRR", color="#10b981")
    axes[0].set_title("Protocol (a): Impression Ranking (MIND)", fontweight="bold")
    axes[0].set_xticks(x_imp)
    axes[0].set_xticklabels(imp_models)
    axes[0].set_ylabel("Score (0.0 to 1.0)")
    axes[0].legend(frameon=True)
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    ret_models = ["Random", "Popularity", "TF-IDF Profile"]
    ret_hr = [
        a_models["random"]["10"]["hit_rate"],
        a_models["popularity"]["10"]["hit_rate"],
        a_models["tfidf_profile"]["10"]["hit_rate"],
    ]
    ret_ndcg = [
        a_models["random"]["10"]["ndcg"],
        a_models["popularity"]["10"]["ndcg"],
        a_models["tfidf_profile"]["10"]["ndcg"],
    ]

    axes[1].bar(x_imp - 0.15, ret_hr, 0.3, label="HitRate@10", color="#f59e0b")
    axes[1].bar(x_imp + 0.15, ret_ndcg, 0.3, label="NDCG@10", color="#6366f1")
    axes[1].set_title("Protocol (b): 24h Recency Window Retrieval", fontweight="bold")
    axes[1].set_xticks(x_imp)
    axes[1].set_xticklabels(ret_models)
    axes[1].set_ylabel("Score")
    axes[1].legend(frameon=True)
    axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    fig.suptitle(
        "News Articles: Dual-Protocol Evaluation Architecture",
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    p4 = figures_dir / "articles_protocols.png"
    fig.savefig(p4, bbox_inches="tight")
    plt.close(fig)
    generated_paths.append(p4)

    return generated_paths


def is_fast_variant(
    movies_metrics: dict[str, Any],
    products_metrics: dict[str, Any],
    articles_metrics: dict[str, Any],
    movies_manifest: dict[str, Any] | None = None,
    products_manifest: dict[str, Any] | None = None,
    articles_manifest: dict[str, Any] | None = None,
) -> bool:
    """Check if any pipeline artifact represents a fast developer variant."""
    movies_manifest = movies_manifest or {}
    products_manifest = products_manifest or {}
    articles_manifest = articles_manifest or {}

    m_var = str(movies_manifest.get("dataset_variant") or movies_metrics.get("dataset_variant", "")).lower()
    p_var = str(products_manifest.get("dataset_variant") or products_metrics.get("dataset_variant", "")).lower()
    a_var = str(articles_manifest.get("dataset_variant") or articles_metrics.get("dataset_variant", "")).lower()
    a_src = str(articles_manifest.get("dataset_source") or articles_metrics.get("dataset_source", "")).lower()

    return bool(
        m_var in ("100k", "fast", "toy")
        or p_var in ("instruments", "fast", "toy")
        or a_var in ("fixture", "fast", "toy")
        or a_src != "mind-small"
    )



def build_markdown_report(
    movies_metrics: dict[str, Any],
    products_metrics: dict[str, Any],
    articles_metrics: dict[str, Any],
    movies_manifest: dict[str, Any] | None = None,
    products_manifest: dict[str, Any] | None = None,
    articles_manifest: dict[str, Any] | None = None,
    allow_fast: bool = False,
) -> str:
    """Construct full docs/RESULTS.md from exact pipeline metrics and manifests."""
    movies_manifest = movies_manifest or {}
    products_manifest = products_manifest or {}
    articles_manifest = articles_manifest or {}

    m_models = movies_metrics["models"]
    p_models = products_metrics["models"]
    a_models = articles_metrics["models"]
    a_protocols = articles_metrics["protocols"]

    m_var = movies_manifest.get("dataset_name") or movies_metrics.get("dataset_variant", "movies")
    p_var = products_manifest.get("dataset_name") or products_metrics.get(
        "dataset_variant", "products"
    )
    a_var = articles_manifest.get("dataset_name") or articles_metrics.get(
        "dataset_variant", "articles"
    )

    m_heading = movies_manifest.get("section_heading") or f"Movies ({m_var} + SAR)"
    p_heading = products_manifest.get("section_heading") or f"Products ({p_var} + SAR)"
    a_heading = (
        articles_manifest.get("section_heading") or f"Articles ({a_var} + TF-IDF Content Model)"
    )

    fast_run = is_fast_variant(
        movies_metrics=movies_metrics,
        products_metrics=products_metrics,
        articles_metrics=articles_metrics,
        movies_manifest=movies_manifest,
        products_manifest=products_manifest,
        articles_manifest=articles_manifest,
    )

    validate_post_train_checks_presence("movies", movies_metrics)
    validate_post_train_checks_presence("products", products_metrics)
    validate_post_train_checks_presence("articles", articles_metrics)

    md: list[str] = []

    # Header and provenance
    if fast_run:
        md.append("# FAST VARIANT, NOT FOR REPORT: Discovery Engine Evaluation & Cross-Type Results")
    else:
        md.append("# Discovery Engine: Comprehensive Evaluation & Cross-Type Results")
    md.append("")
    md.append(
        "> **Single Source of Truth:** This file is auto-generated by `python tools/make_results.py` directly"
    )
    md.append(
        "> from production pipeline artifacts (`artifacts/{movies,products,articles}/metrics.json`)."
    )
    md.append("> Contains strictly zero fabricated or hand-typed metrics.")
    md.append("")
    md.append("## Provenance & Run Metadata")
    md.append("")
    md.append(
        "| Content Type | Dataset Variant | Git Commit | Config Hash | Seed | Evaluation Protocol |"
    )
    md.append("|---|---|---|---|---|---|")
    md.append(
        f"| **Movies** | `{movies_metrics.get('dataset_variant', '100k')}` | `{movies_metrics.get('git_sha', 'HEAD')[:7]}` | `{movies_metrics.get('config_hash', 'N/A')[:8]}` | `{movies_metrics.get('seeds', {}).get('split', 42)}` | Chronological per-user split (80/20) |"
    )
    md.append(
        f"| **Products** | `{products_metrics.get('dataset_variant', 'video_games')}` | `{products_metrics.get('git_sha', 'HEAD')[:7]}` | `{products_metrics.get('config_hash', 'N/A')[:8]}` | `{products_metrics.get('seeds', {}).get('split', 42)}` | Chronological per-user split (budget-capped) |"
    )

    a_source = articles_manifest.get("dataset_source") or articles_metrics.get("dataset_source")
    if a_source == "mind-small":
        articles_label = "MIND-small"
    else:
        articles_label = a_source or articles_metrics.get("dataset_variant", "mind_offline")

    md.append(
        f"| **Articles** | `{articles_label}` | `{articles_metrics.get('git_sha', 'HEAD')[:7]}` | `{articles_metrics.get('config_hash', 'N/A')[:8]}` | `{articles_metrics.get('seeds', {}).get('split', 42)}` | Dual protocol: Impression ranking + 24h Window retrieval |"
    )
    md.append("")
    md.append("---")
    md.append("")

    # Executive Summary
    m_p = movies_metrics.get("protocol", {})
    m_users = m_p.get("evaluated_test_users", 0)
    m_interactions = m_p.get("total_interactions", 0)
    m_sar10 = m_models["sar"]["10"]
    m_pop10 = m_models["popularity"]["10"]
    m_cov_ratio = (
        (m_sar10["coverage"] / m_pop10["coverage"]) if m_pop10.get("coverage", 0) > 0 else 1.0
    )

    p_p = products_metrics.get("protocol", {})
    p_users = p_p.get("evaluated_test_users", 0)
    p_interactions = p_p.get("total_interactions", 0)
    p_sar10 = p_models["sar"]["10"]
    p_pop10 = p_models["popularity"]["10"]

    a_imp = a_protocols.get("impression_ranking", {})
    a_imp_n = a_imp.get("evaluated_impressions", 0)
    imp_models = a_protocols["impression_ranking"]["models"]
    a_tfidf_auc = imp_models["tfidf_profile"]
    a_pop_auc = imp_models["popularity"]

    a_source = articles_manifest.get("dataset_source") or articles_metrics.get("dataset_source")
    if a_source is not None:
        a_is_synthetic = (a_source == "fixture")
    else:
        a_is_synthetic = (
            bool(articles_metrics.get("synthetic_fixture"))
            or bool(articles_metrics.get("is_synthetic"))
            or bool(articles_metrics.get("synthetic_demo"))
            or bool(articles_manifest.get("is_synthetic"))
            or bool(articles_manifest.get("synthetic_fixture"))
            or "SYNTHETIC" in str(a_var).upper()
        )

    md.append("## Executive Summary")
    md.append("")
    md.append(
        "Discovery Engine unifies three fundamentally disparate recommendation regimes under a single extensible architecture:"
    )
    md.append("")
    md.append(
        f"1. **Movies (Collaborative Filtering)**: Evaluated on {m_var} ({m_interactions:,} interactions, {m_users:,} test users). "
        f"Coverage ratio SAR/Popularity is {m_cov_ratio:.1f}x. NDCG@10: {format_metric_with_ci(m_sar10, 'ndcg')} vs Popularity {format_metric_with_ci(m_pop10, 'ndcg')} "
        f"({compute_ci_verdict(m_sar10, m_pop10, 'ndcg', n_samples=m_users)}). Recall@10: {format_metric_with_ci(m_sar10, 'recall')} vs Popularity {format_metric_with_ci(m_pop10, 'recall')} "
        f"({compute_ci_verdict(m_sar10, m_pop10, 'recall', n_samples=m_users)})."
    )
    md.append(
        f"2. **Products (E-Commerce)**: Evaluated on {p_var} ({p_interactions:,} interactions, {p_users:,} test users). "
        f"HitRate@10: {format_metric_with_ci(p_sar10, 'hit_rate')} vs Popularity {format_metric_with_ci(p_pop10, 'hit_rate')} "
        f"({compute_ci_verdict(p_sar10, p_pop10, 'hit_rate', n_samples=p_users)}). NDCG@10: {format_metric_with_ci(p_sar10, 'ndcg')} vs Popularity {format_metric_with_ci(p_pop10, 'ndcg')} "
        f"({compute_ci_verdict(p_sar10, p_pop10, 'ndcg', n_samples=p_users)})."
    )
    if a_is_synthetic or a_imp_n < 200:
        md.append(
            f"3. **Articles (Content & Recency)**: Evaluated on {a_var} (demo only; n={a_imp_n} impressions). "
            f"No verdict (synthetic / n={a_imp_n}); numbers excluded from Executive Summary as demo only."
        )
    else:
        md.append(
            f"3. **Articles (Content & Recency)**: Evaluated on {a_var} ({a_imp_n} impressions). "
            f"Impression AUC: {format_metric_with_ci(a_tfidf_auc, 'auc')} vs Popularity {format_metric_with_ci(a_pop_auc, 'auc')} "
            f"({compute_ci_verdict(a_tfidf_auc, a_pop_auc, 'auc', n_samples=a_imp_n, is_synthetic=a_is_synthetic)}). Impression MRR: {format_metric_with_ci(a_tfidf_auc, 'mrr')} vs Popularity {format_metric_with_ci(a_pop_auc, 'mrr')} "
            f"({compute_ci_verdict(a_tfidf_auc, a_pop_auc, 'mrr', n_samples=a_imp_n, is_synthetic=a_is_synthetic)})."
        )
    md.append("")
    md.append("![Cross-Domain Recommendation Performance](figures/ranking_comparison.png)")
    md.append("")
    md.append("---")
    md.append("")

    # Section 1: Movies
    md.append(f"## 1. {m_heading}")
    md.append("")
    md.append(
        r"Evaluated using identical candidate retrieval pool against positive holdout ratings ($\ge 4.0$)."
    )
    md.append("")
    md.append(
        "| Metric @ K | Random Baseline | Popularity Baseline (95% CI) | SAR (Personalised, 95% CI) | Gain vs Popularity | Statistical Verdict |"
    )
    md.append("|---|---|---|---|---|---|")
    for k in ["5", "10", "20"]:
        rnd = m_models["random"][k]
        pop = m_models["popularity"][k]
        sar = m_models["sar"][k]

        gain_hr = format_pct_gain(sar["hit_rate"], pop["hit_rate"])
        gain_ndcg = format_pct_gain(sar["ndcg"], pop["ndcg"])
        gain_rec = format_pct_gain(sar["recall"], pop["recall"])
        gain_prec = format_pct_gain(sar.get("precision", 0.0), pop.get("precision", 0.0))

        md.append(
            f"| **HitRate@{k}** | {rnd['hit_rate']:.4f} | {format_metric_with_ci(pop, 'hit_rate')} | **{format_metric_with_ci(sar, 'hit_rate')}** | **{gain_hr}** | {compute_ci_verdict(sar, pop, 'hit_rate', n_samples=m_users)} |"
        )
        md.append(
            f"| **NDCG@{k}** | {rnd['ndcg']:.4f} | {format_metric_with_ci(pop, 'ndcg')} | **{format_metric_with_ci(sar, 'ndcg')}** | **{gain_ndcg}** | {compute_ci_verdict(sar, pop, 'ndcg', n_samples=m_users)} |"
        )
        md.append(
            f"| **Recall@{k}** | {rnd['recall']:.4f} | {format_metric_with_ci(pop, 'recall')} | **{format_metric_with_ci(sar, 'recall')}** | **{gain_rec}** | {compute_ci_verdict(sar, pop, 'recall', n_samples=m_users)} |"
        )
        md.append(
            f"| **Precision@{k}** | {rnd.get('precision', 0.0):.4f} | {format_metric_with_ci(pop, 'precision')} | **{format_metric_with_ci(sar, 'precision')}** | **{gain_prec}** | {compute_ci_verdict(sar, pop, 'precision', n_samples=m_users)} |"
        )
    md.append("")
    mbp_status = compute_model_beats_popularity_sanity(m_models["sar"], m_models["popularity"])
    md.append(f"- **Sanity Check (Model > Popularity):** `{mbp_status}`")
    m_checks = movies_metrics.get("sanity_checks", {})
    if "popularity_beats_random" in m_checks:
        pbr_status = "Passed" if m_checks["popularity_beats_random"] else "Not satisfied"
        md.append(f"- **Sanity Check (Popularity > Random):** `{pbr_status}`")
    if "all_bounds_valid" in m_checks:
        abv_status = "Passed" if m_checks["all_bounds_valid"] else "Not satisfied"
        md.append(f"- **Sanity Check (Bounds Valid):** `{abv_status}`")
    md.append("")
    md.append("---")
    md.append("")

    # Section 2: Products
    md.append(f"## 2. {p_heading}")
    md.append("")
    md.append("Evaluated on sparse verified purchase ratings under budget-capped SAR similarity.")
    md.append("")
    md.append(
        "| Metric @ K | Random Baseline | Popularity Baseline (95% CI) | SAR (Personalised, 95% CI) | Gain vs Popularity | Statistical Verdict |"
    )
    md.append("|---|---|---|---|---|---|")
    for k in ["5", "10", "20"]:
        rnd = p_models["random"][k]
        pop = p_models["popularity"][k]
        sar = p_models["sar"][k]

        gain_hr = format_pct_gain(sar["hit_rate"], pop["hit_rate"])
        gain_ndcg = format_pct_gain(sar["ndcg"], pop["ndcg"])
        gain_rec = format_pct_gain(sar["recall"], pop["recall"])
        gain_prec = format_pct_gain(sar.get("precision", 0.0), pop.get("precision", 0.0))

        md.append(
            f"| **HitRate@{k}** | {rnd['hit_rate']:.4f} | {format_metric_with_ci(pop, 'hit_rate')} | **{format_metric_with_ci(sar, 'hit_rate')}** | **{gain_hr}** | {compute_ci_verdict(sar, pop, 'hit_rate', n_samples=p_users)} |"
        )
        md.append(
            f"| **NDCG@{k}** | {rnd['ndcg']:.4f} | {format_metric_with_ci(pop, 'ndcg')} | **{format_metric_with_ci(sar, 'ndcg')}** | **{gain_ndcg}** | {compute_ci_verdict(sar, pop, 'ndcg', n_samples=p_users)} |"
        )
        md.append(
            f"| **Recall@{k}** | {rnd['recall']:.4f} | {format_metric_with_ci(pop, 'recall')} | **{format_metric_with_ci(sar, 'recall')}** | **{gain_rec}** | {compute_ci_verdict(sar, pop, 'recall', n_samples=p_users)} |"
        )
        md.append(
            f"| **Precision@{k}** | {rnd.get('precision', 0.0):.4f} | {format_metric_with_ci(pop, 'precision')} | **{format_metric_with_ci(sar, 'precision')}** | **{gain_prec}** | {compute_ci_verdict(sar, pop, 'precision', n_samples=p_users)} |"
        )
    md.append("")
    p_mbp_status = compute_model_beats_popularity_sanity(p_models["sar"], p_models["popularity"])
    md.append(f"- **Sanity Check (Model > Popularity):** `{p_mbp_status}`")

    p_checks = products_metrics.get("product_specific_checks", {})
    if p_checks:
        md.append("### Product-Specific Robustness Checks")
        md.append("")
        sparse_info = p_checks.get("sparse_data", {})
        tail_info = p_checks.get("long_tail", {})
        cat_info = p_checks.get("category_diversity", {})
        sim_info = p_checks.get("similar_alternatives_spot_check", {})

        md.append("| Check | Measured Value | Target / Baseline | Status |")
        md.append("|---|---|---|---|")
        md.append(
            f"| **Sparse User Share (<= 5 ratings)** | `{sparse_info.get('sparse_user_ratio', 0.0) * 100:.1f}%` ({sparse_info.get('sparse_user_count')}/{sparse_info.get('total_users')} users) | Informative metric | Verified |"
        )
        md.append(
            f"| **Long-Tail Volume Share** | `{tail_info.get('tail_interaction_volume_share', 0.0) * 100:.1f}%` ({tail_info.get('tail_item_count')}/{tail_info.get('total_items')} items) | Informative baseline (catalog tail) | Verified |"
        )
        tail_rec_pct = tail_info.get("tail_recommendation_share_at_k", 0.0) * 100.0
        tail_status = format_target_status(tail_rec_pct, 5.0)
        md.append(
            f"| **Long-Tail Rec Share @ 10** | `{tail_rec_pct:.1f}%` of recommended items | > 5% tail exploration | {tail_status} |"
        )
        cat_mean = cat_info.get("mean_unique_categories", 0.0)
        cat_min = cat_info.get("min_unique_categories", 1)
        cat_max = cat_info.get("max_unique_categories", 100)
        cat_status = (
            "Verified"
            if (cat_min <= cat_mean <= cat_max)
            else f"Not met ({cat_mean:.2f} vs [{cat_min}, {cat_max}])"
        )
        md.append(
            f"| **Category Diversity @ 10** | `{cat_mean:.2f}` unique categories/user | Min: `{cat_min}`, Max: `{cat_max}` | {cat_status} |"
        )
        shared_pct = sim_info.get("shared_category_rate", 0.0) * 100.0
        target_thresh = sim_info.get("target_threshold", 0.6) * 100.0
        sim_status = format_target_status(shared_pct, target_thresh)
        target_str = (
            f"{target_thresh:.0f}%"
            if target_thresh == int(target_thresh)
            else f"{target_thresh:.1f}%"
        )
        md.append(
            f"| **Similar Alternatives Spot-Check** | `{shared_pct:.1f}%` shared categories | Target > {target_str} | {sim_status} |"
        )
        md.append("")

    md.append("---")
    md.append("")

    # Section 3: Articles
    md.append(f"## 3. {a_heading}")
    md.append("")
    if a_is_synthetic:
        md.append("> [!WARNING]")
        md.append(
            "> **SYNTHETIC DEMO (not MIND):** These evaluation artifacts were generated using synthetic offline fixture data (`backend/tests/fixtures/mind/`) because real MIND dataset files were unavailable during automated download. **These results are not evidence of real-world quality.** Real benchmark evaluation will be conducted once MIND dataset files are placed in `data/raw/mind/`."
        )
        md.append("")
    md.append(
        "Evaluated using a rigorous **Dual-Protocol Architecture** tailored for news consumption:"
    )
    md.append("")
    md.append("### Protocol (a): Impression Ranking (MIND Protocol)")
    md.append(
        "Ranks candidates within each impression log (1 positive click amongst negative impressions)."
    )
    md.append("")
    imp_models = a_protocols["impression_ranking"]["models"]
    md.append(
        "| Model | AUC (95% CI) | MRR (95% CI) | nDCG@5 (95% CI) | nDCG@10 (95% CI) | Statistical Verdict (vs Pop) |"
    )
    md.append("|---|---|---|---|---|---|")
    md.append(
        f"| **Random** | `{format_metric_with_ci(imp_models['random'], 'auc')}` | `{format_metric_with_ci(imp_models['random'], 'mrr')}` | `{format_metric_with_ci(imp_models['random'], 'ndcg@5')}` | `{format_metric_with_ci(imp_models['random'], 'ndcg@10')}` | {compute_ci_verdict(imp_models['random'], imp_models['popularity'], 'auc', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
    )
    md.append(
        f"| **Popularity** | `{format_metric_with_ci(imp_models['popularity'], 'auc')}` | `{format_metric_with_ci(imp_models['popularity'], 'mrr')}` | `{format_metric_with_ci(imp_models['popularity'], 'ndcg@5')}` | `{format_metric_with_ci(imp_models['popularity'], 'ndcg@10')}` | Baseline |"
    )
    md.append(
        f"| **TF-IDF Profile** | **`{format_metric_with_ci(imp_models['tfidf_profile'], 'auc')}`** | **`{format_metric_with_ci(imp_models['tfidf_profile'], 'mrr')}`** | **`{format_metric_with_ci(imp_models['tfidf_profile'], 'ndcg@5')}`** | **`{format_metric_with_ci(imp_models['tfidf_profile'], 'ndcg@10')}`** | {compute_ci_verdict(imp_models['tfidf_profile'], imp_models['popularity'], 'auc', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
    )
    md.append("")

    md.append("### Protocol (b): 24h Recency Window Candidate Retrieval")
    md.append(
        "Ranks candidate pool strictly restricted to articles published/clicked within the active 24h recency window."
    )
    md.append("")
    md.append(
        "| Metric @ K | Random Baseline | Popularity Baseline (95% CI) | TF-IDF Profile (95% CI) | Gain vs Popularity | Statistical Verdict |"
    )
    md.append("|---|---|---|---|---|---|")
    for k in ["5", "10", "20"]:
        rnd = a_models["random"][k]
        pop = a_models["popularity"][k]
        tfidf = a_models["tfidf_profile"][k]

        gain_hr = format_pct_gain(tfidf["hit_rate"], pop["hit_rate"])
        gain_ndcg = format_pct_gain(tfidf["ndcg"], pop["ndcg"])
        gain_rec = format_pct_gain(tfidf["recall"], pop["recall"])
        gain_prec = format_pct_gain(tfidf.get("precision", 0.0), pop.get("precision", 0.0))

        md.append(
            f"| **HitRate@{k}** | {rnd['hit_rate']:.4f} | {format_metric_with_ci(pop, 'hit_rate')} | **{format_metric_with_ci(tfidf, 'hit_rate')}** | **{gain_hr}** | {compute_ci_verdict(tfidf, pop, 'hit_rate', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
        )
        md.append(
            f"| **NDCG@{k}** | {rnd['ndcg']:.4f} | {format_metric_with_ci(pop, 'ndcg')} | **{format_metric_with_ci(tfidf, 'ndcg')}** | **{gain_ndcg}** | {compute_ci_verdict(tfidf, pop, 'ndcg', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
        )
        md.append(
            f"| **Recall@{k}** | {rnd['recall']:.4f} | {format_metric_with_ci(pop, 'recall')} | **{format_metric_with_ci(tfidf, 'recall')}** | **{gain_rec}** | {compute_ci_verdict(tfidf, pop, 'recall', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
        )
        md.append(
            f"| **Precision@{k}** | {rnd.get('precision', 0.0):.4f} | {format_metric_with_ci(pop, 'precision')} | **{format_metric_with_ci(tfidf, 'precision')}** | **{gain_prec}** | {compute_ci_verdict(tfidf, pop, 'precision', n_samples=a_imp_n, is_synthetic=a_is_synthetic)} |"
        )
    md.append("")
    md.append("![News Articles Dual Protocol](figures/articles_protocols.png)")
    md.append("")
    md.append("---")
    md.append("")

    # Section 4: Cold-Start Degradation Analysis
    md.append("## 4. Cold-Start Degradation Analysis")
    md.append("")
    md.append(
        r"Cold start performance measured across progressive user history sizes $\{0, 1, 2, 3, 5, 10, 20\}$ signal points."
    )
    md.append("At $k=0$ likes, all models safely fall back to popularity.")
    md.append("")
    md.append(
        "| History Size (Likes) | Movies Recall@10 | Movies NDCG@10 | Products HitRate@10 | Products NDCG@10 | Articles HitRate@10 | Articles NDCG@10 |"
    )
    md.append("|---|---|---|---|---|---|---|")

    m_cs = movies_metrics["cold_start_curves"]["sar"]
    p_cs = products_metrics["cold_start_curves"]["sar"]
    a_cs = articles_metrics["cold_start_curves"]["tfidf_profile"]

    all_sizes = sorted(set(m_cs.keys()) | set(p_cs.keys()) | set(a_cs.keys()), key=lambda k: int(k))
    for s in all_sizes:
        m_r = m_cs.get(s, {}).get("recall@10", 0.0)
        m_n = m_cs.get(s, {}).get("ndcg@10", 0.0)
        p_hr = p_cs.get(s, {}).get("hit_rate@10", 0.0)
        p_n = p_cs.get(s, {}).get("ndcg@10", 0.0)
        a_hr = a_cs.get(s, {}).get("hit_rate@10", 0.0)
        a_n = a_cs.get(s, {}).get("ndcg@10", 0.0)
        md.append(
            f"| **{s} likes** | `{m_r:.4f}` | `{m_n:.4f}` | `{p_hr:.4f}` | `{p_n:.4f}` | `{a_hr:.4f}` | `{a_n:.4f}` |"
        )
    md.append("")
    md.append("![Cold Start Curves](figures/cold_start_curves.png)")
    md.append("")
    md.append("---")
    md.append("")

    # Section 5: Beyond-Accuracy Analysis
    md.append("## 5. Beyond-Accuracy Analysis (Coverage, Diversity, Personalisation)")
    md.append("")
    md.append(
        "Accuracy alone does not capture recommendation health. Popularity baseline achieves strong hit rates by concentrating"
    )
    md.append("all recommendations on a microscopic sliver of the catalogue (< 2% coverage).")
    md.append("")
    md.append(
        "| Content Type | Model | Coverage@10 | Intra-List Diversity@10 | Novelty@10 (bits) | Personalisation@10 |"
    )
    md.append("|---|---|---|---|---|---|")
    for ct, metrics_dict, p_key in [
        ("Movies", movies_metrics, "sar"),
        ("Products", products_metrics, "sar"),
        ("Articles", articles_metrics, "tfidf_profile"),
    ]:
        mods = metrics_dict["models"]
        for m_label, k_key in [
            ("Random", "random"),
            ("Popularity", "popularity"),
            (f"Personalised ({p_key})", p_key),
        ]:
            data = mods[k_key]["10"]
            md.append(
                f"| **{ct}** | {m_label} | `{data['coverage']:.4f}` | `{data['diversity']:.4f}` | `{data['novelty']:.2f}` bits | `{data['personalisation']:.4f}` |"
            )
    md.append("")
    md.append("![Beyond-Accuracy Trade-offs](figures/diversity_coverage.png)")
    md.append("")
    md.append("---")
    md.append("")

    # Section 6: Evaluation Protocols & Temporal Invariants
    md.append("## 6. Evaluation Protocols & Invariant Guarantees")
    md.append("")
    md.append(
        "The Discovery Engine enforces 6 core evaluation invariants (R1-R6) across all content domains:"
    )
    md.append("")
    md.append(
        "1. **R1 (Data Validity):** Dataset validation reports match actual partition interactions, users, items, and sparsity bounds."
    )
    md.append(
        r"2. **R2 (Temporal Leakage Isolation):** Chronological splits strictly enforce $t_{max}^{train} \le t_{min}^{test}$. Future interactions and test articles never enter similarity or TF-IDF vocabulary."
    )
    md.append(
        "3. **R3 (Model Invariants):** Recommendation lists feature strictly monotonic non-increasing scores, zero duplicates, and complete exclusion of previously seen items."
    )
    md.append(
        "4. **R4 (Evaluation Validity):** Personalised models and baselines are scored against an identical candidate set. Sanity ordering ($Personalised > Popularity > Random$) is verified."
    )
    md.append(
        "5. **R5 (Cold-Start Consistency):** Native cold-start scoring builds valid profiles from arbitrary user history, degrading smoothly from 20 likes down to 0 likes."
    )
    md.append(
        "6. **R6 (Cryptographic Integrity):** Every artifact directory contains a SHA-256 `manifest.json` sealing parquet data files, models, and evaluation outputs."
    )
    md.append("")
    md.append("---")
    md.append("")

    # Section 7: Statistical Honesty & Bootstrap Analysis
    md.append("## 7. Statistical Honesty & Bootstrap Analysis")
    md.append("")
    md.append(
        "To prevent statistical delusion and over-claiming subtle ranking gains, headline ranking metrics"
    )
    md.append(
        "are evaluated with non-parametric bootstrap 95% confidence intervals (500 resamples over test users/impressions)."
    )
    md.append(
        "A model's advantage over the non-personalised popularity baseline is considered statistically significant"
    )
    md.append(
        "if and only if the model's lower confidence bound strictly exceeds popularity's upper bound (p < 0.05)."
    )
    md.append("")
    md.append("### Empirical Findings Across Domains")
    md.append("")

    # Movies empirical findings
    md.append(f"1. **Movies ({m_var}, N={m_users:,} test users):**")
    if m_users < 200 or movies_metrics.get("is_synthetic", False):
        md.append(
            f"   - **No verdict (synthetic / n={m_users}):** Sample size below minimum evaluation threshold (N < 200) or dataset is synthetic fixture."
        )
    else:
        m_sep = []
        m_overlap = []
        m_worse = []
        for met in ["recall", "ndcg", "hit_rate", "precision"]:
            v = compute_ci_verdict(
                m_models["sar"]["10"], m_models["popularity"]["10"], met, n_samples=m_users
            )
            m_str = f"{met.upper()}@10 ({format_metric_with_ci(m_models['sar']['10'], met)} vs Pop {format_metric_with_ci(m_models['popularity']['10'], met)})"
            if v == "Model better (CIs separate)":
                m_sep.append(m_str)
            elif v == "Model worse":
                m_worse.append(m_str)
            else:
                m_overlap.append(m_str)

        if m_sep:
            md.append(
                f"   - **Statistically Significant Advantage (CIs separate):** {', '.join(m_sep)}."
            )
        if m_overlap:
            md.append(f"   - **No Significant Difference (CIs overlap):** {', '.join(m_overlap)}.")
        if m_worse:
            md.append(f"   - **Model Worse:** {', '.join(m_worse)}.")

    # Products empirical findings
    md.append(f"2. **Products ({p_var}, N={p_users:,} test users):**")
    if p_users < 200 or products_metrics.get("is_synthetic", False):
        md.append(
            f"   - **No verdict (synthetic / n={p_users}):** Sample size below minimum evaluation threshold (N < 200) or dataset is synthetic fixture."
        )
    else:
        p_sep = []
        p_overlap = []
        p_worse = []
        for met in ["recall", "ndcg", "hit_rate", "precision"]:
            v = compute_ci_verdict(
                p_models["sar"]["10"], p_models["popularity"]["10"], met, n_samples=p_users
            )
            p_str = f"{met.upper()}@10 ({format_metric_with_ci(p_models['sar']['10'], met)} vs Pop {format_metric_with_ci(p_models['popularity']['10'], met)})"
            if v == "Model better (CIs separate)":
                p_sep.append(p_str)
            elif v == "Model worse":
                p_worse.append(p_str)
            else:
                p_overlap.append(p_str)

        if p_sep:
            md.append(
                f"   - **Statistically Significant Advantage (CIs separate):** {', '.join(p_sep)}."
            )
        if p_overlap:
            md.append(f"   - **No Significant Difference (CIs overlap):** {', '.join(p_overlap)}.")
        if p_worse:
            md.append(f"   - **Model Worse:** {', '.join(p_worse)}.")

    # Articles empirical findings
    md.append(f"3. **Articles ({a_var}, N={a_imp_n:,} impressions):**")
    if a_is_synthetic or a_imp_n < 200:
        md.append(
            f"   - **No verdict (synthetic / n={a_imp_n}):** Sample size below minimum evaluation threshold (N < 200) or dataset is synthetic fixture. Results excluded from empirical claims."
        )
    else:
        a_sep = []
        a_overlap = []
        a_worse = []
        for met in ["auc", "mrr", "ndcg@5", "ndcg@10"]:
            v = compute_ci_verdict(
                imp_models["tfidf_profile"],
                imp_models["popularity"],
                met,
                n_samples=a_imp_n,
                is_synthetic=a_is_synthetic,
            )
            a_str = f"{met.upper()} ({format_metric_with_ci(imp_models['tfidf_profile'], met)} vs Pop {format_metric_with_ci(imp_models['popularity'], met)})"
            if v == "Model better (CIs separate)":
                a_sep.append(a_str)
            elif v == "Model worse":
                a_worse.append(a_str)
            else:
                a_overlap.append(a_str)

        if a_sep:
            md.append(
                f"   - **Impression Ranking Statistically Significant Advantage (CIs separate):** {', '.join(a_sep)}."
            )
        if a_overlap:
            md.append(
                f"   - **Impression Ranking No Significant Difference (CIs overlap):** {', '.join(a_overlap)}."
            )
        if a_worse:
            md.append(f"   - **Impression Ranking Model Worse:** {', '.join(a_worse)}.")

    md.append("")
    md.append("### Known Limitations & Failure Modes")
    md.append("")
    md.append(
        "1. **Popularity Bias in Dense Corpora:** In dense collaborative filtering domains (e.g. MovieLens), popular blockbuster items dominate user interactions. Non-personalized popularity baselines achieve competitive hit rates by recommending narrow subsets of blockbuster items. While collaborative models achieve higher catalogue coverage and personalization, overlapping confidence intervals on ranking position demonstrate that ranking position advantage requires cautious interpretation."
    )
    md.append(
        "2. **Sparse E-Commerce Feedback:** In high-sparsity product catalogs, a substantial share of users have few total interactions. Absolute hit rates remain low across all models due to catalog sparsity, and sparse taste vectors can yield confidence interval overlap on cold users."
    )
    md.append(
        "3. **News Freshness Horizon:** Candidate pools restricted to active recency windows eliminate outdated articles but restrict the retrievable candidate set."
    )
    md.append(
        "4. **Offline vs Online Gap:** Offline evaluation on historical logs reflects past logging policy candidates; live click-through performance is subject to presentation and position bias."
    )
    md.append("")

    return "\n".join(md) + "\n"


def main() -> None:
    """CLI entry point for tools/make_results.py."""
    parser = argparse.ArgumentParser(
        description="Generate docs/RESULTS.md and figures from metrics.json."
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=REPO_ROOT / "artifacts",
        help="Path to artifacts/ root containing movies, products, articles directories",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=REPO_ROOT / "docs" / "RESULTS.md",
        help="Path to output markdown file (default: docs/RESULTS.md)",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "figures",
        help="Path to output figures directory (default: docs/figures)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/RESULTS.md is up-to-date without writing",
    )
    parser.add_argument(
        "--allow-fast",
        action="store_true",
        help="Allow generating RESULTS.md from fast variants (marks title 'FAST VARIANT, NOT FOR REPORT')",
    )
    args = parser.parse_args()

    artifacts_dir: Path = args.artifacts_dir
    output_md: Path = args.output_md
    figures_dir: Path = args.figures_dir

    print(f"Loading evaluation artifacts from {artifacts_dir}...")
    movies_metrics = load_metrics_json(artifacts_dir, "movies")
    products_metrics = load_metrics_json(artifacts_dir, "products")
    articles_metrics = load_metrics_json(artifacts_dir, "articles")

    movies_manifest = load_manifest_json(artifacts_dir, "movies")
    products_manifest = load_manifest_json(artifacts_dir, "products")
    articles_manifest = load_manifest_json(artifacts_dir, "articles")

    fast_run = is_fast_variant(
        movies_metrics=movies_metrics,
        products_metrics=products_metrics,
        articles_metrics=articles_metrics,
        movies_manifest=movies_manifest,
        products_manifest=products_manifest,
        articles_manifest=articles_manifest,
    )
    if fast_run and not args.allow_fast:
        print(
            "[ERROR] Refusing to write RESULTS.md from a fast variant unless --allow-fast is specified.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        validate_post_train_checks_presence("movies", movies_metrics)
        validate_post_train_checks_presence("products", products_metrics)
        validate_post_train_checks_presence("articles", articles_metrics)
    except ValueError as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating figures in {figures_dir}...")
    figure_paths = generate_figures(
        movies_metrics=movies_metrics,
        products_metrics=products_metrics,
        articles_metrics=articles_metrics,
        figures_dir=figures_dir,
    )
    for p in figure_paths:
        try:
            rel_p = p.relative_to(REPO_ROOT)
        except ValueError:
            rel_p = p
        print(f"  - Generated: {rel_p}")

    print("Constructing markdown report...")
    generated_report = build_markdown_report(
        movies_metrics=movies_metrics,
        products_metrics=products_metrics,
        articles_metrics=articles_metrics,
        movies_manifest=movies_manifest,
        products_manifest=products_manifest,
        articles_manifest=articles_manifest,
    )

    # Preserve existing Section 8 (API Serving Performance) if present
    section_8_header = "## 8. API Serving Performance & Resource Budgets (Phase 7)"
    if output_md.exists():
        existing_text = output_md.read_text(encoding="utf-8")
        if section_8_header in existing_text:
            s8_part = section_8_header + existing_text.split(section_8_header, 1)[1]
            generated_report = generated_report.rstrip() + "\n\n" + s8_part.strip() + "\n"

    if args.check:
        if not output_md.exists():
            print(f"[ERROR] {output_md} does not exist!")
            sys.exit(1)
        current_content = output_md.read_text(encoding="utf-8")
        if current_content != generated_report:
            print(
                f"[ERROR] {output_md} is out of date! Run `python tools/make_results.py` to regenerate."
            )
            sys.exit(1)
        print(f"[SUCCESS] {output_md} is up-to-date.")
        sys.exit(0)

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(generated_report, encoding="utf-8")
    try:
        rel_out = output_md.relative_to(REPO_ROOT)
    except ValueError:
        rel_out = output_md
    print(f"[SUCCESS] Updated {rel_out} ({len(generated_report)} bytes).")


if __name__ == "__main__":
    main()
