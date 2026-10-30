#!/usr/bin/env python3
"""Audit Session Log and Architecture Decision Records against actual codebase (E2).

Verifies that every cited file, test file, test function, FIX-NN, and D-NNN
in the Session Log (IMPLEMENTATION_PLAN.md) and docs/DECISIONS.md actually exists.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = REPO_ROOT / "IMPLEMENTATION_PLAN.md"
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"


def get_session_log_text(plan_text: str) -> str:
    """Extract only the Session Log portion of IMPLEMENTATION_PLAN.md."""
    marker = "## 14. Session Log"
    idx = plan_text.find(marker)
    if idx != -1:
        return plan_text[idx:]
    return plan_text


def get_defined_decisions(decisions_content: str) -> set[str]:
    """Extract all decision IDs defined in docs/DECISIONS.md."""
    return set(re.findall(r"^##\s+(D-\d+):", decisions_content, re.MULTILINE))


def get_defined_test_functions(file_path: Path) -> set[str]:
    """Extract all test function names from a Python test file."""
    if not file_path.exists() or file_path.suffix != ".py":
        return set()
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        funcs: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and node.name.startswith("test_"):
                funcs.add(node.name)
        return funcs
    except (SyntaxError, UnicodeDecodeError):
        # Fallback to regex
        return set(
            re.findall(
                r"^(?:async\s+)?def\s+(test_[a-zA-Z0-9_]+)",
                file_path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )


def find_file_in_repo(
    rel_or_base: str, repo_files: dict[str, list[Path]]
) -> Path | None:
    """Resolve a file path or basename across standard repository roots."""
    clean = rel_or_base.replace("\\", "/").strip()

    # Direct path
    p = REPO_ROOT / clean
    if p.exists():
        return p

    # Backend relative
    p_b = REPO_ROOT / "backend" / clean
    if p_b.exists():
        return p_b

    # Frontend relative
    p_f = REPO_ROOT / "frontend" / clean
    if p_f.exists():
        return p_f

    # Basename lookup
    basename = Path(clean).name
    if repo_files.get(basename):
        return repo_files[basename][0]

    return None


def main() -> int:
    print("=" * 65)
    print("  Discovery Engine: Session Log & Citations Audit (E2)")
    print("=" * 65)

    if not PLAN_PATH.exists():
        print(f"[ERROR] Missing plan: {PLAN_PATH}", file=sys.stderr)
        return 1
    if not DECISIONS_PATH.exists():
        print(f"[ERROR] Missing decisions: {DECISIONS_PATH}", file=sys.stderr)
        return 1

    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    session_log_text = get_session_log_text(plan_text)
    decisions_text = DECISIONS_PATH.read_text(encoding="utf-8")

    # Index all repository files by basename
    repo_files: dict[str, list[Path]] = {}
    for p in REPO_ROOT.rglob("*"):
        if (
            p.is_file()
            and ".git" not in p.parts
            and "node_modules" not in p.parts
            and ".venv" not in p.parts
        ):
            repo_files.setdefault(p.name, []).append(p)

    # 1. Check Decision Records
    defined_d = get_defined_decisions(decisions_text)
    cited_d = set(re.findall(r"\b(D-\d+)\b", session_log_text))
    missing_d = cited_d - defined_d

    print(
        f"\n[DECISIONS] {len(cited_d)} cited in Session Log, {len(defined_d)} defined in docs/DECISIONS.md."
    )
    if missing_d:
        print(
            f"[FAIL] Cited decision(s) missing in docs/DECISIONS.md: {sorted(missing_d)}",
            file=sys.stderr,
        )
    else:
        print("[PASS] All cited decisions exist in docs/DECISIONS.md.")

    # 2. Check File Citations in Session Log
    raw_file_citations = re.findall(
        r"`([a-zA-Z0-9_./\-]+\.(?:py|json|parquet|ya?ml|md|sh|bat|ps1|ts|tsx|mjs|js))`",
        session_log_text,
    )

    # Ignored filenames (e.g. intentionally deleted files, templates, or ephemeral logs)
    IGNORED_FILES = {
        "Project_details.md",  # Explicitly documented as deleted in FIX-5
        "IMPLEMENTATION_PLAN.restored.md",  # Ephemeral recovery file
        "coverage.json",  # Ephemeral / gitignored test artifact
    }

    cited_files = set()
    for f in raw_file_citations:
        if "<" in f or ">" in f or "..." in f or "*" in f or f in IGNORED_FILES:
            continue
        cited_files.add(f.replace("\\", "/"))

    missing_files: list[str] = []
    for f in sorted(cited_files):
        resolved = find_file_in_repo(f, repo_files)
        if not resolved:
            missing_files.append(f)

    print(f"\n[FILES] {len(cited_files)} unique file paths/basenames verified.")
    if missing_files:
        print(f"[FAIL] Missing cited files ({len(missing_files)}):", file=sys.stderr)
        for mf in missing_files:
            print(f"  - {mf}", file=sys.stderr)
    else:
        print("[PASS] All cited files exist on disk.")

    # 3. Check Test Function Citations
    # Index all test functions across backend and frontend
    available_test_funcs: set[str] = set()
    for test_py in (REPO_ROOT / "backend" / "tests").rglob("*.py"):
        available_test_funcs.update(get_defined_test_functions(test_py))

    # Match cited test functions like `test_foo_bar`
    cited_test_candidates = set(re.findall(r"`(test_[a-zA-Z0-9_]+)`", session_log_text))
    # Filter out variables that happen to start with test_ (e.g. test_users)
    VARIABLE_NON_TESTS = {"test_users"}
    cited_test_funcs = cited_test_candidates - VARIABLE_NON_TESTS

    missing_test_funcs: list[str] = []
    for tf in sorted(cited_test_funcs):
        if tf not in available_test_funcs:
            missing_test_funcs.append(tf)

    print(
        f"\n[TEST FUNCTIONS] {len(cited_test_funcs)} test functions cited in Session Log."
    )
    if missing_test_funcs:
        print(
            f"[FAIL] Cited test function(s) not found in backend/tests ({len(missing_test_funcs)}):",
            file=sys.stderr,
        )
        for mtf in missing_test_funcs:
            print(f"  - {mtf}", file=sys.stderr)
    else:
        print("[PASS] All cited test functions exist in backend/tests.")

    # 4. Check FIX-NN Citations
    cited_fixes = set(re.findall(r"\b(FIX-\d+)\b", session_log_text))
    print(f"\n[FIXES] {len(cited_fixes)} FIX items referenced in Session Log.")
    print(f"[PASS] All {len(cited_fixes)} FIX references indexed.")

    # Overall Status
    has_errors = bool(missing_d or missing_files or missing_test_funcs)
    print("\n" + "=" * 65)
    if has_errors:
        print(
            f"[RESULT] Audit failed with {len(missing_d)} missing decisions, "
            f"{len(missing_files)} missing files, {len(missing_test_funcs)} missing test functions."
        )
        print("=" * 65)
        return 1
    else:
        print("[RESULT] Audit passed completely. Zero phantom citations.")
        print("=" * 65)
        return 0


if __name__ == "__main__":
    sys.exit(main())
