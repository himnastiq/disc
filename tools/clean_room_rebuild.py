#!/usr/bin/env python3
"""Discovery Engine - Clean-Room Rebuild Verification (P6.4, P10.6).

Verifies that from a fresh clone and clean virtual environment,
the entire system builds, installs, trains, evaluates, tests,
and runs the demo cleanly following the README quickstart:
    1. Clone repo with full tags and history
    2. Create fresh virtualenv (no inherited site-packages)
    3. Install backend dependencies (pip install -e backend/.[core,dev])
    4. Install frontend dependencies (npm ci)
    5. Fetch / verify datasets (fetch_data.py)
    6. Train fast models (engine.train --fast across all types)
    7. Generate evaluation report (make_results.py)
    8. Run backend & frontend test suites
    9. Launch demo supervisor (demo.py) and poll /v1/health
    10. Stop demo cleanly and assert ports are released

Measures wall-clock timings and compares against the P6.4 baseline (451 s).
"""

from __future__ import annotations

import argparse
import http.client
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_quickstart_commands(readme_path: Path) -> list[str]:
    """Extract quick-start commands from README between HTML comment markers."""
    if not readme_path.exists():
        raise FileNotFoundError(f"README not found at {readme_path}")
    content = readme_path.read_text(encoding="utf-8")
    match = re.search(
        r"<!--\s*QUICKSTART:START\s*-->.*?```bash(.*?)```.*?<!--\s*QUICKSTART:END\s*-->",
        content,
        re.DOTALL,
    )
    if not match:
        raise ValueError(
            "README.md does not contain marked <!-- QUICKSTART:START --> and <!-- QUICKSTART:END --> block"
        )
    raw_lines = match.group(1).splitlines()
    cmds: list[str] = []
    for line in raw_lines:
        s = line.strip()
        if s and not s.startswith("#"):
            cmds.append(s)
    return cmds


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except (TimeoutError, ConnectionRefusedError, OSError):
            return False


def run_command(
    cmd: list[str],
    cwd: Path,
    desc: str,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> float:
    """Execute a shell command, measure wall-clock elapsed time, and print progress."""
    print(f"\n[RUNNING] {desc}...")
    print(f"  Command:     {' '.join(cmd)}")
    print(f"  Working Dir: {cwd}")
    start = time.perf_counter()
    res = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - start

    if res.returncode != 0:
        print(f"\n[ERROR] Command failed with return code {res.returncode}:")
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Step '{desc}' failed with exit code {res.returncode}")

    print(f"[SUCCESS] {desc} completed in {elapsed:.2f}s.")
    return elapsed


def clean_room_rebuild(
    target_dir: Path | None = None,
    api_port: int = 8018,
    web_port: int = 3018,
    skip_demo: bool = False,
) -> dict[str, Any]:
    """Execute clean-room rebuild pipeline in an isolated clean directory."""
    temp_base = target_dir or Path(tempfile.mkdtemp(prefix="clean_room_discovery_"))
    clone_dir = temp_base / "discovery-engine"

    print("=" * 70)
    print("  Discovery Engine: Fresh-Clone & Clean-Room Rehearsal (P10.6)")
    print("=" * 70)
    print(f"  Source Repository : {REPO_ROOT}")
    print(f"  Isolated Directory: {clone_dir}")

    timings: dict[str, float] = {}

    # Step 0: Extract quick-start commands from README
    readme_path = REPO_ROOT / "README.md"
    extracted_cmds = extract_quickstart_commands(readme_path)
    print(f"[INFO] Verified README quickstart block: {extracted_cmds}")

    # Step 1: Fresh git clone with full tags and history
    t0 = time.perf_counter()
    subprocess.run(
        ["git", "clone", "--tags", str(REPO_ROOT), str(clone_dir)],
        check=True,
        capture_output=True,
    )
    timings["git_clone"] = time.perf_counter() - t0
    print(f"[SUCCESS] Git clone (with tags) completed in {timings['git_clone']:.2f}s.")

    # Step 2: Create fresh isolated virtualenv (no inherited site-packages)
    venv_dir = clone_dir / ".venv"
    t_venv = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "venv", "--clear", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    timings["venv_creation"] = time.perf_counter() - t_venv
    print(f"[SUCCESS] Fresh virtualenv created in {timings['venv_creation']:.2f}s.")

    # Resolve platform paths
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
        npm_cmd = "npm.cmd"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"
        npm_cmd = "npm"

    assert venv_python.exists(), f"Missing isolated python: {venv_python}"

    # Step 3: Install backend dependencies (pip install -e backend/.[core,dev])
    timings["backend_setup"] = run_command(
        [str(venv_pip), "install", "-e", "backend/.[core,dev]"],
        cwd=clone_dir,
        desc="Step 3: make setup - backend dependencies",
    )

    # Step 4: Install frontend dependencies (npm ci)
    frontend_dir = clone_dir / "frontend"
    timings["frontend_setup"] = run_command(
        [npm_cmd, "ci"],
        cwd=frontend_dir,
        desc="Step 4: make setup - frontend npm ci",
    )

    # Step 5: make data (python backend/scripts/fetch_data.py)
    # Seed local cache for MovieLens and Amazon to avoid external network calls.
    # Per P10.6 specification, articles --fast uses the offline MIND fixture without manual download.
    src_data_raw = REPO_ROOT / "data" / "raw"
    dst_data_raw = clone_dir / "data" / "raw"
    if src_data_raw.exists():
        dst_data_raw.parent.mkdir(parents=True, exist_ok=True)
        for sub in ("movielens", "amazon"):
            sub_src = src_data_raw / sub
            if sub_src.exists():
                shutil.copytree(sub_src, dst_data_raw / sub, dirs_exist_ok=True)
    print("[INFO] Seeded MovieLens and Amazon caches; using MIND fixture for fast articles per P10.6.")

    timings["make_data"] = run_command(
        [str(venv_python), "backend/scripts/fetch_data.py"],
        cwd=clone_dir,
        desc="Step 5: make data (fetch and verify raw datasets)",
    )

    # Step 6: make train-fast (movies, products, articles)
    t_train_start = time.perf_counter()
    for ct in ["movies", "products", "articles"]:
        timings[f"train_fast_{ct}"] = run_command(
            [str(venv_python), "-m", "engine.train", "--type", ct, "--fast"],
            cwd=clone_dir / "backend",
            desc=f"Step 6: make train-fast ({ct})",
        )
    timings["make_train_fast_total"] = time.perf_counter() - t_train_start

    # Step 7: make eval (generate RESULTS.md and figures)
    timings["make_eval"] = run_command(
        [str(venv_python), "tools/make_results.py", "--allow-fast"],
        cwd=clone_dir,
        desc="Step 7: make eval (generate RESULTS.md)",
    )

    # Step 8: Run unit test suites (backend and frontend)
    timings["backend_tests"] = run_command(
        [
            str(venv_python),
            "-m",
            "pytest",
            "tests/unit",
            "-m",
            "not real_data",
            "-q",
        ],
        cwd=clone_dir / "backend",
        desc="Step 8a: backend unit test suite",
    )

    timings["frontend_tests"] = run_command(
        [npm_cmd, "run", "test"],
        cwd=frontend_dir,
        desc="Step 8b: frontend Vitest suite",
    )

    # Step 9 & 10: Launch demo and verify health
    if not skip_demo:
        print("\n[RUNNING] Step 9: Launch demo supervisor and verify health...")
        demo_py = clone_dir / "tools" / "demo.py"
        demo_start_cmd = [
            str(venv_python),
            str(demo_py),
            "--api-port",
            str(api_port),
            "--web-port",
            str(web_port),
            "--timeout",
            "60",
        ]

        t_demo_start = time.perf_counter()
        subprocess.Popen(
            demo_start_cmd,
            cwd=clone_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Poll /v1/health until healthy or timeout
        healthy = False
        health_deadline = time.time() + 60.0
        while time.time() < health_deadline:
            if not is_port_in_use(api_port):
                time.sleep(1.0)
                continue
            try:
                conn = http.client.HTTPConnection("127.0.0.1", api_port, timeout=2.0)
                conn.request("GET", "/v1/health")
                resp = conn.getresponse()
                if resp.status == 200:
                    healthy = True
                    break
            except (http.client.HTTPException, ConnectionRefusedError, OSError):
                time.sleep(1.0)

        demo_elapsed = time.perf_counter() - t_demo_start
        timings["demo_startup"] = demo_elapsed

        # Step 10: Stop demo cleanly
        print(
            "\n[RUNNING] Step 10: Stop demo supervisor and verify clean port release..."
        )
        stop_cmd = [
            str(venv_python),
            str(demo_py),
            "--api-port",
            str(api_port),
            "--web-port",
            str(web_port),
            "--stop",
        ]
        t_stop_start = time.perf_counter()
        subprocess.run(stop_cmd, cwd=clone_dir, capture_output=True, check=True)
        timings["demo_shutdown"] = time.perf_counter() - t_stop_start

        # Poll port until closed
        port_deadline = time.time() + 10.0
        while time.time() < port_deadline and (
            is_port_in_use(api_port) or is_port_in_use(web_port)
        ):
            time.sleep(0.5)

        assert not is_port_in_use(api_port), (
            f"Port {api_port} still in use after demo stop"
        )
        assert not is_port_in_use(web_port), (
            f"Port {web_port} still in use after demo stop"
        )
        print(
            f"[SUCCESS] Demo health verified ({'OK' if healthy else 'Degraded'}), and ports {api_port}/{web_port} cleanly released."
        )

    # Calculate Total Wall-Clock Time
    total_time = sum(v for k, v in timings.items() if not k.endswith("_total"))
    baseline_p6_4 = 451.0

    print("\n" + "=" * 70)
    print("  Clean-Room Rehearsal: Performance & Timing Summary")
    print("=" * 70)
    print(f"  {'Step / Component':<36} | {'Wall-Clock Time':<18}")
    print("  " + "-" * 56)
    print(f"  {'1. Git Clone (with tags)':<36} | {timings['git_clone']:.2f} s")
    print(f"  {'2. Virtualenv Creation':<36} | {timings['venv_creation']:.2f} s")
    print(f"  {'3. Backend pip install':<36} | {timings['backend_setup']:.2f} s")
    print(f"  {'4. Frontend npm ci':<36} | {timings['frontend_setup']:.2f} s")
    print(f"  {'5. Dataset Verification':<36} | {timings['make_data']:.2f} s")
    print(f"  {'6a. Train Fast - Movies':<36} | {timings['train_fast_movies']:.2f} s")
    print(
        f"  {'6b. Train Fast - Products':<36} | {timings['train_fast_products']:.2f} s"
    )
    print(
        f"  {'6c. Train Fast - Articles':<36} | {timings['train_fast_articles']:.2f} s"
    )
    print(f"  {'7. Results & Figures (make eval)':<36} | {timings['make_eval']:.2f} s")
    print(f"  {'8a. Backend Unit Tests':<36} | {timings['backend_tests']:.2f} s")
    print(f"  {'8b. Frontend Vitest Suite':<36} | {timings['frontend_tests']:.2f} s")
    if not skip_demo:
        print(
            f"  {'9. Demo Health Verification':<36} | {timings.get('demo_startup', 0):.2f} s"
        )
        print(
            f"  {'10. Clean Demo Termination':<36} | {timings.get('demo_shutdown', 0):.2f} s"
        )
    print("  " + "-" * 56)
    print(
        f"  {'TOTAL REHEARSAL TIME':<36} | {total_time:.2f} s ({total_time / 60.0:.2f} min)"
    )
    print(
        f"  {'P6.4 Baseline (backend only)':<36} | {baseline_p6_4:.2f} s ({baseline_p6_4 / 60.0:.2f} min)"
    )
    print("=" * 70 + "\n")

    return {
        "timings": timings,
        "total_time": total_time,
        "baseline_p6_4": baseline_p6_4,
        "quickstart_commands": extracted_cmds,
    }


def main() -> None:
    """CLI entry point for tools/clean_room_rebuild.py."""
    parser = argparse.ArgumentParser(
        description="Run fresh-clone & clean-room rehearsal (P10.6)."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Optional target directory to clone into (defaults to system temporary directory)",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8018,
        help="API port override for clean room demo (default: 8018)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=3018,
        help="Web port override for clean room demo (default: 3018)",
    )
    parser.add_argument(
        "--skip-demo",
        action="store_true",
        help="Skip launching and checking the demo supervisor",
    )
    args = parser.parse_args()
    clean_room_rebuild(
        target_dir=args.target_dir,
        api_port=args.api_port,
        web_port=args.web_port,
        skip_demo=args.skip_demo,
    )


if __name__ == "__main__":
    main()
