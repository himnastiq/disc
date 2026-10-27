# AREA TEST — Test suite quality and CI coverage

**Verdict:** PASS WITH FINDINGS — 1 MEDIUM.

## Files read
- `backend/tests/` tree (unit, contract, integration, property)
- `backend/tests/conftest.py`
- `backend/pyproject.toml` pytest markers
- `.github/workflows/ci.yml`
- `backend/tests/integration/test_articles_split_leakage.py`
- `backend/tests/integration/test_determinism.py`
- `backend/tests/integration/test_clean_room.py`
- `backend/tests/integration/test_phase7_gate.py`
- `backend/tests/contract/test_api_metadata.py`
- `backend/tests/unit/test_api_security.py`

## Findings
### F-013 — CI deselects 42 `real_data` tests, including the P5.3 and P6.3 acceptance tests (MEDIUM)
`.github/workflows/ci.yml:54` runs:

```bash
pytest tests/ -v --tb=short --maxfail=20 -ra -m "not real_data"
```

`backend/pyproject.toml:65` defines `real_data` as “tests that require full/real datasets or trained artifacts”. Collection shows 42/440 tests are deselected.

Both acceptance-critical files are wholly marked `real_data`:
- `backend/tests/integration/test_articles_split_leakage.py:13` — P5.3 R2 test.
- `backend/tests/integration/test_determinism.py:21` — P6.3 retrain/topn hash test.

**Impact:** The two tests that would catch the MIND leakage (F-003) and verify determinism are never run in CI. Local full-suite runs pass because the fixtures/artifacts are present, but a normal PR does not exercise them. P5.3 is still unchecked in the plan, so the acceptance gap is real rather than merely a CI configuration preference.

**Recommendation:** Keep the 42 heavy tests in a scheduled/nightly job or a separate `real-data` CI job, and require it before closing P5.3/P6.3. At minimum, run the leakage test on the committed synthetic fixture in the default job.

## Other test-quality notes
- The search contract test at `backend/tests/contract/test_api_metadata.py:216` only checks `total_matches >= len(results)`, allowing F-014.
- The full suite is otherwise strong: 439 passed, 1 skipped, 1 warning; property tests use Hypothesis; contract tests cover every endpoint/type; runtime-purity and phase-gate tests exist.
- The one skipped test is the ~7.5-minute clean-room rebuild (`test_clean_room.py:29`), gated by `RUN_CLEAN_ROOM`; P6.4 is therefore verified by the Session Log/manual run, not by default CI.
- The only warning is a Starlette/httpx deprecation (`StarletteDeprecationWarning`), not a failure.

## Uncovered / notes
- I did not run coverage (`pytest-cov` is installed but no coverage report/CI threshold exists).
- I did not run the clean-room rebuild or the full 42-test `real_data` set again; the full 439-test run was executed earlier in this audit.
