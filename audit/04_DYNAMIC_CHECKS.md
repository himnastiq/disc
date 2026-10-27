# Dynamic Checks — Commands, Results, Skips

**Environment:** Windows 10/11, Python 3.11.7 (MSC v.1937 64-bit), project `.venv`.
**Installed key versions:** numpy 2.4.6, pandas 3.1.0, scipy 1.17.1, scikit-learn 1.9.1, pyarrow 26.0.0, pydantic 2.14.1, PyYAML 6.0.3, fastapi 0.162.0, starlette 1.9.0, uvicorn 0.54.0, joblib 1.6.0, pytest 9.1.1, hypothesis 6.170.9, httpx 0.28.1, ruff 0.17.2, mypy 2.4.0, pip-audit 2.10.1, matplotlib 3.11.2. `recommenders` is **not installed**.

## 1. Static quality gates

| Check | Command | Result |
|---|---|---|
| Ruff lint | `ruff check .` (backend) | PASS — all checks passed |
| Ruff format | `ruff format --check .` (backend) | PASS — 118 files already formatted |
| Mypy | `mypy engine/ api/` (backend) | PASS — success, 45 source files |
| OpenAPI | `python backend/scripts/export_openapi.py --check` | PASS — committed schema up to date |
| Vendored manifest | `python tools/vendored_manifest.py --check` | PASS — 22 files |
| Secret scan | regex over repository | PASS — no credential patterns; one test literal |
| Results regeneration | `python tools/make_results.py --check` | PASS — `docs/RESULTS.md` up to date; figures regenerated identically |
| Full test suite | `pytest tests/` | **439 passed, 1 skipped, 1 warning in 836.64 s** |
| CI-equivalent suite | `pytest tests/ -m "not real_data"` | **397 passed, 1 skipped, 42 deselected** |

The single skip is the opt-in ~7.5-minute clean-room rebuild (`test_clean_room.py:29`). The warning is a Starlette/httpx deprecation, not a failure.

## 2. Artifact integrity

`audit/scratch/dynamic_checks.py` copied the mini movies artifact to a temp directory and ran `verify_artifacts`:

| Probe | Result |
|---|---|
| Untouched artifact | PASS |
| Delete `items.parquet` | `ArtifactCorruptError` |
| Flip one byte in `items.parquet` | `ArtifactCorruptError` |
| Change `artifact_schema_version` to `9.9.9` | `ArtifactCorruptError` |

## 3. API probes (mini artifacts, FastAPI TestClient)

| Probe | Result |
|---|---|
| `/v1/health`, `/v1/types`, `/v1/about` | 200 |
| `k=0`, `k=51` | 422 |
| `type=../movies` | 404 |
| Unknown user / unknown item | 404 |
| Empty / 101-char search query | 422 |
| Cold-start empty history | 200 |
| Cold-start 201 entries | 422 |
| Cold-start duplicate IDs | 422 |
| Cold-start unknown-only history | 200 |
| `exclude` returned item | Item removed |
| k=5 prefix vs k=10 | Stable |
| `/v1/metrics` vs artifact JSON | Byte-equivalent payload |
| Missing API key | 401 |
| Wrong API key | 401 |
| Valid non-ASCII key | 200 |

## 4. Contract bug reproduced: search total

Using the mini movies index:
- Query `q=a` has **59** matching items.
- `limit=1` → response `total_matches: 1`, returned 1.
- `limit=5` → `total_matches: 5`.
- `limit=20` → `total_matches: 20`.

This contradicts `SearchResponse.total_matches` (“Total number of matches”, `api/schemas.py:129`). Reported as F-014.

## 5. Cross-process determinism probe

The articles Random baseline uses Python’s built-in `hash()`. Running the same context in three fresh processes produced:

```
5076166
6895007
6011368
```

Reported as F-008. The project’s `RandomModel` uses SHA-256 and is deterministic; the evaluation path bypasses it.

## 6. Artifact sanity

| Type | Interactions | Items | Notes |
|---|---:|---:|---|
| movies | 999,611 | 3,883 | MovieLens 1M; `positive` present |
| products | 216,994 | 8,000 | Amazon Video Games; **no `positive` column** (F-005) |
| articles | 28 | 15 | Synthetic fixture, labelled “SYNTHETIC DEMO (not MIND)” |

Metrics/provenance keys inspected: `protocol`, `seeds`, `config_hash`, `git_sha`, `created_at`, `k_values`, `models`, `cold_start_curves`, `sanity_checks`; articles adds `protocols`, `is_synthetic`, `synthetic_fixture`, `synthetic_demo`, `label`, `provenance_banner`.

## 7. Documentation trace

More than 15 numbers in `docs/RESULTS.md` were spot-checked against artifacts/benchmark output (interaction counts, item counts, p95 latencies, RSS, headline metrics, cold-start values). They trace correctly. The separate CONFORMANCE R8 numbers do not (F-004).

## 8. Skips and reasons

| Check | Status | Reason |
|---|---|---|
| `pip-audit --local` | **SKIPPED/FAILED** | PyPI connection timed out; dependency vulnerability status unknown. |
| Full 500-request benchmark | **NOT RERUN** | Used committed `docs/RESULTS.md`; runtime would be long and the generated numbers are internally consistent. |
| Clean-room rebuild | **SKIPPED** | Test is opt-in and takes ~7.5 min; Session Log records a prior ~451.51 s run. |
| Schemathesis | **NOT RUN** | Not installed; plan says “if it can be installed”. Hypothesis fuzzing ran in the suite. |
| Upstream vendored diff | **NOT RUN** | No network/PyPI; provenance verified via project manifest/NOTICE. |
| Real MIND data | **UNAVAILABLE** | Microsoft download restricted; manual placement not present. P5.3 cannot be closed. |
| >1 MB body probe | **NOT RERUN** | Covered by `test_payload_too_large_via_content_length`; dynamic script did not send a large body. |
| Concurrent requests | **NOT RERUN** | Covered by `tests/integration/test_phase7_gate.py`. |
| Coverage report | **NOT RUN** | `pytest-cov` installed but no configured coverage gate. |

## 9. Safety
All dynamic work ran against copies/fixtures and read-only probes. No project file was modified by the dynamic checks. The final snapshot comparison is recorded in `REPORT.md`.
