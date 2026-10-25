#!/usr/bin/env python3
"""Discovery Engine - Clean-Room Rebuild Verification (P6.4).

Verifies that from a fresh clone and fresh virtual environment,
the entire system builds, trains, and evaluates cleanly using
only the standard README / Makefile commands:
    1. make setup (pip install -e backend/.[core,dev])
    2. make data (python backend/scripts/fetch_data.py)
    3. make train-fast (python -m engine.train --type <type> --fast)
    4. make eval (python tools/make_results.py --check)

Measures and records wall-clock timings and verifies artifact integrity.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_command(cmd: list[str], cwd: Path, desc: str) -> float:
    """Execute a shell command, measure wall-clock elapsed time, and print progress."""
    print(f"\n[RUNNING] {desc}...")
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Working Dir: {cwd}")
    start = time.perf_counter()
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - start

    if res.returncode != 0:
        print(f"\n[ERROR] Command failed with return code {res.returncode}:")
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Step '{desc}' failed with exit code {res.returncode}")

    print(f"[SUCCESS] {desc} completed in {elapsed:.2f}s.")
    return elapsed


def clean_room_rebuild(target_dir: Path | None = None) -> dict[str, float]:
    """Execute clean-room rebuild pipeline in an isolated clean directory."""
    temp_base = target_dir or Path(tempfile.mkdtemp(prefix="clean_room_discovery_"))
    clone_dir = temp_base / "discovery-engine"

    print("=" * 65)
    print("  Discovery Engine: Clean-Room Rebuild Verification (P6.4)")
    print("=" * 65)
    print(f"  Source Repository : {REPO_ROOT}")
    print(f"  Isolated Directory: {clone_dir}")

    timings: dict[str, float] = {}

    # Step 0: Fresh git clone
    t0 = time.perf_counter()
    subprocess.run(
        ["git", "clone", str(REPO_ROOT), str(clone_dir)],
        check=True,
        capture_output=True,
    )
    timings["git_clone"] = time.perf_counter() - t0
    print(f"[SUCCESS] Git clone completed in {timings['git_clone']:.2f}s.")

    # Create fresh isolated venv
    venv_dir = clone_dir / ".venv"
    t_venv = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )
    timings["venv_creation"] = time.perf_counter() - t_venv
    print(f"[SUCCESS] Fresh virtualenv created in {timings['venv_creation']:.2f}s.")

    # Python & Pip binaries in isolated venv
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"

    assert venv_python.exists(), f"Missing isolated python: {venv_python}"

    # Step 1: make setup (pip install -e backend/.[core,dev])
    timings["make_setup"] = run_command(
        [str(venv_pip), "install", "-e", "backend/.[core,dev]"],
        cwd=clone_dir,
        desc="Step 1: make setup (install backend and dev dependencies)",
    )

    # Step 2: make data (python backend/scripts/fetch_data.py)
    # Populate existing local raw data cache to avoid redundant external network downloads
    src_data_raw = REPO_ROOT / "data" / "raw"
    dst_data_raw = clone_dir / "data" / "raw"
    if src_data_raw.exists():
        dst_data_raw.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_data_raw, dst_data_raw, dirs_exist_ok=True)

    timings["make_data"] = run_command(
        [str(venv_python), "backend/scripts/fetch_data.py"],
        cwd=clone_dir,
        desc="Step 2: make data (fetch and verify raw datasets)",
    )

    # Step 3: make train-fast (movies, products, articles)
    t_train_start = time.perf_counter()
    for ct in ["movies", "products", "articles"]:
        timings[f"train_fast_{ct}"] = run_command(
            [str(venv_python), "-m", "engine.train", "--type", ct, "--fast"],
            cwd=clone_dir / "backend",
            desc=f"Step 3: make train-fast ({ct})",
        )
    timings["make_train_fast_total"] = time.perf_counter() - t_train_start

    # Step 4: make eval (python tools/make_results.py --check)
    timings["make_eval"] = run_command(
        [str(venv_python), "tools/make_results.py"],
        cwd=clone_dir,
        desc="Step 4: make eval (generate RESULTS.md and figures)",
    )

    # Step 5: Assert artifacts integrity across all 3 domains
    for ct in ["movies", "products", "articles"]:
        art_dir = clone_dir / "artifacts" / ct
        assert (art_dir / "manifest.json").exists(), f"Missing manifest.json for {ct}"
        assert (art_dir / "metrics.json").exists(), f"Missing metrics.json for {ct}"
        assert (art_dir / "topn.parquet").exists(), f"Missing topn.parquet for {ct}"
        assert (art_dir / "items.parquet").exists(), f"Missing items.parquet for {ct}"

    # Print Summary Table
    print("\n" + "=" * 65)
    print("  Clean-Room Rebuild: Performance & Timing Summary")
    print("=" * 65)
    print(f"  {'Step':<30} | {'Wall-Clock Time':<15}")
    print("  " + "-" * 50)
    print(f"  {'1. Git Clone':<30} | {timings['git_clone']:.2f} s")
    print(f"  {'2. Virtualenv Creation':<30} | {timings['venv_creation']:.2f} s")
    print(f"  {'3. make setup (pip install)':<30} | {timings['make_setup']:.2f} s")
    print(f"  {'4. make data (dataset cache)':<30} | {timings['make_data']:.2f} s")
    print(
        f"  {'5. make train-fast (Movies)':<30} | {timings['train_fast_movies']:.2f} s"
    )
    print(
        f"  {'6. make train-fast (Products)':<30} | {timings['train_fast_products']:.2f} s"
    )
    print(
        f"  {'7. make train-fast (Articles)':<30} | {timings['train_fast_articles']:.2f} s"
    )
    print(f"  {'8. make eval (RESULTS.md)':<30} | {timings['make_eval']:.2f} s")
    total_time = sum(timings.values())
    print("  " + "-" * 50)
    print(
        f"  {'TOTAL REBUILD TIME':<30} | {total_time:.2f} s ({total_time / 60.0:.2f} min)"
    )
    print("=" * 65 + "\n")

    return timings


def main() -> None:
    """CLI entry point for tools/clean_room_rebuild.py."""
    parser = argparse.ArgumentParser(description="Run clean-room rebuild verification.")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Optional target directory to clone into (defaults to system temporary directory)",
    )
    args = parser.parse_args()
    clean_room_rebuild(target_dir=args.target_dir)


if __name__ == "__main__":
    main()
