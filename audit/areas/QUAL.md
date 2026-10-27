# AREA QUAL — General code quality

**Verdict:** PASS WITH FINDINGS — 1 MEDIUM, 1 LOW (plus the HIGH `eval` issue reported under SEC/ADAP).

## Files read
- All `backend/engine/` and `backend/api/` source files listed in the other area reports
- `audit/hardcoded_scan_raw.txt` and `audit/scratch/hardcode_scan.py`
- `backend/pyproject.toml` ruff/mypy configuration

## Findings
### F-020 — Runtime `assert` statements in library code (LOW)
`backend/engine/adapters/amazon.py:261,267`, `backend/engine/adapters/mind.py:392,398`, and `backend/engine/models/tfidf.py:444` use bare `assert` for state checks. Under `python -O`, these vanish and the code proceeds with `None` state, producing an `AttributeError` later instead of a clear error.

**Impact:** Low; production runs are not expected to use `-O`, but the checks are not robust invariants.

**Recommendation:** Raise explicit `RuntimeError`/`ArtifactError` instead of `assert` in non-test code.

### F-019 — Private `_entries` access in the API (LOW, also in API)
`backend/api/routes/metadata.py:291`. See AREA API.

## Hardcoded sweep summary
The raw scan is 1,190 lines across 14 categories:
- 78 absolute-path/URL-like strings — mostly documentation URLs, dataset URLs, and Windows path normalization; benign.
- 136 URL/host literals — expected dataset/citation endpoints.
- 2 ports — localhost demo defaults.
- 1 secret-like literal — a test value only (`test_api_security.py:102`); no production secret.
- 142 type-specific strings — mostly registry/docstring/API descriptions. A few real type branches exist (`artifacts.py:149-159`, `train.py:247`), which is acceptable for display metadata but worth reviewing.
- 658 magic numbers — mostly thresholds, test values, and metric constants. Hot spots: `train.py:247` (`max_test = 2000`), `api/search.py:55` (`+1000` default rank), `articles_eval.py:121` (`10000000` hash modulus, see F-008).
- 16 seed literals — expected; configs use `seed: 42`.
- 24 broad `except Exception` — mostly API/logging/optional-tool fallbacks. Two hide real problems: `config.py:175-176` (F-010) and `articles_eval.py:505-506` (F-009).
- 15 print calls — training CLI summary; acceptable.
- 1 TODO marker — test fixture only.
- 47 suppressions — mostly `type: ignore`/`noqa` with reasons; no blanket suppressions in production.
- 16 runtime asserts — see F-020.
- 12 unsafe-call hits — the real one is `amazon.py:51` `eval` (F-001); the rest are Makefile `find`/shell text.
- 14 naive-time calls — timing/logging only; no business logic depends on wall-clock time.

No hardcoded production credentials, API keys, or tokens were found.

## Positives verified
- `ruff check .` and `ruff format --check .` pass; `mypy engine/ api/` passes strict mode.
- The code is consistently typed, uses Pydantic models at boundaries, and keeps engine/API separation clean.
- Error messages are actionable; logging is structured.
- The test suite is broad (unit/contract/integration/property) and fast enough for local iteration (excluding the clean-room test).

## Uncovered / notes
- The hardcoded scan is regex-based; semantic constants inside configs/tests were not exhaustively reviewed.
- No complexity/lint metric (e.g. cyclomatic complexity) was run.
