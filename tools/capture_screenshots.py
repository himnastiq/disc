#!/usr/bin/env python3
"""Discovery Engine - Screenshot Automation Supervisor (P11.6).

Produces all 22 deterministic documentation and showcase screenshots from
final artifacts and production build via Playwright.

Usage:
    python tools/capture_screenshots.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
SCREENSHOTS_DIR = REPO_ROOT / "docs" / "screenshots"

EXPECTED_FILES = [
    # Movies (7)
    "movies-foryou.png",
    "movies-compare.png",
    "movies-coldstart.png",
    "movies-evaluation.png",
    "movies-about.png",
    "movies-drawer.png",
    "movies-foryou-mobile.png",
    # Products (7)
    "products-foryou.png",
    "products-compare.png",
    "products-coldstart.png",
    "products-evaluation.png",
    "products-about.png",
    "products-drawer.png",
    "products-foryou-mobile.png",
    # Articles (7)
    "articles-foryou.png",
    "articles-compare.png",
    "articles-coldstart.png",
    "articles-evaluation.png",
    "articles-about.png",
    "articles-drawer.png",
    "articles-foryou-mobile.png",
    # Theme (1)
    "theme-dark.png",
]


def get_python_executable() -> str:
    venv_py_win = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    venv_py_unix = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_py_win.exists():
        return str(venv_py_win)
    if venv_py_unix.exists():
        return str(venv_py_unix)
    return sys.executable


def get_node_executable() -> str:
    return "node.exe" if sys.platform == "win32" else "node"


def is_server_running(url: str = "http://localhost:3000") -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture UI showcase screenshots via Playwright"
    )
    parser.add_argument(
        "--skip-start",
        action="store_true",
        help="Skip starting demo if already running",
    )
    args = parser.parse_args()

    python_bin = get_python_executable()
    node_bin = get_node_executable()
    demo_script = REPO_ROOT / "tools" / "demo.py"

    started_demo = False
    if not args.skip_start and not is_server_running():
        print("[CAPTURE] Demo not running. Launching demo server via tools/demo.py...")
        start_res = subprocess.run(
            [python_bin, str(demo_script), "--no-wait", "--timeout", "60"],
            cwd=REPO_ROOT,
            check=False,
        )
        if start_res.returncode != 0:
            print("[ERROR] Failed to launch demo supervisor.", file=sys.stderr)
            return 1
        started_demo = True

    try:
        print("[CAPTURE] Executing Playwright screenshot capture script...")
        capture_script = FRONTEND_DIR / "scripts" / "capture_screenshots.ts"
        env = os.environ.copy()
        env["PLAYWRIGHT_TEST_BASE_URL"] = "http://localhost:3000"

        res = subprocess.run(
            [node_bin, "--experimental-strip-types", str(capture_script)],
            cwd=FRONTEND_DIR,
            env=env,
            check=False,
        )
        if res.returncode != 0:
            print("[ERROR] Screenshot capture failed.", file=sys.stderr)
            return 1

        print("\n[VERIFICATION] Verifying all 22 required screenshots...")
        missing: list[str] = []
        oversized: list[str] = []

        from PIL import Image

        for fname in EXPECTED_FILES:
            fpath = SCREENSHOTS_DIR / fname
            if not fpath.exists():
                missing.append(fname)
            else:
                sz = fpath.stat().st_size
                if sz > 800 * 1024:
                    print(f"  [OPTIMIZE] Optimizing {fname} ({sz / 1024:.1f} KB)...")
                    with Image.open(fpath) as im:
                        q = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                        q.save(fpath, format="PNG", optimize=True)
                    new_sz = fpath.stat().st_size
                    print(f"    -> Reduced to {new_sz / 1024:.1f} KB")
                    sz = new_sz

                if sz > 1024 * 1024:
                    oversized.append(f"{fname} ({sz / 1024:.1f} KB)")

        if missing:
            print(
                f"[ERROR] Missing {len(missing)} screenshots: {missing}",
                file=sys.stderr,
            )
            return 1
        if oversized:
            print(
                f"[ERROR] Found oversized screenshots (>1MB): {oversized}",
                file=sys.stderr,
            )
            return 1

        print(
            f"[SUCCESS] All {len(EXPECTED_FILES)} screenshots verified on disk under 1 MB."
        )
        return 0

    finally:
        if started_demo:
            print("[CAPTURE] Stopping demo server processes...")
            subprocess.run(
                [python_bin, str(demo_script), "--stop", "--force"],
                cwd=REPO_ROOT,
                check=False,
            )


if __name__ == "__main__":
    sys.exit(main())
