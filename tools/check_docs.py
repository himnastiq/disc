#!/usr/bin/env python3
"""Discovery Engine - Documentation Integrity & Honesty Checker (P11.1, E2).

Verifies that documentation adheres strictly to project rules:
  1. Broken links & images: Every relative markdown link/image resolves to an existing file.
  2. Backticked repo paths: Every cited path in code formatting exists in the repository.
  3. Commands: All documented make targets exist in Makefile, and python tools/*.py exist.
  4. Leftover markers: Zero TODO, FIXME, or XXX markers in showcase docs and README.md.
  5. Banned wording: No subjective overclaims ("decisively", "outperforms", "beats",
     "state-of-the-art", "production-ready") outside generated blocks in showcase prose.
  6. Typed numbers: No un-allowlisted decimal or percentage numbers outside generated blocks.
  7. Required phrases: Derivation statement and non-commercial notice present in
     README.md, /v1/about, docs/DEMO_SCRIPT.md, and docs/REPORT_OUTLINE.md.

Supports:
  python tools/check_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
README_PATH = REPO_ROOT / "README.md"
MAKEFILE_PATH = REPO_ROOT / "Makefile"
ALLOWLIST_PATH = REPO_ROOT / "tools" / "docs_numbers_allowlist.txt"
ABOUT_ROUTE_PATH = REPO_ROOT / "backend" / "api" / "routes" / "metadata.py"
ABOUT_TAB_PATH = REPO_ROOT / "frontend" / "components" / "tabs" / "AboutTab.tsx"

# The Honesty Rule applies strictly to showcase and reader-facing prose
PROSE_HONESTY_TARGETS = [
    README_PATH,
    DOCS_DIR / "ARCHITECTURE.md",
    DOCS_DIR / "DEMO_SCRIPT.md",
    DOCS_DIR / "REPORT_OUTLINE.md",
]

BANNED_WORDS = [
    r"\bdecisively\b",
    r"\boutperforms\b",
    r"\bbeats\b",
    r"\bstate-of-the-art\b",
    r"\bproduction-ready\b",
]


def load_allowlist() -> set[str]:
    """Load allowlisted number strings and patterns."""
    if not ALLOWLIST_PATH.exists():
        return set()
    allowed = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            allowed.add(s)
    return allowed


def load_makefile_targets() -> set[str]:
    """Extract target names from Makefile."""
    if not MAKEFILE_PATH.exists():
        return set()
    targets = set()
    for line in MAKEFILE_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([a-zA-Z0-9_-]+):", line)
        if m:
            targets.add(m.group(1))
    return targets


def strip_generated_blocks(content: str) -> str:
    """Remove text inside GENERATED blocks so honesty checks only scan prose."""
    pattern = re.compile(
        r"<!--\s*GENERATED:[a-zA-Z0-9_-]+:START\s*-->.*?<!--\s*GENERATED:[a-zA-Z0-9_-]+:END\s*-->",
        re.DOTALL,
    )
    return pattern.sub("", content)


def get_all_doc_files() -> list[Path]:
    """Find all markdown files in docs/ and root README.md."""
    files = []
    if README_PATH.exists():
        files.append(README_PATH)
    if DOCS_DIR.exists():
        files.extend(DOCS_DIR.rglob("*.md"))
    return sorted(files)


# =========================================================================
# Check Implementations
# =========================================================================


def check_links_and_images(files: list[Path]) -> list[str]:
    """Check that all relative links and image references point to existing files."""
    errors = []
    link_pattern = re.compile(
        r"\[(?:[^\]]*)\]\((?!https?://|mailto:|#|tel:)([^\s\)]+)\)"
    )
    img_pattern = re.compile(r"!\[(?:[^\]]*)\]\((?!https?://|data:)([^\s\)]+)\)")

    for f in files:
        content = f.read_text(encoding="utf-8")
        rel_f = f.relative_to(REPO_ROOT).as_posix()

        # Find links
        for m in link_pattern.finditer(content):
            target = m.group(1).split("#")[0].split("?")[0].strip()
            if not target:
                continue
            # Resolve relative to file directory
            target_path = (f.parent / target).resolve()
            if not target_path.exists():
                errors.append(
                    f"{rel_f}: Broken relative link '{target}' -> {target_path}"
                )

        # Find images
        for m in img_pattern.finditer(content):
            target = m.group(1).split("#")[0].split("?")[0].strip()
            if not target:
                continue
            target_path = (f.parent / target).resolve()
            if not target_path.exists():
                errors.append(
                    f"{rel_f}: Broken image source '{target}' -> {target_path}"
                )

    return errors


def check_backticked_paths(files: list[Path]) -> list[str]:
    """Check that backticked repo paths exist on disk."""
    errors = []
    # Match backticked strings that look like project paths
    path_pattern = re.compile(
        r"`((?:backend|frontend|tools|docs|data|artifacts|\.github)/[a-zA-Z0-9_\-\./]+)`"
    )

    # Exclude dynamic or placeholder patterns
    known_placeholders = {
        "artifacts/<type>",
        "artifacts/<type>/manifest.json",
        "artifacts/<type>/items.parquet",
        "artifacts/<type>/interactions.parquet",
        "artifacts/<type>/users.parquet",
        "artifacts/<type>/model/",
        "artifacts/<type>/topn.parquet",
        "artifacts/<type>/metrics.json",
        "artifacts/<type>/demo_users.json",
        "artifacts/<type>/data_report.json",
        "artifacts/<type>/tuning.json",
        "artifacts/movies",
        "artifacts/products",
        "artifacts/articles",
        "data/raw/<domain>",
        "docs/screenshots/<type>-<tab>.png",
        "frontend/.next/static/canary-test.js",  # Ephemeral test path in decision log
    }

    for f in files:
        content = f.read_text(encoding="utf-8")
        rel_f = f.relative_to(REPO_ROOT).as_posix()

        for m in path_pattern.finditer(content):
            p_str = m.group(1).strip()
            if (
                p_str in known_placeholders
                or "<" in p_str
                or "*" in p_str
                or "..." in p_str
            ):
                continue
            clean = p_str.split("#")[0].rstrip("/")
            resolved = REPO_ROOT / clean
            if not resolved.exists():
                errors.append(f"{rel_f}: Backticked path does not exist: `{p_str}`")

    return errors


def check_commands(files: list[Path]) -> list[str]:
    """Check documented make targets and python tools/*.py commands inside code spans."""
    errors = []
    makefile_targets = load_makefile_targets()
    make_cmd_pattern = re.compile(r"`make\s+([a-zA-Z0-9_-]+)`")
    tool_cmd_pattern = re.compile(r"`python\s+tools/([a-zA-Z0-9_-]+\.py)`")

    for f in files:
        content = f.read_text(encoding="utf-8")
        rel_f = f.relative_to(REPO_ROOT).as_posix()

        # Check make targets if Makefile exists
        if makefile_targets:
            for m in make_cmd_pattern.finditer(content):
                target = m.group(1)
                if target.startswith("-"):
                    continue
                if target not in makefile_targets:
                    errors.append(
                        f"{rel_f}: Documented make target '{target}' does not exist in Makefile"
                    )

        # Check python tools/*.py
        for m in tool_cmd_pattern.finditer(content):
            script_name = m.group(1)
            script_path = REPO_ROOT / "tools" / script_name
            if not script_path.exists():
                errors.append(
                    f"{rel_f}: Documented tool script 'tools/{script_name}' does not exist"
                )

    return errors


def check_leftover_markers() -> list[str]:
    """Check for leftover TODO, FIXME, or XXX markers in showcase docs."""
    errors = []
    marker_pattern = re.compile(r"\b(TODO|FIXME|XXX)\b")

    for f in PROSE_HONESTY_TARGETS:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        rel_f = f.relative_to(REPO_ROOT).as_posix()
        for idx, line in enumerate(content.splitlines(), start=1):
            if marker_pattern.search(line):
                errors.append(
                    f"{rel_f}:{idx}: Leftover marker found: {line.strip()[:60]}"
                )

    return errors


def check_banned_wording() -> list[str]:
    """Check for prohibited subjective superlatives outside generated blocks in showcase prose."""
    errors = []

    for f in PROSE_HONESTY_TARGETS:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        prose_only = strip_generated_blocks(content)
        rel_f = f.relative_to(REPO_ROOT).as_posix()

        for pat in BANNED_WORDS:
            regex = re.compile(pat, re.IGNORECASE)
            for idx, line in enumerate(prose_only.splitlines(), start=1):
                m = regex.search(line)
                if m:
                    errors.append(
                        f"{rel_f}:{idx}: Banned subjective word '{m.group(0)}' in line: {line.strip()[:60]}"
                    )

    return errors


def check_unallowlisted_numbers() -> list[str]:
    """Check for typed decimal or percentage numbers outside generated blocks in showcase prose."""
    errors = []
    allowlist = load_allowlist()

    decimal_pattern = re.compile(r"\b\d+\.\d+\b")
    pct_pattern = re.compile(r"\b\d+%\b")

    for f in PROSE_HONESTY_TARGETS:
        if not f.exists():
            continue

        content = f.read_text(encoding="utf-8")
        prose_only = strip_generated_blocks(content)
        rel_f = f.relative_to(REPO_ROOT).as_posix()

        in_code_block = False
        for idx, line in enumerate(prose_only.splitlines(), start=1):
            strip_line = line.strip()
            if strip_line.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Skip table lines
            if strip_line.startswith("|"):
                continue

            for m in decimal_pattern.finditer(line):
                val = m.group(0)
                if val not in allowlist and not any(a in line for a in allowlist):
                    if (
                        "ACM" in line
                        or "SIGIR" in line
                        or "KDD" in line
                        or "doi.org" in line
                    ):
                        continue
                    errors.append(
                        f"{rel_f}:{idx}: Un-allowlisted decimal '{val}' in prose: {line.strip()[:60]}"
                    )

            for m in pct_pattern.finditer(line):
                val = m.group(0)
                if val not in allowlist and not any(a in line for a in allowlist):
                    errors.append(
                        f"{rel_f}:{idx}: Un-allowlisted percentage '{val}' in prose: {line.strip()[:60]}"
                    )

    return errors


def check_required_phrases() -> list[str]:
    """Check required derivation and educational notices in specified files."""
    errors = []
    targets = [
        README_PATH,
        ABOUT_ROUTE_PATH,
        ABOUT_TAB_PATH,
        DOCS_DIR / "DEMO_SCRIPT.md",
        DOCS_DIR / "REPORT_OUTLINE.md",
    ]

    req_terms = [
        ("Recommenders", "reference to Recommenders project"),
        ("MIT", "MIT License citation"),
        ("non-commercial", "non-commercial notice"),
    ]

    for t in targets:
        if not t.exists():
            errors.append(
                f"Missing required documentation file: {t.relative_to(REPO_ROOT).as_posix()}"
            )
            continue

        content = t.read_text(encoding="utf-8").lower()
        rel_t = t.relative_to(REPO_ROOT).as_posix()

        terms_to_check = (
            [
                ("MIT", "MIT License citation"),
                ("non-commercial", "non-commercial notice"),
            ]
            if t == README_PATH
            else req_terms
        )

        for term, desc in terms_to_check:
            if term.lower() not in content:
                errors.append(f"{rel_t}: Missing required phrase ({desc}): '{term}'")

    return errors


def main() -> int:
    print("=" * 65)
    print("  Discovery Engine: Documentation Honesty & Integrity (P11.1, E2)")
    print("=" * 65)

    files = get_all_doc_files()
    print(f"Scanning {len(files)} markdown documentation files across repository...")

    all_errors: list[str] = []

    # 1. Links & Images
    err_links = check_links_and_images(files)
    all_errors.extend(err_links)
    print(
        f"[{'FAIL' if err_links else 'PASS'}] Links & Images: {len(err_links)} broken"
    )

    # 2. Backticked Paths
    err_paths = check_backticked_paths(files)
    all_errors.extend(err_paths)
    print(
        f"[{'FAIL' if err_paths else 'PASS'}] Backticked Paths: {len(err_paths)} invalid"
    )

    # 3. Commands & Scripts
    err_cmds = check_commands(files)
    all_errors.extend(err_cmds)
    print(
        f"[{'FAIL' if err_cmds else 'PASS'}] Commands & Targets: {len(err_cmds)} missing"
    )

    # 4. Leftover Markers
    err_markers = check_leftover_markers()
    all_errors.extend(err_markers)
    print(
        f"[{'FAIL' if err_markers else 'PASS'}] Leftover Markers: {len(err_markers)} found"
    )

    # 5. Banned Words
    err_words = check_banned_wording()
    all_errors.extend(err_words)
    print(
        f"[{'FAIL' if err_words else 'PASS'}] Banned Superlatives: {len(err_words)} found"
    )

    # 6. Un-allowlisted Numbers
    err_nums = check_unallowlisted_numbers()
    all_errors.extend(err_nums)
    print(
        f"[{'FAIL' if err_nums else 'PASS'}] Typed Numbers Audit: {len(err_nums)} un-allowlisted"
    )

    # 7. Required Phrases
    err_phrases = check_required_phrases()
    all_errors.extend(err_phrases)
    print(
        f"[{'FAIL' if err_phrases else 'PASS'}] Required Phrases Audit: {len(err_phrases)} missing"
    )

    print("=" * 65)
    if all_errors:
        print(f"[FAIL] Documentation checks failed with {len(all_errors)} issues:\n")
        for e in all_errors[:20]:
            print(f"  - {e}")
        if len(all_errors) > 20:
            print(f"  ... and {len(all_errors) - 20} more issues.")
        return 1

    print("[SUCCESS] All documentation integrity and honesty checks passed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
