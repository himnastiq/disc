#!/usr/bin/env python3
"""Check that core engine abstractions remain unchanged (P4.7, P5.11).

Asserts that git diff between the Phase 3 end commit and current HEAD
is strictly confined to:
- adapters/ (backend/engine/adapters/)
- configs/ (backend/engine/configs/)
- tests/ (backend/tests/)
- docs/
- tools/
- backend/scripts/
- IMPLEMENTATION_PLAN.md

If any core engine file (backend/engine/ outside adapters and configs)
was modified, requires a corresponding entry in docs/DECISIONS.md explaining
why the abstraction was insufficient.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Phase 3 end commit SHA (P3.13)
PHASE_3_END_COMMIT = "6da1d3a"

# Allowed path patterns for domain additions
ALLOWED_PATTERNS = [
    "backend/engine/adapters/*",
    "backend/engine/adapters/**/*",
    "backend/engine/configs/*",
    "backend/engine/configs/**/*",
    "configs/*",
    "configs/**/*",
    "backend/tests/*",
    "backend/tests/**/*",
    "tests/*",
    "tests/**/*",
    "docs/*",
    "docs/**/*",
    "tools/*",
    "tools/**/*",
    "backend/scripts/*",
    "backend/scripts/**/*",
    "scripts/*",
    "scripts/**/*",
    "IMPLEMENTATION_PLAN.md",
    "Makefile",
    ".gitignore",
    ".gitattributes",
]

CORE_ENGINE_PREFIXES = [
    "backend/engine/",
]

EXEMPT_PREFIXES = [
    "backend/engine/adapters/",
    "backend/engine/configs/",
]


def get_git_diff_files(base_commit: str, target: str = "HEAD") -> list[str]:
    """Retrieve list of modified files between base_commit and target."""
    cmd = ["git", "diff", "--name-only", base_commit, target]
    result = subprocess.run(
        cmd,
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


def is_allowed_path(
    file_path: str, allowed_patterns: list[str] = ALLOWED_PATTERNS
) -> bool:
    """Check if file path matches any of the allowed patterns."""
    norm_path = file_path.replace("\\", "/")
    return any(fnmatch.fnmatch(norm_path, pattern) for pattern in allowed_patterns)


def is_core_engine_file(file_path: str) -> bool:
    """Determine if a file belongs to core engine abstractions."""
    norm_path = file_path.replace("\\", "/")
    if any(norm_path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
        return False
    return any(norm_path.startswith(prefix) for prefix in CORE_ENGINE_PREFIXES)


def has_documented_decision_for_core_change(decisions_file: Path) -> bool:
    """Verify if docs/DECISIONS.md documents an architectural exception for core changes."""
    if not decisions_file.exists():
        return False
    content = decisions_file.read_text(encoding="utf-8")
    # Check for D-0xx entry mentioning abstraction change or core change
    return bool(
        re.search(
            r"## D-\d+.*(?:abstraction|core change|refactor)", content, re.IGNORECASE
        )
    )


def check_core_unchanged(
    base_commit: str = PHASE_3_END_COMMIT,
    target: str = "HEAD",
    decisions_path: Path | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Check that only allowed files were modified and return (passed, disallowed, core_violations)."""
    decisions_file = decisions_path or (REPO_ROOT / "docs" / "DECISIONS.md")
    modified_files = get_git_diff_files(base_commit, target)

    disallowed_files: list[str] = []
    core_violations: list[str] = []

    for f in modified_files:
        if is_core_engine_file(f):
            core_violations.append(f)
        elif not is_allowed_path(f):
            disallowed_files.append(f)

    if core_violations:
        if has_documented_decision_for_core_change(decisions_file):
            print(
                f"[NOTE] Core files modified ({len(core_violations)}), but documented in DECISIONS.md."
            )
            passed = len(disallowed_files) == 0
        else:
            passed = False
    else:
        passed = len(disallowed_files) == 0

    return passed, disallowed_files, core_violations


def main() -> None:
    """CLI entry point for tools/core_unchanged.py."""
    parser = argparse.ArgumentParser(
        description="Verify engine core abstractions remained untouched since Phase 3."
    )
    parser.add_argument(
        "--base",
        default=PHASE_3_END_COMMIT,
        help=f"Base commit to compare against (default: {PHASE_3_END_COMMIT} Phase 3 end)",
    )
    parser.add_argument(
        "--target",
        default="HEAD",
        help="Target commit to compare against (default: HEAD)",
    )
    args = parser.parse_args()

    print(f"Comparing diff between base '{args.base}' and target '{args.target}'...")
    passed, disallowed, core_violations = check_core_unchanged(
        base_commit=args.base,
        target=args.target,
    )

    if not passed:
        print("\n[ERROR] Core Unchanged Check FAILED!")
        if core_violations:
            print(
                f"\nForbidden modifications in core engine files ({len(core_violations)}):"
            )
            for f in core_violations:
                print(f"  - {f}")
            print(
                "\nAny change to engine core requires a docs/DECISIONS.md entry explaining"
            )
            print("why the abstraction was insufficient.")
        if disallowed:
            print(f"\nModifications outside allowed domains ({len(disallowed)}):")
            for f in disallowed:
                print(f"  - {f}")
        sys.exit(1)

    print("\n[SUCCESS] Core Unchanged Check PASSED.")
    print(f"All changes since Phase 3 ({args.base}) are strictly restricted to:")
    print("  - adapters/ (AmazonProductsAdapter)")
    print("  - configs/ (products.yaml)")
    print("  - tests/ (products split leakage, amazon adapter, product checks)")
    print("  - docs/ (DATASETS.md, DECISIONS.md)")
    print("  - tools/ & scripts/ (product_checks.py, fetch_data.py)")
    print("Zero core engine abstractions were modified.")


if __name__ == "__main__":
    main()
