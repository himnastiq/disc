"""Discovery Engine - Startup Latency Benchmark (FIX-57).

Measures per-domain initialization and total FastAPI lifespan startup to first request
across production artifacts, verifying compliance with the sub-20s startup SLA.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.lookups import build_type_lookups  # noqa: E402
from api.main import create_app  # noqa: E402
from api.search import LazySearchIndex  # noqa: E402
from engine import registry  # noqa: E402
from engine.artifacts import load_artifacts, verify_artifacts  # noqa: E402
from engine.config import resolve_serving_config  # noqa: E402

DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"
DEFAULT_TARGET_S = 20.0


def measure_domain_breakdown(artifacts_dir: Path) -> list[dict[str, float | str]]:
    """Measure detailed component timings for each available content type."""
    rows: list[dict[str, float | str]] = []
    for ctype in registry.public_types():
        cdir = artifacts_dir / ctype
        if not cdir.exists():
            continue

        t0 = time.perf_counter()
        verify_artifacts(cdir)
        t1 = time.perf_counter()
        loaded = load_artifacts(cdir, verify=False)
        t2 = time.perf_counter()
        spec = resolve_serving_config(ctype, cdir)
        model = registry.build_model(spec)
        model.load(loaded.model_dir)
        t3 = time.perf_counter()
        _ = build_type_lookups(spec, loaded)
        t4 = time.perf_counter()
        _ = LazySearchIndex(loaded.items, loaded.interactions)
        t5 = time.perf_counter()

        rows.append(
            {
                "domain": ctype,
                "verify": round(t1 - t0, 3),
                "load": round(t2 - t1, 3),
                "model": round(t3 - t2, 3),
                "lookups": round(t4 - t3, 3),
                "search": round(t5 - t4, 3),
                "total": round(t5 - t0, 3),
            }
        )
    return rows


def measure_app_startup(
    artifacts_dir: Path, target_s: float = DEFAULT_TARGET_S
) -> tuple[float, float, float, bool]:
    """Measure full FastAPI application lifespan startup and first-request latency.

    Returns:
        (lifespan_time, first_req_time, total_time, passed)
    """
    import os

    os.environ["ARTIFACT_DIR"] = str(artifacts_dir)

    t0 = time.perf_counter()
    app = create_app()
    with TestClient(app) as client:
        t1 = time.perf_counter()
        resp = client.get("/health")
        t2 = time.perf_counter()

        if resp.status_code != 200:
            raise RuntimeError(f"Health check failed with HTTP {resp.status_code}: {resp.text}")

        lifespan_s = t1 - t0
        first_req_s = t2 - t1
        total_s = t2 - t0
        passed = total_s <= target_s

        return lifespan_s, first_req_s, total_s, passed


def main() -> int:
    """CLI entry point for measure_startup."""
    parser = argparse.ArgumentParser(
        description="Discovery Engine - Measure startup latency against sub-20s budget."
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Path to artifacts root directory",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_TARGET_S,
        help="Target startup budget in seconds (default: 20.0s)",
    )
    args = parser.parse_args()

    art_dir = args.artifacts_dir.resolve()
    target_s = args.target

    print("=" * 72)
    print("  Discovery Engine: Startup Benchmark (FIX-57)")
    print("=" * 72)
    print(f"  Artifacts Directory : {art_dir}")
    print(f"  Target Budget       : {target_s:.1f} s")
    print("-" * 72)

    # 1. Component breakdown per domain
    domain_rows = measure_domain_breakdown(art_dir)
    print("\n  Per-Domain Component Breakdown:")
    header = f"  {'Domain':<12} | {'Verify':>8} | {'Load':>8} | {'Model':>8} | {'Lookups':>8} | {'Search':>8} | {'Total':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    sum_lookups = 0.0
    sum_total = 0.0
    for r in domain_rows:
        sum_lookups += float(r["lookups"])
        sum_total += float(r["total"])
        print(
            f"  {r['domain']:<12} | {r['verify']:>7.2f}s | {r['load']:>7.2f}s | {r['model']:>7.2f}s | {r['lookups']:>7.2f}s | {r['search']:>7.2f}s | {r['total']:>7.2f}s"
        )
    print("  " + "-" * (len(header) - 2))
    print(
        f"  {'Cumulative':<12} | {'':>8} | {'':>8} | {'':>8} | {sum_lookups:>7.2f}s | {'':>8} | {sum_total:>7.2f}s\n"
    )

    # 2. Whole application lifespan startup & first request
    lifespan_s, first_req_s, total_s, passed = measure_app_startup(art_dir, target_s)
    status_str = "PASS" if passed else "FAIL"

    print("  Application Startup Timing:")
    print("  " + "-" * 40)
    print(f"  Lifespan Init       : {lifespan_s:.3f} s")
    print(f"  First Request (/health): {first_req_s:.3f} s")
    print(f"  Total To First Req  : {total_s:.3f} s")
    print(f"  Budget Status (< {target_s:.1f}s): [{status_str}]")
    print("=" * 72 + "\n")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
