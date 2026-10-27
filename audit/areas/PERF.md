# AREA PERF — Performance and resources

**Verdict:** PASS WITH CAVEAT — no performance defect proven; documentation overclaim is reported under DOCS.

## Files read
- `backend/scripts/bench_api.py`
- `docs/RESULTS.md`
- `artifacts/{movies,products,articles}/metrics.json`
- `artifacts/*/manifest.json`
- `backend/api/lookups.py`
- `backend/api/main.py`

## Evidence
- `docs/RESULTS.md:207-222` reports 500 requests per endpoint:
  - movies `GET /v1/recommend` p95 **87.23 ms**, p99 151.69 ms, RSS **796.0 MB**.
  - products `GET /v1/recommend` p95 16.76 ms.
  - articles `GET /v1/recommend` p95 15.08 ms.
  - cold-start p95 5.14–5.76 ms across types.
- R8 budget is p95 < 150 ms and RSS < 2 GB; all reported p95 values pass. The movies p99 (151.69 ms) exceeds 150 ms, but the stated budget is p95, so this is a tail observation rather than a failure.
- The benchmark uses 200 sampled users per domain, warm-up, and all three domains loaded simultaneously (`RESULTS.md:226-228`).
- `api/lookups.py` precomputes profile/recency/category structures, and `topn.parquet` serves known users without live scoring.
- Artifact sizes inspected: movies 999,611 interactions / 3,883 items; products 216,994 / 8,000; articles 28 / 15. The products `max_items_in_similarity=8000` cap is the main memory control.
- `docs/RESULTS.md` regenerates identically via `python tools/make_results.py --check`.

## Caveat
- I did not rerun `scripts/bench_api.py` (500 requests × many endpoints) in this audit. The performance verdict relies on the committed benchmark output, which is generated from artifacts and is internally consistent.
- The documentation claim “actual < 5 ms / ~340 MB” in `docs/CONFORMANCE.md:81` is **not** supported by `docs/RESULTS.md:214/228` (87.23 ms / 796.4 MB). That is a docs finding (F-004), not a performance regression.
- Peak memory during training (as opposed to serving) was not independently measured.

## Recommendation
- Add a CI or nightly benchmark job with a regression threshold, and correct the CONFORMANCE R8 numbers to the generated RESULTS values.
