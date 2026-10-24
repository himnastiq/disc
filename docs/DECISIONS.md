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

---

<!-- Add new entries above this line -->

