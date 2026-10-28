#!/usr/bin/env python3
"""Check tracked files git hygiene (FIX-53).

Fails if any tracked git file:
  1. is under artifacts*/ or data/ (except tests/fixtures/artifacts_mini)
  2. is over 5 MB (5,242,880 bytes)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def is_forbidden_path(rel_path: str) -> bool:
    """Return True if relative path is under forbidden directory."""
    norm = rel_path.replace("\\", "/").strip("/")

    # Exception allowed for mini artifacts fixture
    if "tests/fixtures/artifacts_mini" in norm:
        return False

    parts = norm.split("/")
    # Check if root or any directory component is under artifacts* or data
    if parts[0].startswith("artifacts") or parts[0] == "data":
        return True
    for part in parts[:-1]:
        if part.startswith("artifacts") or part == "data":
            return True
    return False


def get_tracked_files_with_sizes(repo_root: Path = REPO_ROOT) -> list[tuple[str, int]]:
    """Return list of (rel_path, size_in_bytes) for all tracked files in git index."""
    # git ls-files -s outputs: <mode> <sha> <stage>\t<path>
    res = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    results: list[tuple[str, int]] = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        meta, sep, path = line.partition("\t")
        if not sep:
            continue
        path = path.strip()
        disk_path = repo_root / path
        if disk_path.is_file():
            size = disk_path.stat().st_size
        else:
            # If deleted on disk, query git object size
            parts = meta.split()
            sha = parts[1] if len(parts) > 1 else ""
            if sha:
                sz_res = subprocess.run(
                    ["git", "cat-file", "-s", sha],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                size = int(sz_res.stdout.strip()) if sz_res.returncode == 0 else 0
            else:
                size = 0
        results.append((path, size))
    return results


def check_tracked_files(repo_root: Path = REPO_ROOT) -> list[str]:
    """Check git tracked files against hygiene rules; return list of violation descriptions."""
    violations: list[str] = []
    tracked = get_tracked_files_with_sizes(repo_root)

    for path, size in tracked:
        if is_forbidden_path(path):
            violations.append(
                f"Forbidden tracked file under artifacts*/ or data/: {path}"
            )
        if size > MAX_FILE_SIZE_BYTES:
            size_mb = size / (1024 * 1024)
            violations.append(
                f"File exceeds 5 MB limit ({size_mb:.2f} MB > 5.00 MB): {path}"
            )

    return violations


def main() -> None:
    violations = check_tracked_files(REPO_ROOT)
    if violations:
        print("[ERROR] Tracked file hygiene check failed!", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        sys.exit(1)

    print(
        "[SUCCESS] Tracked file hygiene check passed. Zero forbidden or oversize tracked files."
    )


if __name__ == "__main__":
    main()
