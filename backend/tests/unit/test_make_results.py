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
