# Architecture Decision Records

> Each entry follows the format: Date, Context, Options considered, Decision, Consequences, Related tasks.

---

## D-001: Project license (2024-10-24)

**Context:** Need to choose a license for the project's original code.

**Options considered:** MIT, Apache 2.0, GPL

**Decision:** MIT — matches the vendored Recommenders license, simplest for an educational project.

**Consequences:** No copyleft obligations; derived code remains MIT.

**Related tasks:** P0.1

---

## D-002: Loosen pyproject.toml upper version bounds (2026-10-24)

**Context:** The previous session pinned tight upper bounds (e.g. `numpy>=1.24,<2.0`). On the current dev machine (Python 3.14.2, macOS ARM64), numpy 2.x is required — numpy 1.x does not build for Python 3.13+.

**Options considered:** (a) Pin Python to 3.11 only, (b) Loosen upper bounds while keeping minimum versions, (c) Remove all bounds.

**Decision:** (b) Keep `>=` minimum constraints from the plan, remove `<` upper bounds. This allows the latest compatible versions to install on any Python >=3.11.

**Consequences:** Dependencies float to latest compatible; CI on Python 3.11 may see different versions than dev. Minimum versions still enforced.

**Related tasks:** P0.3

---

## D-003: Portable Makefile (2026-10-24)

**Context:** The previous session wrote a Makefile with hardcoded Windows absolute paths (`e:\discover\.venv\Scripts\python.exe` etc.), which cannot work on macOS or Linux.

**Decision:** Rewrote all tool references to use `python3` / `pip` (overridable via `PYTHON ?=` / `PIP ?=`). Commands use `python -m <tool>` pattern to work in any activated venv on any OS.

**Consequences:** Users must activate the venv or set `PYTHON`/`PIP` variables. Works on macOS, Linux, and Windows (with appropriate shell).

**Related tasks:** P0.4

---

## D-004: Environment record (2026-10-24)

**Context:** P0.10 requires recording the verified environment.

**Record:**
- **OS:** macOS (ARM64, Apple Silicon)
- **Python:** 3.14.2
- **Key tool versions:** pytest 9.1.1, ruff 0.17.2, mypy 2.4.0, numpy 2.5.4, pandas 3.1.0, scipy 1.18.1, scikit-learn 1.9.1, fastapi 0.162.0, pydantic 2.14.1, hypothesis 6.170.9
- **`make check` result:** GREEN (lint + type check + 7 tests pass)

**Related tasks:** P0.10

## D-005: Windows environment verification (2026-10-24)

**Context:** The workspace is running on Windows 11 with Python 3.11.7. Verified fresh virtualenv setup and execution of tests and linters.

**Record:**
- **OS:** Windows 11 (x64)
- **Python:** 3.11.7
- **Key tool versions:** pytest 9.1.1, ruff 0.17.2, mypy 2.4.0, numpy 2.4.6, pandas 3.1.0, scipy 1.17.1, scikit-learn 1.9.1, fastapi 0.162.0, pydantic 2.14.1, hypothesis 6.170.9
- **Checks result:** GREEN (lint + type check + 7 tests pass)

**Related tasks:** P0.3, P0.10

## D-006: Recommenders source version and license (2026-10-24)

**Context:** P1.1 requires selecting a pinned release of `recommenders` from PyPI that supports Python 3.11, installing it in a throwaway virtualenv outside the repo, copying its LICENSE into `backend/discovery/LICENSE`, and recording the version.

**Decision:**
- **Package:** `recommenders`
- **PyPI version:** `1.2.1`
- **Release tag / commit:** Git tag `1.2.1` (`51b1451f28ffea99df38e833441ee45ca09ba3a9` at https://github.com/recommenders-team/recommenders)
- **License:** MIT (Copyright (c) 2018-present Microsoft Corporation, 2023-present Recommenders contributors) copied to `backend/discovery/LICENSE`.

**Consequences:** `1.2.1` is the base from which `backend/discovery/` will be trimmed and renamed in subsequent Phase 1 tasks.

**Related tasks:** P1.1, P1.6

## D-007: Recommenders API adjustments and NumPy 2 compatibility (2026-10-24)

**Context:** During P1.7 smoke testing of the vendored `discovery` package against actual source:
1. The plan named the chronological splitter `python_chronological_split`. The actual function name in `discovery.datasets.python_splitters` is `python_chrono_split`.
2. NumPy 2.x removed the expired attribute `np.NaN` in favor of `np.nan`. `SARSingleNode` in Recommenders 1.2.1 used `np.NaN` in item/user mapping lookups.

**Decision:**
1. Use `python_chrono_split` as the real splitter API name (per operating rule 6).
2. Patch `models/sar/sar_singlenode.py` to use `np.nan` instead of `np.NaN`.

**Consequences:** `discovery` works seamlessly across both NumPy 1.x and NumPy 2.x environments.

**Related tasks:** P1.5, P1.7, P2.6

---

## D-008: Fast config overrides and schema model_copy (2026-10-24)

**Context:** P2.2 requires applying fast developer overrides when `--fast` is specified. Mutating Pydantic v2 schemas in-place can inadvertently mutate cached or shared objects.

**Decision:**
Use `spec.model_copy(deep=True)` when applying overrides in `engine.config.apply_fast_overrides`, ensuring pristine original models and immutability.

**Consequences:** Clean separation between default and fast development configurations.

**Related tasks:** P2.2, P2.8, P2.12

## D-009: SAR cold-start weighting convention and consistency verification (2026-10-24)

**Context:** Task P3.6 requires cold-start scoring for SAR via `recommend_history`. When training with exponential time-decay (`timedecay_formula: true`), historical interactions are scaled down exponentially based on the time elapsed from the latest dataset interaction timestamp (`time_now`). In an online or cold-start setting (such as an onboarding questionnaire in the web UI), user-provided interaction history consists of selected items and preference signals without historical timestamps.

**Decision:**
1. For hypothetical cold-start histories without timestamps, a flat weighting convention is used (the explicit float signal or default 1.0) to construct the affinity row vector.
2. In `SarModel.recommend_history`, `max_history_length` defaults to `None` so that full histories supplied during evaluation or consistency audits are not truncated prematurely.
3. For consistency verification (R3):
   - Under flat weighting (`timedecay_formula: false`), `recommend_user` and `recommend_history` on raw training signals produce 100% bit-for-bit identical recommendations for 50 sampled known users.
   - Under time-decayed models (`timedecay_formula: true`), `recommend_history` supplied with the user's decayed training affinities produces 100% bit-for-bit identical recommendations for 50 sampled known users.

**Consequences:** Clear, mathematically grounded consistency guarantee between user-based and history-based recommendation pipelines.

**Related tasks:** P3.5, P3.6, R3

---

<!-- Add new entries above this line -->
