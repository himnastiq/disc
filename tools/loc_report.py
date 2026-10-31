#!/usr/bin/env python3
"""Discovery Engine - Lines of Code & Provenance Accounting (P11.3).

Analyzes git-tracked files using `git ls-files` to compute exact, deterministic
file counts and line counts per area, distinguishing original versus derived code.

Exclusions (per P11.3 specification):
    - Lockfiles: `backend/uv.lock`, `frontend/package-lock.json`
    - Schema exports: `backend/api/openapi.json`
    - Synthetic fixtures: `backend/tests/fixtures/artifacts_mini/*`
    - Binary and media files: `.parquet`, `.npz`, `.npy`, `.png`, `.jpg`, `.ico`, `.gz`
    - Vendored license: `backend/discovery/LICENSE`

Outputs:
    docs/ORIGINAL_VS_DERIVED.md

Supports:
    python tools/loc_report.py          # Regenerates docs/ORIGINAL_VS_DERIVED.md
    python tools/loc_report.py --check  # Verifies committed report matches disk
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "ORIGINAL_VS_DERIVED.md"

BINARY_EXTENSIONS = {
    ".parquet",
    ".npz",
    ".npy",
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".svg",
    ".gz",
    ".zip",
    ".tar",
    ".pyc",
}

EXCLUDED_EXACT_PATHS = {
    "backend/uv.lock",
    "frontend/package-lock.json",
    "backend/api/openapi.json",
    "backend/discovery/LICENSE",
}


@dataclass
class AreaStats:
    name: str
    classification: str
    file_count: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_blank_lines: int = 0


def get_tracked_files() -> list[str]:
    """Get list of tracked files using git ls-files."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def is_excluded(path_str: str) -> bool:
    """Check if file should be excluded from LOC accounting."""
    if path_str in EXCLUDED_EXACT_PATHS:
        return True
    if path_str.startswith("backend/tests/fixtures/artifacts_mini/"):
        return True
    return any(path_str.endswith(ext) for ext in BINARY_EXTENSIONS)


def classify_file(path_str: str) -> str:
    """Classify a tracked path into an accounting area."""
    if path_str.startswith("backend/discovery/"):
        return "Derived: Microsoft Recommenders (backend/discovery/)"
    if path_str.startswith("backend/engine/"):
        return "Original: Recommender Core (backend/engine/)"
    if path_str.startswith("backend/api/"):
        return "Original: FastAPI Serving Layer (backend/api/)"
    if path_str.startswith("frontend/"):
        return "Original: Next.js Frontend Dashboard (frontend/)"
    if path_str.startswith("tools/"):
        return "Original: Automation & Quality Tools (tools/)"
    if path_str.startswith("backend/tests/") or "tests/" in path_str:
        return "Original: Testing Suites & Harnesses (tests/)"
    if path_str.startswith("docs/"):
        return "Original: Specifications & Documentation (docs/)"
    return "Original: Repository Root & Configurations"


def analyze_lines(file_path: Path) -> tuple[int, int, int]:
    """Count (total_lines, code_lines, comment_blank_lines) for a text file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return 0, 0, 0

    lines = content.splitlines()
    total = len(lines)
    code = 0
    comment_blank = 0

    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "//", "/*", "*")):
            comment_blank += 1
        else:
            code += 1

    return total, code, comment_blank


def generate_loc_markdown() -> str:
    """Compute and format the Original vs Derived lines of code report."""
    files = get_tracked_files()

    areas: dict[str, AreaStats] = {}
    area_definitions = [
        ("Derived: Microsoft Recommenders (backend/discovery/)", "Derived (MIT)"),
        ("Original: Recommender Core (backend/engine/)", "Original"),
        ("Original: FastAPI Serving Layer (backend/api/)", "Original"),
        ("Original: Next.js Frontend Dashboard (frontend/)", "Original"),
        ("Original: Automation & Quality Tools (tools/)", "Original"),
        ("Original: Testing Suites & Harnesses (tests/)", "Original"),
        ("Original: Specifications & Documentation (docs/)", "Original"),
        ("Original: Repository Root & Configurations", "Original"),
    ]

    for name, classification in area_definitions:
        areas[name] = AreaStats(name=name, classification=classification)

    excluded_count = 0
    for rel_path in sorted(files):
        if is_excluded(rel_path):
            excluded_count += 1
            continue

        full_path = REPO_ROOT / rel_path
        if not full_path.exists() or full_path.is_dir():
            continue

        area_name = classify_file(rel_path)
        if area_name not in areas:
            areas[area_name] = AreaStats(name=area_name, classification="Original")

        total, code, blank = analyze_lines(full_path)
        stat = areas[area_name]
        stat.file_count += 1
        stat.total_lines += total
        stat.code_lines += code
        stat.comment_blank_lines += blank

    # Compute subtotals
    derived_total = sum(
        s.total_lines for s in areas.values() if s.classification.startswith("Derived")
    )
    derived_code = sum(
        s.code_lines for s in areas.values() if s.classification.startswith("Derived")
    )
    derived_files = sum(
        s.file_count for s in areas.values() if s.classification.startswith("Derived")
    )

    original_total = sum(
        s.total_lines for s in areas.values() if s.classification == "Original"
    )
    original_code = sum(
        s.code_lines for s in areas.values() if s.classification == "Original"
    )
    original_files = sum(
        s.file_count for s in areas.values() if s.classification == "Original"
    )

    grand_total_lines = derived_total + original_total
    grand_total_code = derived_code + original_code
    grand_total_files = derived_files + original_files

    orig_pct_lines = (
        (original_total / grand_total_lines * 100) if grand_total_lines else 0.0
    )
    orig_pct_code = (
        (original_code / grand_total_code * 100) if grand_total_code else 0.0
    )

    lines = [
        "# Original versus Derived Accounting",
        "",
        "> **Deterministic Report:** Automatically generated by `python tools/loc_report.py` from `git ls-files`.",
        "> Distinguishes original Discovery Engine code from derived components vendored from Microsoft Recommenders.",
        "",
        "## 1. Codebase Composition Summary",
        "",
        "| Classification | Tracked Files | Total Lines | Code Lines | Comments & Blank | Share of Lines | Share of Code |",
        "|---|---|---|---|---|---|---|",
        f"| **Original Discovery Engine** | {original_files:,} | {original_total:,} | {original_code:,} | {(original_total - original_code):,} | **{orig_pct_lines:.1f}%** | **{orig_pct_code:.1f}%** |",
        f"| **Derived (Microsoft Recommenders)** | {derived_files:,} | {derived_total:,} | {derived_code:,} | {(derived_total - derived_code):,} | **{(100 - orig_pct_lines):.1f}%** | **{(100 - orig_pct_code):.1f}%** |",
        f"| **Total Accounted** | **{grand_total_files:,}** | **{grand_total_lines:,}** | **{grand_total_code:,}** | **{(grand_total_lines - grand_total_code):,}** | **100.0%** | **100.0%** |",
        "",
        "---",
        "",
        "## 2. Detailed Breakdown by Architectural Area",
        "",
        "| Area | Origin / License | File Count | Total Lines | Code Lines | Blank / Comment |",
        "|---|---|---|---|---|---|",
    ]

    for name, _ in area_definitions:
        stat = areas[name]
        lines.append(
            f"| `{stat.name}` | {stat.classification} | {stat.file_count:,} | {stat.total_lines:,} | {stat.code_lines:,} | {stat.comment_blank_lines:,} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Exclusion Rules & Accounting Standards",
            "",
            f"Per Phase 11 Task P11.3 specification, exactly **{excluded_count}** tracked non-code, generated, or binary files are excluded from line counting:",
            "- **Dependency Lockfiles:** `backend/uv.lock`, `frontend/package-lock.json` (auto-generated machine resolution graphs).",
            "- **API Schemas:** `backend/api/openapi.json` (machine export from FastAPI runtime models).",
            "- **Synthetic Test Fixtures:** `backend/tests/fixtures/artifacts_mini/*` (pre-built serialized mock tables for offline integration testing).",
            "- **Binary & Media Formats:** `.parquet`, `.npz`, `.npy`, `.png`, `.jpg`, `.ico`, `.gz` files.",
            "- **Vendored License:** `backend/discovery/LICENSE` (third-party MIT legal text).",
            "",
            "---",
            "",
            "## 4. Architectural Provenance Statement",
            "",
            "- **Original Framework:** 100% of the dataset adapters, temporal splits, candidate filtering, bootstrap evaluation harness, artifact layout, FastAPI REST backend, Next.js web dashboard, and verification tools are original work created for Discovery Engine.",
            "- **Derived Mathematics:** `backend/discovery/` contains trimmed single-node algorithms (SAR co-occurrence matrix math and TF-IDF profile matching) derived from Microsoft Recommenders (v1.2.1, MIT License), patched for CPU-only execution without deep-learning frameworks (PyTorch, TensorFlow, Spark).",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify original-vs-derived LOC report."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether docs/ORIGINAL_VS_DERIVED.md matches current codebase without modifying it.",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  Discovery Engine: Original vs Derived Accounting (P11.3)")
    print("=" * 65)

    generated_text = generate_loc_markdown()

    if args.check:
        if not OUTPUT_PATH.exists():
            print(f"[FAIL] Missing {OUTPUT_PATH}. Run `python tools/loc_report.py`.")
            return 1
        committed_text = OUTPUT_PATH.read_text(encoding="utf-8")
        if committed_text != generated_text:
            print(
                "[FAIL] docs/ORIGINAL_VS_DERIVED.md drifts from tracked files. Run `python tools/loc_report.py`."
            )
            return 1
        print("[PASS] docs/ORIGINAL_VS_DERIVED.md is up to date.")
        return 0

    OUTPUT_PATH.write_text(generated_text, encoding="utf-8")
    print(f"[SUCCESS] Generated {OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
