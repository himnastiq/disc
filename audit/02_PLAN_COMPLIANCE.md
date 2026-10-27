# Plan Compliance — P0.1 through P7.13

**Source:** `IMPLEMENTATION_PLAN.md` (read in full, including the Session Log).
**Scope:** Phases 0–7 only. Phases 8+ are out of scope and are not counted as defects.
**Verdicts:** PASS / PARTIAL / FAIL / BLOCKED.

**Summary:** 87 tasks audited — **76 PASS, 8 PARTIAL, 2 FAIL, 1 BLOCKED**.
- FAIL: P0.3 (no dependency lock), P5.3 (real-data R2 acceptance not met; plan marker still `[ ]`).
- BLOCKED: P5.1 (real MIND files unavailable; documented manual step).
- PARTIAL: P0.8, P3.8, P4.2, P5.8, P5.12, P6.3, P6.5, P7.3.

## Phase 0

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P0.1 | [x] | PASS | Git initialized; `.gitignore` covers Python/Node/data/artifacts/.env/IDE; MIT `LICENSE` present. |
| P0.2 | [x] | PASS | `backend/{discovery,engine,api,tests}`, `frontend/`, `docs/`, `tools/`, `artifacts/`, `data/` exist with package `__init__.py` files. |
| P0.3 | [x] | **FAIL** | `backend/pyproject.toml:11-46` uses lower bounds only; no `uv.lock`/pinned requirements. `.gitignore:70-71` falsely says lock files are committed. F-012. |
| P0.4 | [x] | PASS | All required `Makefile` targets exist. `make` itself is unavailable on this Windows host; underlying commands were run directly. |
| P0.5 | [x] | PASS | `ruff`/`mypy` strict for engine/api, vendored exclusions, `.pre-commit-config.yaml` present; lint/format/mypy all green. |
| P0.6 | [x] | PASS | `tools/progress.py` parses phase sections/markers and rewrites the dashboard; `test_progress.py` covers it; CI checks no diff. |
| P0.7 | [x] | PASS | `docs/` contains ATTRIBUTION, DATASETS, DECISIONS, ARCHITECTURE, RESULTS, DEMO_SCRIPT and VENDORED_FILES. |
| P0.8 | [x] | **PARTIAL** | `fetch_data.py --help`/`--dry-run` work and manual steps are printed, but downloads verify only byte count (`fetch_data.py:98-110`), not checksums. F-001. |
| P0.9 | [x] | PASS | `.github/workflows/ci.yml` runs backend lint/type/vendored/progress/pytest; frontend job is explicitly disabled until Phase 8. It runs steps directly rather than `make check`, but covers the same checks. |
| P0.10 | [x] | PASS | Session Log records environment/commands; current suite is green (439 passed, 1 skipped). |
| P0.11 | [x] | PASS | Session Log contains the Phase 0 gate entry. |

## Phase 1

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P1.1 | [x] | PASS | Recommenders 1.2.1/tag `51b1451…` recorded; MIT `backend/discovery/LICENSE` preserved. |
| P1.2 | [x] | PASS | `docs/vendored_modules.txt` lists the traced module set; Spark/TF/PyTorch/Cornac/Azure/notebooks excluded. |
| P1.3 | [x] | PASS | Only declared modules under `backend/discovery/{datasets,evaluation,models,utils}`; copyright headers preserved. |
| P1.4 | [x] | PASS | No production `import recommenders`/`from recommenders`; old name remains only in notices/docs/license. |
| P1.5 | [x] | PASS | Lazy/optional imports documented in NOTICE; runtime-purity tests assert no TF/PySpark/Torch/Cornac. |
| P1.6 | [x] | PASS | NOTICE/ATTRIBUTION complete; `tools/vendored_manifest.py --check` passes for 22 files; manifest regenerates deterministically. |
| P1.7 | [x] | PASS | SAR, split, metrics, TF-IDF, and loader smoke tests exist and pass in the full suite. |
| P1.8 | [x] | PASS | `pip show recommenders` fails; `find_spec("recommenders")` is `None`. |
| P1.9 | [x] | PASS | Phase 1 gate/R10 evidence recorded in Session Log. |

## Phase 2

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P2.1 | [x] | PASS | Strict Pydantic Interaction/Item/ScoredItem/Reason/ValidationReport/ContentTypeSpec; unit tests reject bad data. |
| P2.2 | [x] | PASS | YAML loading, validation errors, config hash, fast overrides; tests cover missing/wrong fields. |
| P2.3 | [x] | PASS | Abstract adapter/model bases and error hierarchy; mypy strict passes. |
| P2.4 | [x] | PASS | PopularityModel deterministic tie-break; RandomModel seeded via SHA-256; property tests. |
| P2.5 | [x] | PASS | Decorator registration; unknown names raise clear errors; toy type proves extensibility. |
| P2.6 | [x] | PASS | Chronological/leave-last-n/impression-time splits with R2 leakage checks; deliberate-leak test raises. |
| P2.7 | [x] | PASS | Ranking metrics plus hit-rate/coverage/novelty/diversity/personalisation; hand-computed fixtures. |
| P2.8 | [x] | PASS | Harness runs split/fit/evaluate/cold-start and writes canonical metrics.json; schema documented. |
| P2.9 | [x] | PASS | Reusable R1–R5 checkers used by harness and tests. |
| P2.10 | [x] | PASS | Manifest/checksums/schema version; dynamic delete, byte-flip, and version-tamper all raise ArtifactCorruptError. |
| P2.11 | [x] | PASS | `explain.py`/`coldstart.py` handle empty/duplicate/unknown/short histories; unit tests. |
| P2.12 | [x] | PASS | `python -m engine.train --type X [--fast] [--seed N]`; structured logging; toy adapter works. |
| P2.13 | [x] | PASS | Phase 2 gate entry in Session Log. |

## Phase 3

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P3.1 | [x] | PASS | DATASETS documents 100K/1M and license; fetch supports both; artifacts show 1M loaded. |
| P3.2 | [x] | PASS | MovieLens adapter handles schema/string IDs/title cleaning/year/genres/min-interactions; tests. |
| P3.3 | [x] | PASS | `data_report.json` includes counts/sparsity/filtering/timestamp range; R1 validation. |
| P3.4 | [x] | PASS | Chronological split + R2 leakage test on real MovieLens data. |
| P3.5 | [x] | PASS | SAR wrapper: fit/recommend_user/popular/similar_items/top-neighbour sparsification; R3 tests. |
| P3.6 | [x] | PASS | SAR cold-start affinity product; 50-user consistency test in integration. |
| P3.7 | [x] | PASS | Reason = argmax affinity×sim, share threshold; property tests assert history membership/max contributor. |
| P3.8 | [x] | **PARTIAL** | Tuning runs on validation and logs split_used, but threshold trials with a `positive` column are scored against fixed labels (`tuning.py:205-209`). F-006. |
| P3.9 | [x] | PASS | Final movies model trained/evaluated vs Random/Popularity; metrics include sanity/extra metrics; decisions recorded. |
| P3.10 | [x] | PASS | Cold-start curve 0–20 stored in metrics.json; non-monotonic points visible. |
| P3.11 | [x] | PASS | topn/users/items artifacts and ~8 diverse demo users with personas. |
| P3.12 | [x] | PASS | `test_movies_golden.py` compares fixed users/key metrics to stored golden values. |
| P3.13 | [x] | PASS | Phase 3 gate rituals (train-only popularity, no test similarity, history-only reasons, no seen items). |

## Phase 4

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P4.1 | [x] | PASS | Dataset decision (Amazon Video Games 5-core + metadata) and license notes recorded. |
| P4.2 | [x] | **PARTIAL** | Adapter implements join/fallbacks/cap, but the cap is computed before split using test interactions (F-002) and product rows omit `positive` (F-005). |
| P4.3 | [x] | PASS | Products data report and chronological leakage test pass. |
| P4.4 | [x] | PASS | Products config reuses SAR; 8,000-item cap and serving RSS documented. |
| P4.5 | [x] | PASS | Tuning/train/eval/cold-start/artifacts/demo users match the movies procedure. |
| P4.6 | [x] | PASS | Sparse-data, long-tail, category-diversity, similar-alternative checks recorded in metrics. |
| P4.7 | [x] | PASS | `tools/core_unchanged.py` and products gate enforce core-unchanged rule. |
| P4.8 | [x] | PASS | Phase 4 gate entry in Session Log. |

## Phase 5

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P5.1 | [!] | BLOCKED | Vendored MIND helpers verified; Microsoft blob access restricted; manual Hugging Face/Kaggle steps documented. Real files not present. |
| P5.2 | [x] | PASS | MIND parser handles news/behaviors, missing abstracts, unicode, empty histories; fixture tests. |
| P5.3 | [ ] | **FAIL** | Real-data R2 acceptance not met. Code backdates later history and globally dedupes (F-003); the only leakage test is `real_data` and CI-excluded (F-013). Plan marker remains unchecked. |
| P5.4 | [x] | PASS | TF-IDF vocabulary fit on train-period articles only; sparse matrix/vocab persisted; unit tests. |
| P5.5 | [x] | PASS | Candidate recency window enforced; window popularity baseline; tests assert no out-of-window items. |
| P5.6 | [x] | PASS | Native cold start via `recommend_history`; consistency test present. |
| P5.7 | [x] | PASS | Explanation = highest-cosine history article; property test. |
| P5.8 | [x] | **PARTIAL** | Both protocols reported, but impression fallback can include train (F-007), Random baseline is hash-nondeterministic (F-008), and leakage flag is hardcoded (F-015). |
| P5.9 | [x] | PASS | Cold-start curve, top-N, users stats, demo users present for articles. |
| P5.10 | [x] | PASS | Short/missing/non-English/duplicate/missing-catalogue tests present. |
| P5.11 | [x] | PASS | `tools/core_unchanged.py` run for articles. |
| P5.12 | [x] | **PARTIAL** | Phase 5 gate entry exists, but it was accepted on the synthetic fixture while P5.3 remains open; the gate cannot be considered fully met on real data. |

## Phase 6

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P6.1 | [x] | PASS | `tools/make_results.py` generates RESULTS/figures from metrics; `--check` reports up to date. |
| P6.2 | [x] | PASS | Toy fourth type registers/trains/serves without engine/api core edits; integration test. |
| P6.3 | [x] | **PARTIAL** | Determinism test exists and Session Log reports identical topn hashes, but it is `real_data` and CI-excluded; articles Random baseline is separately nondeterministic (F-008/F-013). |
| P6.4 | [x] | PASS | Clean-room script and manual ~451.51 s run recorded; test is opt-in/slow. |
| P6.5 | [x] | **PARTIAL** | Shared loader/R3 suite works, but products interactions omit the required `positive` field (F-005), so artifacts are not schema-identical. |
| P6.6 | [x] | PASS | Movies/products and both articles protocols include 500-resample 95% CIs; articles payload contains `*_ci95` fields. |
| P6.7 | [x] | PASS | DECISIONS contains limitation entries (popularity bias, cold items, domain shift, short histories, freshness, offline/online, licenses). |
| P6.8 | [x] | PASS | Phase 6 gate + shuffled-label test present. |

## Phase 7

| Task | Plan | Verdict | Evidence / notes |
|---|---|---|---|
| P7.1 | [x] | PASS | Lifespan loads all registry types; corrupt/missing type marked unavailable; env config; `OPENBLAS_NUM_THREADS=1` set before numpy. |
| P7.2 | [x] | PASS | Pydantic schemas; standardized error handlers for 400/401/403/404/409/422/503/500; no stack traces. |
| P7.3 | [x] | **PARTIAL** | All metadata endpoints exist and contract tests pass, but `/items/search` `total_matches` is capped by `limit` (F-014). |
| P7.4 | [x] | PASS | Profile endpoint returns counts/categories/recent 10/first-last/persona; pandas-equivalence tests. |
| P7.5 | [x] | PASS | Recommend supports topn/live, `exclude`, raw+display scores, reasons, meta; R3 asserted; dynamic exclude/prefix probes pass. |
| P7.6 | [x] | PASS | Cold-start max 200, duplicate 422, unknown ignored/listed, mode switch, signal bounds; dynamic probes pass. |
| P7.7 | [x] | PASS | Popular/similar endpoints; similar excludes query item; unknown item 404. |
| P7.8 | [x] | PASS | Optional constant-time byte key, env CORS, 1 MB body limit, 100-char search cap; non-ASCII key 200/401 tests. |
| P7.9 | [x] | PASS | `openapi.json` committed; export check passes. |
| P7.10 | [x] | PASS | Endpoint×type contract tests, R3 invariants, Hypothesis fuzzing. Schemathesis was not installed/run; that part was optional (“if it can be installed”). |
| P7.11 | [x] | PASS | `bench_api.py` (warm-up, 500 requests, p50/p95/p99/RSS); RESULTS generated; p95 < 150 ms, RSS < 2 GB. Not independently rerun. |
| P7.12 | [x] | PASS | Subprocess runtime-purity test asserts no TF/PySpark/Torch/Cornac. |
| P7.13 | [x] | PASS | Phase 7 gate tests: exclusion removal, k-prefix stability, concurrent identical results. Dynamic probes confirm exclude/prefix. |

## Notes
- A `[x]` in the plan is treated as the author’s claim, not proof. Verdicts above are based on code, tests, artifacts, and dynamic checks.
- Phases 8+ (frontend, deployment) are intentionally not audited and are not failures.
- The two FAILs and nine PARTIALs are the actionable compliance gap; the detailed defects are in `FINDINGS.json` and `REPORT.md`.
