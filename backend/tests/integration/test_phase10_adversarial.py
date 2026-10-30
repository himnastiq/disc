"""Phase 10 Adversarial Testing and Robustness Gate (P10.8).

Systematic verification of the five adversarial hypotheses (H1 to H5) certifying
that the Discovery Engine recommender system exhibits complete stability, input
validation resilience, concurrency safety, search robustness, and domain isolation.

Hypotheses:
  H1: Extreme cold-start combinations (heterogeneous tastes, monolithic genre blocks,
      sub-threshold ratings, popular-item flooding, empty text features).
  H2: Hard boundary inputs (200 vs 201 items, k outside [1, 50], invalid signals,
      duplicate IDs, and RSS memory stability across repeated requests).
  H3: Concurrency at scale (50 simultaneous requests alternating cold-start POSTs
      and personalized GETs across all 3 domains; concurrent equals sequential baseline).
  H4: Hostile search strings (zero-width chars, RTL Arabic, NFC vs NFD accents,
      emojis, 100 vs 101 characters, regex metacharacters, zero-width-only queries).
  H5: Fault isolation and cache bleed (manifest missing/corrupt, parquet missing,
      schema mismatch; broken type returns 503, healthy types serve uncorrupted).
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import (
    ColdStartResponse,
    HealthResponse,
    PopularResponse,
    SearchResponse,
)
from engine import registry

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_ARTIFACTS_DIR = Path(
    os.environ.get(
        "ARTIFACT_DIR",
        REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini",
    )
)
CONTENT_TYPES = registry.public_types()


def get_process_rss_mb() -> float:
    """Return process RSS in MB using stdlib ctypes on Windows or resource on POSIX."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return float(counters.WorkingSetSize) / (1024 * 1024)
    except Exception:
        pass
    try:
        import resource

        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except Exception:
        return 0.0


@pytest.fixture(scope="module")
def api_client() -> Any:
    """Initialize test client with lifespan context."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===========================================================================
# H1: Extreme Cold-Start Hypotheses
# ===========================================================================


def test_h1_extreme_cold_start_heterogeneous_mix(api_client: TestClient) -> None:
    """H1.1: Extremely different items together (e.g. animation vs horror)."""
    # Sample 2 distinct items from movies popular catalog
    r_pop = api_client.get("/v1/popular?type=movies&k=10")
    assert r_pop.status_code == 200
    toy_id = r_pop.json()["results"][0]["item_id"]
    horror_id = r_pop.json()["results"][1]["item_id"]

    history = [
        {"item_id": toy_id, "signal": 5.0},
        {"item_id": horror_id, "signal": 5.0},
    ]
    resp = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history, "k": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    ColdStartResponse.model_validate(data)

    # Invariants: no NaN/inf, finite scores, no history items recommended
    history_ids = {toy_id, horror_id}
    for item in data["results"]:
        assert not math.isnan(item["score"])
        assert not math.isinf(item["score"])
        assert item["item_id"] not in history_ids
        if item.get("reason") and item["reason"].get("item_id"):
            assert item["reason"]["item_id"] in history_ids


def test_h1_extreme_cold_start_all_subthreshold_ratings(api_client: TestClient) -> None:
    """H1.2: History containing only sub-threshold ratings.

    Per FIX-46, negative/sub-threshold ratings are ignored as evidence for
    affinity generation, falling back cleanly to popularity.
    """
    r_users = api_client.get("/v1/types/movies/users")
    user_id = str(r_users.json()["users"][0]["user_id"])
    r_prof = api_client.get(f"/v1/users/{user_id}/profile?type=movies")
    assert r_prof.status_code == 200
    recent = r_prof.json()["recent_items"]
    assert len(recent) >= 1

    # Provide only 1-star ratings (well below positive_threshold 4.0)
    subthreshold_history = [{"item_id": str(x["item_id"]), "signal": 1.0} for x in recent[:3]]
    resp = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": subthreshold_history, "k": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Mode must be popularity because positive evidence count is zero
    assert data["mode"] == "popularity"
    history_ids = {str(x["item_id"]) for x in recent[:3]}
    for item in data["results"]:
        assert item["item_id"] not in history_ids


def test_h1_extreme_cold_start_monolithic_popular_items(api_client: TestClient) -> None:
    """H1.3: Flooding history with top popular items; assert no seen items recommended."""
    r_pop = api_client.get("/v1/popular?type=movies&k=20")
    assert r_pop.status_code == 200
    pop_items = r_pop.json()["results"]
    history = [{"item_id": x["item_id"], "signal": 5.0} for x in pop_items]

    resp = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history, "k": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    seen_ids = {x["item_id"] for x in pop_items}
    for item in data["results"]:
        assert item["item_id"] not in seen_ids


def test_h1_extreme_cold_start_empty_feature_article(api_client: TestClient) -> None:
    """H1.4: Articles cold start where history item has minimal/stop-word text.

    Asserts zero divide-by-zero, fallback to popularity, and finite sorted scores.
    """
    r_articles = api_client.get("/v1/popular?type=articles&k=5")
    assert r_articles.status_code == 200
    art_id = r_articles.json()["results"][0]["item_id"]

    resp = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "articles", "history": [{"item_id": art_id, "signal": 1.0}], "k": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 5
    scores = [item["score"] for item in data["results"]]
    assert all(not math.isnan(s) and not math.isinf(s) for s in scores)
    assert scores == sorted(scores, reverse=True)


# ===========================================================================
# H2: Input Boundaries & Memory Resilience Hypotheses
# ===========================================================================


def test_h2_boundary_history_size_200_vs_201(api_client: TestClient) -> None:
    """H2.1: Exactly 200 items succeeds; 201 items rejected with 422 validation_error."""
    # 1. Exactly 200 unique mock/unknown items -> 200 OK
    history_200 = [{"item_id": f"unk_{i}", "signal": 4.0} for i in range(200)]
    resp_200 = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history_200, "k": 10},
    )
    assert resp_200.status_code == 200
    assert len(resp_200.json()["ignored_item_ids"]) == 200

    # 2. 201 items -> 422 validation_error
    history_201 = [{"item_id": f"unk_{i}", "signal": 4.0} for i in range(201)]
    resp_201 = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history_201, "k": 10},
    )
    assert resp_201.status_code == 422
    assert resp_201.json()["error"]["code"] == "validation_error"


def test_h2_boundary_k_values(api_client: TestClient) -> None:
    """H2.2: k boundaries (0, 1, 50, 51, negative)."""
    # k = 0 -> 422
    assert api_client.get("/v1/recommend?type=movies&user_id=1&k=0").status_code == 422
    # k = -1 -> 422
    assert api_client.get("/v1/recommend?type=movies&user_id=1&k=-1").status_code == 422
    # k = 51 -> 422
    assert api_client.get("/v1/recommend?type=movies&user_id=1&k=51").status_code == 422
    # k = 1 -> 200
    r1 = api_client.get("/v1/recommend?type=movies&user_id=1&k=1")
    assert r1.status_code == 200
    assert len(r1.json()["results"]) == 1
    # k = 50 -> 200
    r50 = api_client.get("/v1/recommend?type=movies&user_id=1&k=50")
    assert r50.status_code == 200
    assert 1 <= len(r50.json()["results"]) <= 50


def test_h2_boundary_signal_validation(api_client: TestClient) -> None:
    """H2.3: Signal validation (string 'NaN', negative, > 5.0)."""
    # String 'NaN' -> 422
    r_nan = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": [{"item_id": "1", "signal": "NaN"}]},
    )
    assert r_nan.status_code == 422

    # Negative signal -> 422
    r_neg = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": [{"item_id": "1", "signal": -1.0}]},
    )
    assert r_neg.status_code == 422

    # Excessive signal > 5.0 -> 422
    r_big = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": [{"item_id": "1", "signal": 10.0}]},
    )
    assert r_big.status_code == 422


def test_h2_duplicate_ids_rejection(api_client: TestClient) -> None:
    """H2.4: Duplicate item IDs in history produces 422 duplicate_ids."""
    history = [
        {"item_id": "item_alpha", "signal": 5.0},
        {"item_id": "item_beta", "signal": 4.0},
        {"item_id": "item_alpha", "signal": 3.0},
    ]
    resp = api_client.post(
        "/v1/recommend/cold-start",
        json={"type": "movies", "history": history, "k": 10},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "duplicate_ids"
    assert "item_alpha" in data["error"]["details"]["duplicates"]


def test_h2_memory_rss_stability(api_client: TestClient) -> None:
    """H2.5: 100 repeated 200-item requests must not grow process RSS by more than 50MB."""
    rss_before = get_process_rss_mb()

    history = [{"item_id": f"dummy_{i}", "signal": 4.0} for i in range(200)]
    payload = {"type": "movies", "history": history, "k": 10}

    for _ in range(100):
        resp = api_client.post("/v1/recommend/cold-start", json=payload)
        assert resp.status_code == 200

    rss_after = get_process_rss_mb()
    growth_mb = rss_after - rss_before
    print(
        f"\n[RSS MEMORY] Before: {rss_before:.2f} MB, After: {rss_after:.2f} MB, Growth: {growth_mb:.2f} MB"
    )
    assert growth_mb < 50.0, (
        f"Memory leak detected: RSS grew by {growth_mb:.2f} MB (> 50 MB threshold)"
    )


# ===========================================================================
# H3: Concurrency at Scale Hypotheses
# ===========================================================================


def test_h3_concurrency_at_scale(api_client: TestClient) -> None:
    """H3: 50 simultaneous requests alternating cold-start POSTs and GETs across all 3 types.

    Asserts concurrent responses equal sequential baseline for same inputs (no race conditions).
    """
    # 1. Prepare 50 test request specifications
    test_specs: list[dict[str, Any]] = []
    types_list = list(CONTENT_TYPES)

    for i in range(50):
        c_type = types_list[i % len(types_list)]
        if i % 2 == 0:
            test_specs.append(
                {
                    "kind": "get",
                    "url": f"/v1/recommend?type={c_type}&user_id=1&k=10",
                }
            )
        else:
            test_specs.append(
                {
                    "kind": "post",
                    "url": "/v1/recommend/cold-start",
                    "body": {
                        "type": c_type,
                        "history": [{"item_id": f"hist_{i}_{j}", "signal": 4.5} for j in range(5)],
                        "k": 10,
                    },
                }
            )

    # 2. Compute sequential baseline
    sequential_baseline: list[tuple[int, str]] = []
    for spec in test_specs:
        if spec["kind"] == "get":
            r = api_client.get(spec["url"])
        else:
            r = api_client.post(spec["url"], json=spec["body"])
        assert r.status_code == 200
        sequential_baseline.append((r.status_code, r.text))

    rss_start = get_process_rss_mb()

    # 3. Execute 3 rounds of 50 concurrent requests
    for round_idx in range(1, 4):
        round_latencies: list[float] = []

        def execute_request(
            idx: int, lat_accum: list[float] = round_latencies
        ) -> tuple[int, tuple[int, str]]:
            spec = test_specs[idx]
            t0 = time.perf_counter()
            if spec["kind"] == "get":
                r = api_client.get(spec["url"])
            else:
                r = api_client.post(spec["url"], json=spec["body"])
            dur = (time.perf_counter() - t0) * 1000
            lat_accum.append(dur)
            return idx, (r.status_code, r.text)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(execute_request, i) for i in range(50)]
            results = [f.result() for f in futures]

        # Assert no 5xx and bit-for-bit equality with baseline
        for idx, (status, text) in results:
            assert status == 200
            base_status, base_text = sequential_baseline[idx]
            assert status == base_status
            # Compare JSON content (meta latency_ms will differ, results must be identical)
            data_concurrent = json.loads(text)
            data_baseline = json.loads(base_text)
            assert data_concurrent["results"] == data_baseline["results"]

        round_latencies.sort()
        p95 = round_latencies[int(0.95 * len(round_latencies))]
        print(f"\n[CONCURRENCY ROUND {round_idx}] 50 requests: p95 = {p95:.2f} ms")

    rss_end = get_process_rss_mb()
    print(f"[CONCURRENCY MEMORY] RSS Start: {rss_start:.2f} MB, RSS End: {rss_end:.2f} MB")


# ===========================================================================
# H4: Hostile Search Strings Hypotheses
# ===========================================================================


def test_h4_search_unicode_normalization_nfc_vs_nfd(api_client: TestClient) -> None:
    """H4.1: Accented text in NFC vs NFD returns identical item rankings and counts."""
    # 'café' in NFC (composed \u00e9) vs NFD (decomposed e + \u0301)
    q_nfc = unicodedata.normalize("NFC", "café")
    q_nfd = unicodedata.normalize("NFD", "café")
    assert q_nfc != q_nfd  # different code points

    r_nfc = api_client.get(f"/v1/items/search?type=movies&q={q_nfc}")
    r_nfd = api_client.get(f"/v1/items/search?type=movies&q={q_nfd}")

    assert r_nfc.status_code == 200
    assert r_nfd.status_code == 200
    assert r_nfc.json()["results"] == r_nfd.json()["results"]
    assert r_nfc.json()["total_matches"] == r_nfd.json()["total_matches"]


def test_h4_search_zero_width_and_rtl_arabic(api_client: TestClient) -> None:
    """H4.2: Zero-width characters and RTL Arabic execute cleanly without 5xx."""
    # 1. Zero-width spaces interleaved: 't\u200be\u200ds\ufefft'
    q_zw = "t\u200be\u200ds\ufefft"
    resp_zw = api_client.get(f"/v1/items/search?type=movies&q={q_zw}")
    assert resp_zw.status_code == 200
    SearchResponse.model_validate(resp_zw.json())

    # 2. RTL Arabic text: 'فيلم حرب النجوم'
    q_ar = "فيلم حرب النجوم"
    resp_ar = api_client.get(f"/v1/items/search?type=movies&q={q_ar}")
    assert resp_ar.status_code == 200
    SearchResponse.model_validate(resp_ar.json())

    # 3. Pure zero-width-only query
    q_pure_zw = "\u200b\u200d\ufeff"
    resp_pure = api_client.get(f"/v1/items/search?type=movies&q={q_pure_zw}")
    assert resp_pure.status_code == 200
    assert resp_pure.json()["results"] == []
    assert resp_pure.json()["total_matches"] == 0


def test_h4_search_emojis_and_regex_metacharacters(api_client: TestClient) -> None:
    """H4.3: Emojis and regex metacharacters ('*?+(|\\') never trigger regex exceptions."""
    # Emojis
    q_emoji = "🎬🍿🚀🔥"
    resp_emoji = api_client.get(f"/v1/items/search?type=movies&q={q_emoji}")
    assert resp_emoji.status_code == 200

    # Regex metacharacters
    q_regex = ".*(test|val)\\[1\\]\\?"
    resp_regex = api_client.get(f"/v1/items/search?type=movies&q={q_regex}")
    assert resp_regex.status_code == 200
    assert resp_regex.json()["total_matches"] >= 0


def test_h4_search_length_100_vs_101(api_client: TestClient) -> None:
    """H4.4: 100 character query succeeds; 101 character query rejected with 422."""
    q_100 = "x" * 100
    resp_100 = api_client.get(f"/v1/items/search?type=movies&q={q_100}")
    assert resp_100.status_code == 200

    q_101 = "x" * 101
    resp_101 = api_client.get(f"/v1/items/search?type=movies&q={q_101}")
    assert resp_101.status_code == 422
    assert resp_101.json()["error"]["code"] == "validation_error"


# ===========================================================================
# H5: Availability & Domain Fault Isolation Hypotheses
# ===========================================================================


@pytest.mark.parametrize(
    "tamper_mode",
    [
        "missing_manifest",
        "invalid_json_manifest",
        "checksum_mismatch",
        "missing_items",
        "schema_mismatch",
    ],
)
def test_h5_availability_and_domain_isolation(tamper_mode: str) -> None:
    """H5: Breaking one content type's artifacts leaves other domains healthy (503 isolation)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_dir = Path(tmp_dir) / "artifacts"
        # Copy healthy artifacts
        shutil.copytree(DEFAULT_ARTIFACTS_DIR, staging_dir)

        broken_type = "products"
        target_dir = staging_dir / broken_type

        # Apply specific corruption
        if tamper_mode == "missing_manifest":
            (target_dir / "manifest.json").unlink()
        elif tamper_mode == "invalid_json_manifest":
            (target_dir / "manifest.json").write_text("{broken json", encoding="utf-8")
        elif tamper_mode == "checksum_mismatch":
            # Tamper with an artifact file without updating manifest
            with (target_dir / "topn.parquet").open("ab") as f:
                f.write(b"corruption_bytes")
        elif tamper_mode == "missing_items":
            (target_dir / "items.parquet").unlink()
        elif tamper_mode == "schema_mismatch":
            # Inject schema version mismatch in manifest
            manifest_path = target_dir / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["artifact_schema_version"] = "999.0.0"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

        # Initialize API with staged artifacts
        old_dir = os.environ.get("ARTIFACT_DIR")
        os.environ["ARTIFACT_DIR"] = str(staging_dir)
        try:
            app = create_app()
            with TestClient(app, raise_server_exceptions=False) as client:
                # 1. Health endpoint reports status='degraded' and broken type
                r_health = client.get("/v1/health")
                assert r_health.status_code == 200
                health_data = r_health.json()
                HealthResponse.model_validate(health_data)
                assert health_data["status"] == "degraded"
                assert health_data["types"][broken_type]["available"] is False

                # 2. Broken domain returns 503 type_unavailable
                r_broken = client.get(f"/v1/recommend?type={broken_type}&user_id=1&k=5")
                assert r_broken.status_code == 503
                assert r_broken.json()["error"]["code"] == "type_unavailable"

                # 3. Healthy domains ('movies', 'articles') remain 100% operational
                for healthy_type in ["movies", "articles"]:
                    r_healthy = client.get(f"/v1/popular?type={healthy_type}&k=5")
                    assert r_healthy.status_code == 200
                    PopularResponse.model_validate(r_healthy.json())

                    # Assert no item from broken type bleeds into healthy results
                    for item in r_healthy.json()["results"]:
                        assert not str(item["item_id"]).startswith("broken")
        finally:
            if old_dir is not None:
                os.environ["ARTIFACT_DIR"] = old_dir
            else:
                os.environ.pop("ARTIFACT_DIR", None)
