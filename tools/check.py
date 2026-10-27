#!/usr/bin/env python3
"""Discovery Engine - Cross-platform quality checks runner (FIX-43).

Runs linting, formatting check, type checking, and test suite across platforms
without requiring GNU Make or Unix shell utilities:
  1. ruff check .
  2. ruff format --check .
  3. mypy engine/ api/
  4. pytest tests/ -v --tb=short
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"


def run_step(name: str, cmd: list[str], cwd: Path) -> None:
    """Execute a single check step and exit on failure."""
    cmd_str = " ".join(cmd)
    print("\n========================================================")
    print(f"RUNNING: {name}")
    print(f"COMMAND: {cmd_str}")
    print(f"CWD:     {cwd}")
    print("========================================================")

    res = subprocess.run(cmd, check=False, cwd=cwd)
    if res.returncode != 0:
        print(
            f"\n[FAILURE] {name} failed with exit code {res.returncode}.",
            file=sys.stderr,
        )
        sys.exit(res.returncode)
    print(f"[PASSED]  {name}")


def main() -> None:
    py = sys.executable

    steps = [
        ("Ruff Linter", [py, "-m", "ruff", "check", "."], BACKEND_DIR),
        (
            "Ruff Format Check",
            [py, "-m", "ruff", "format", "--check", "."],
            BACKEND_DIR,
        ),
        ("Mypy Type Checker", [py, "-m", "mypy", "engine/", "api/"], BACKEND_DIR),
        (
            "Conformance Audit Document Check",
            [py, str(REPO_ROOT / "tools" / "check_conformance.py"), "--check"],
            REPO_ROOT,
        ),
        (
            "Pytest Test Suite",
            [py, "-m", "pytest", "tests/", "-v", "--tb=short"],
            BACKEND_DIR,
        ),
    ]

    print("========================================================")
    print("Discovery Engine Quality Assurance Checks")
    print(f"Python interpreter: {py}")
    print(f"Repository root:    {REPO_ROOT}")
    print("========================================================")

    for name, cmd, cwd in steps:
        run_step(name, cmd, cwd)

    print("\n========================================================")
    print("[SUCCESS] All checks passed successfully.")
    print("========================================================")


if __name__ == "__main__":
    main()
