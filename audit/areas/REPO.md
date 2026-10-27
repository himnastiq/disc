# AREA REPO — Repository, packaging, tooling, CI

**Verdict:** PASS WITH FINDINGS — 1 MEDIUM.

## Files read
- `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml`
- `Makefile`, `README.md`, `LICENSE`
- `backend/pyproject.toml`
- `.github/workflows/ci.yml`
- `tools/check.py`, `tools/progress.py`, `tools/vendored_manifest.py`
- `backend/tests/unit/test_progress.py`
- repository tree, `git log`, `git ls-files`, `git status`

## Findings
### F-012 — Dependency versions are not locked (MEDIUM)
- `backend/pyproject.toml:11` only sets `requires-python = ">=3.11"`.
- `backend/pyproject.toml:16` declares `dependencies = []`; `backend/pyproject.toml:19-46` uses lower bounds such as `numpy>=1.24`, `pandas>=2.0`, `fastapi>=0.109.0`.
- No `uv.lock`, `requirements.txt` pin, or `backend/*.lock` exists.
- `.gitignore:70-71` explicitly claims “uv.lock and package-lock.json ARE committed”, but neither file exists.
- P0.3 explicitly requires “Lock versions (uv lock or pinned requirements)”. This is unmet.

**Impact:** A fresh install today can resolve to different versions than the audited environment, so “retraining produces identical hashes” and CI greenness are not reproducible over time. The installed environment is also unusually new (`pandas 3.1.0`, `numpy 2.4.6`, `fastapi 0.162.0`, `starlette 1.9.0`), increasing the chance of future breakage.

**Recommendation:** Commit a lock file generated from the supported Python 3.11 environment and install with `--locked`/`-r` in CI.

## Positives verified
- `ruff check .` → all passed.
- `ruff format --check .` → 118 files already formatted.
- `mypy engine/ api/` → success, 45 source files.
- Full test suite → 439 passed, 1 skipped, 1 warning in 836.64 s.
- OpenAPI export check → committed `backend/api/openapi.json` is up to date.
- Vendored manifest check → passed, 22 files.
- `Makefile` targets required by P0.4 exist (`setup`, `data`, `train`, `train-fast`, `eval`, `api`, `web`, `test`, `lint`, `check`, `gates`, `progress`, `clean`, `demo`).
- `tools/check.py` provides a cross-platform equivalent to `make check`; CI runs the individual steps directly.
- `tools/progress.py` is covered by `backend/tests/unit/test_progress.py` and CI checks that regenerating the dashboard produces no diff.
- `.gitignore` excludes `data/`, `artifacts/`, `.venv/`, caches, and `.env*`; no raw datasets or artifacts are tracked.

## Uncovered / notes
- `make` is not installed in this Windows environment, so targets were validated by reading them and by running the underlying commands directly.
- I did not run `tools/progress.py` because it rewrites `IMPLEMENTATION_PLAN.md`; its idempotence is covered by the test suite and CI.
- CI does not run the `slow` clean-room test; see AREA TEST.
