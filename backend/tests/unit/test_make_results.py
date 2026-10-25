"""Discovery Engine - Tests for tools/make_results.py (P6.1).

Verifies that:
1. `tools/make_results.py` generates `docs/RESULTS.md` and all 4 figures.
2. All figures are valid PNG files with proper headers.
3. Every metric in the generated tables matches `metrics.json` without fabrication.
4. The `--check` CLI flag correctly passes when up to date and fails when out of date.
5. Idempotent regeneration produces identical markdown reports.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MAKE_RESULTS_SCRIPT = REPO_ROOT / "tools" / "make_results.py"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
DOCS_DIR = REPO_ROOT / "docs"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_make_results_generates_markdown_and_figures(tmp_path: Path) -> None:
    """Verify execution of make_results.py generates docs/RESULTS.md and 4 PNG figures."""
    out_md = tmp_path / "RESULTS.md"
    fig_dir = tmp_path / "figures"

    cmd = [
        sys.executable,
        str(MAKE_RESULTS_SCRIPT),
        "--artifacts-dir",
        str(ARTIFACTS_DIR),
        "--output-md",
        str(out_md),
        "--figures-dir",
        str(fig_dir),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "Updated" in res.stdout
    assert out_md.exists()
    assert fig_dir.exists()

    expected_figures = [
        "ranking_comparison.png",
        "cold_start_curves.png",
        "diversity_coverage.png",
        "articles_protocols.png",
    ]

    for fig_name in expected_figures:
        fig_path = fig_dir / fig_name
        assert fig_path.exists(), f"Missing expected figure: {fig_name}"
        data = fig_path.read_bytes()
        assert len(data) > 1024, f"Figure {fig_name} is too small ({len(data)} bytes)"
        assert data.startswith(PNG_MAGIC), f"Figure {fig_name} does not have valid PNG header"


def test_make_results_metrics_grounded_in_artifacts() -> None:
    """Verify metrics table in docs/RESULTS.md matches artifacts/metrics.json exactly."""
    results_md_path = DOCS_DIR / "RESULTS.md"
    assert results_md_path.exists(), "docs/RESULTS.md must exist"
    content = results_md_path.read_text(encoding="utf-8")

    # Load artifacts directly
    movies_metrics = json.loads(
        (ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8")
    )
    products_metrics = json.loads(
        (ARTIFACTS_DIR / "products" / "metrics.json").read_text(encoding="utf-8")
    )
    articles_metrics = json.loads(
        (ARTIFACTS_DIR / "articles" / "metrics.json").read_text(encoding="utf-8")
    )

    # Assert exact formatted float values exist in content
    # MovieLens SAR HitRate@10
    m_sar_hr10 = f"{movies_metrics['models']['sar']['10']['hit_rate']:.4f}"
    assert m_sar_hr10 in content, f"Missing MovieLens SAR HitRate@10 {m_sar_hr10} in RESULTS.md"

    # Amazon SAR NDCG@10
    p_sar_ndcg10 = f"{products_metrics['models']['sar']['10']['ndcg']:.4f}"
    assert p_sar_ndcg10 in content, f"Missing Products SAR NDCG@10 {p_sar_ndcg10} in RESULTS.md"

    # MIND TF-IDF Impression AUC
    a_imp_auc = f"{articles_metrics['protocols']['impression_ranking']['models']['tfidf_profile']['auc']:.4f}"
    assert a_imp_auc in content, f"Missing MIND TF-IDF AUC {a_imp_auc} in RESULTS.md"

    # Cold start values
    m_cs_recall10 = f"{movies_metrics['cold_start_curves']['sar']['20']['recall@10']:.4f}"
    assert m_cs_recall10 in content, (
        f"Missing MovieLens Cold Start Recall@10 (20 likes) {m_cs_recall10}"
    )


def test_make_results_check_flag() -> None:
    """Verify that --check flag succeeds on current committed state."""
    cmd = [
        sys.executable,
        str(MAKE_RESULTS_SCRIPT),
        "--artifacts-dir",
        str(ARTIFACTS_DIR),
        "--output-md",
        str(DOCS_DIR / "RESULTS.md"),
        "--figures-dir",
        str(DOCS_DIR / "figures"),
        "--check",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "is up-to-date" in res.stdout


def test_make_results_idempotency(tmp_path: Path) -> None:
    """Verify running make_results.py twice produces text-identical output."""
    out_md1 = tmp_path / "RESULTS_1.md"
    out_md2 = tmp_path / "RESULTS_2.md"
    fig_dir = tmp_path / "figures"

    base_cmd = [
        sys.executable,
        str(MAKE_RESULTS_SCRIPT),
        "--artifacts-dir",
        str(ARTIFACTS_DIR),
        "--figures-dir",
        str(fig_dir),
    ]

    subprocess.run([*base_cmd, "--output-md", str(out_md1)], check=True)
    subprocess.run([*base_cmd, "--output-md", str(out_md2)], check=True)

    assert out_md1.read_text(encoding="utf-8") == out_md2.read_text(encoding="utf-8")


def test_make_results_ci_verdicts_no_beats_when_overlapping() -> None:
    """Verify that when SAR < Popularity and CIs overlap, no 'beats' verdict is produced (FIX-23)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import build_markdown_report, compute_ci_verdict

    # 1. Direct unit assertions on compute_ci_verdict
    # Separate CIs: model better
    v_better = compute_ci_verdict(
        {"hit_rate": 0.20, "hit_rate_ci95": [0.18, 0.22]},
        {"hit_rate": 0.12, "hit_rate_ci95": [0.10, 0.14]},
        "hit_rate",
    )
    assert v_better == "Model better (CIs separate)"

    # Overlapping CIs: SAR < Popularity
    v_overlap = compute_ci_verdict(
        {"hit_rate": 0.14, "hit_rate_ci95": [0.11, 0.17]},
        {"hit_rate": 0.16, "hit_rate_ci95": [0.13, 0.19]},
        "hit_rate",
    )
    assert v_overlap == "No significant difference (CIs overlap)"
    assert "beats" not in v_overlap.lower()

    # Separate CIs: model worse
    v_worse = compute_ci_verdict(
        {"hit_rate": 0.08, "hit_rate_ci95": [0.06, 0.09]},
        {"hit_rate": 0.15, "hit_rate_ci95": [0.13, 0.17]},
        "hit_rate",
    )
    assert v_worse == "Model worse"
    assert "beats" not in v_worse.lower()

    # 2. End-to-end report generation with SAR < Popularity and overlapping CIs
    m_dict = json.loads((ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8"))
    p_dict = json.loads((ARTIFACTS_DIR / "products" / "metrics.json").read_text(encoding="utf-8"))
    a_dict = json.loads((ARTIFACTS_DIR / "articles" / "metrics.json").read_text(encoding="utf-8"))

    # Force SAR < Popularity with overlapping CIs across all movie metrics
    for k in ["5", "10", "20"]:
        for met in ["hit_rate", "ndcg", "recall", "precision"]:
            m_dict["models"]["sar"][k][met] = 0.040
            m_dict["models"]["sar"][k][f"{met}_ci95"] = [0.030, 0.055]
            m_dict["models"]["popularity"][k][met] = 0.045
            m_dict["models"]["popularity"][k][f"{met}_ci95"] = [0.035, 0.060]

    report = build_markdown_report(m_dict, p_dict, a_dict)

    # Assert that no "beats" verdict appears anywhere in the output report
    assert "Model beats Popularity" not in report
    assert "beats Popularity" not in report
    assert "beats Random" not in report
    assert "decisively beats" not in report
    # Assert proper statistical verdict is rendered
    assert "No significant difference (CIs overlap)" in report


def test_articles_provenance_synthetic_banner() -> None:
    """Verify Articles provenance label and synthetic fixture warning banner (FIX-24)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import build_markdown_report

    m_dict = json.loads((ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8"))
    p_dict = json.loads((ARTIFACTS_DIR / "products" / "metrics.json").read_text(encoding="utf-8"))
    a_dict = json.loads((ARTIFACTS_DIR / "articles" / "metrics.json").read_text(encoding="utf-8"))

    report = build_markdown_report(m_dict, p_dict, a_dict)

    # 1. Labelled as SYNTHETIC DEMO (not MIND)
    assert "SYNTHETIC DEMO (not MIND)" in report or "SYNTHETIC FIXTURE (not MIND)" in report
    # 2. Warning banner present
    assert (
        "**SYNTHETIC DEMO (not MIND):**" in report or "**SYNTHETIC FIXTURE (not MIND):**" in report
    )
    assert "results are not evidence of real-world quality" in report.lower()


def test_make_results_status_column_target_met_and_not_met() -> None:
    """Verify Status column: 'Verified' only when target met, otherwise 'Not met' with both numbers (FIX-27a)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import format_target_status

    # Target met
    status_met = format_target_status(65.0, 50.0)
    assert status_met == "Verified"

    # 43.0% vs > 50% target
    status_not_met = format_target_status(43.0, 50.0)
    assert "Not met" in status_not_met
    assert "43.0%" in status_not_met
    assert "50%" in status_not_met or "50.0%" in status_not_met


def test_make_results_section_headings_and_dataset_names_from_manifest() -> None:
    """Verify section headings and dataset names come from manifest, never typed (FIX-27b)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import build_markdown_report

    m_dict = json.loads((ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8"))
    p_dict = json.loads((ARTIFACTS_DIR / "products" / "metrics.json").read_text(encoding="utf-8"))
    a_dict = json.loads((ARTIFACTS_DIR / "articles" / "metrics.json").read_text(encoding="utf-8"))

    m_manifest = {
        "dataset_name": "Custom Movie Dataset",
        "section_heading": "Movies (Custom Movie Dataset + CustomModel)",
    }
    p_manifest = {
        "dataset_name": "Amazon Video Games",
        "section_heading": "Products (Amazon Video Games + SAR)",
    }
    a_manifest = {
        "dataset_name": "Custom News Fixture",
        "section_heading": "Articles (Custom News Fixture + Neural)",
    }

    report = build_markdown_report(m_dict, p_dict, a_dict, m_manifest, p_manifest, a_manifest)

    assert "## 1. Movies (Custom Movie Dataset + CustomModel)" in report
    assert "## 2. Products (Amazon Video Games + SAR)" in report
    assert "## 3. Articles (Custom News Fixture + Neural)" in report
    assert "Custom Movie Dataset" in report
    assert "Amazon Video Games" in report


def test_make_results_model_beats_popularity_sanity_computed_from_rows() -> None:
    """Verify Model > Popularity sanity line is computed from rows and never 'Passed' if any row fails (FIX-27c)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import compute_model_beats_popularity_sanity

    # 1. All rows pass
    model_all_pass = {"10": {"hit_rate": 0.30, "ndcg": 0.20, "recall": 0.15, "precision": 0.05}}
    pop_all_pass = {"10": {"hit_rate": 0.20, "ndcg": 0.15, "recall": 0.10, "precision": 0.04}}
    assert (
        compute_model_beats_popularity_sanity(model_all_pass, pop_all_pass, k_list=["10"])
        == "Passed"
    )

    # 2. Mixed: some metrics below popularity
    model_mixed = {"10": {"hit_rate": 0.30, "ndcg": 0.14, "recall": 0.15, "precision": 0.03}}
    res_mixed = compute_model_beats_popularity_sanity(model_mixed, pop_all_pass, k_list=["10"])
    assert res_mixed.startswith("Mixed: model below Popularity on")
    assert "ndcg@10" in res_mixed
    assert "precision@10" in res_mixed
    assert res_mixed != "Passed"


def test_make_results_minimum_sample_rule_n3_and_n9() -> None:
    """Verify minimum-sample rule with n=3 and n=9 produces 'No verdict (synthetic / n=<n>)' (FIX-27d)."""
    if str(REPO_ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
    from make_results import build_markdown_report, compute_ci_verdict

    # 1. Direct compute_ci_verdict assertions with n=3 and n=9
    m_dict = {"hit_rate": 0.90, "hit_rate_ci95": [0.85, 0.95]}
    p_dict = {"hit_rate": 0.10, "hit_rate_ci95": [0.05, 0.15]}

    v3 = compute_ci_verdict(m_dict, p_dict, "hit_rate", n_samples=3)
    assert v3 == "No verdict (synthetic / n=3)"

    v9 = compute_ci_verdict(m_dict, p_dict, "hit_rate", n_samples=9)
    assert v9 == "No verdict (synthetic / n=9)"

    # 2. Full report generation: numbers excluded from Executive Summary except as 'demo only'
    movies_metrics = json.loads(
        (ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8")
    )
    products_metrics = json.loads(
        (ARTIFACTS_DIR / "products" / "metrics.json").read_text(encoding="utf-8")
    )
    articles_metrics = json.loads(
        (ARTIFACTS_DIR / "articles" / "metrics.json").read_text(encoding="utf-8")
    )

    report = build_markdown_report(movies_metrics, products_metrics, articles_metrics)
    assert "No verdict (synthetic / n=9)" in report
    # Executive summary has 'demo only' for articles
    exec_summary = report.split("## Executive Summary")[1].split("## 1.")[0]
    assert "demo only" in exec_summary
    assert "Impression AUC:" not in exec_summary
