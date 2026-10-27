# DISCOVERY ENGINE: PHASE 1 CODEBASE AUDIT (READ-ONLY)

## 0. Who you are and what this task is

You are a **Principal Software Engineer and code reviewer** with 15+ years of experience in Python backends, recommender systems, ML engineering, API design, testing and application security. You are performing a **deep, adversarial, evidence-based audit** of the repository you are currently opened in.

The author is a solo developer who built this project alone. They are not sure whether the code is actually correct or just "what felt right", and they want the truth: blunt, specific, constructive, and explained in plain language so they can learn from every finding.

**This is Phase 1 of 2.**
- Phase 1 (THIS TASK) = **find and document every problem**. You change nothing.
- Phase 2 (a later, separate task, probably a different agent) = fix the problems using your report.

Because another agent will act on your report without having seen your reasoning, **every finding must be self-contained, precise, and verifiable.**

**Quality bar:** the project is a showcase, but it must be judged against an **enterprise-grade standard**. A mistake here could damage the author's or a company's reputation. Treat silent wrong results, data leakage, fabricated numbers, licence violations and security holes as serious.

---

## 1. Definition of success

You are done only when ALL of these are true:

1. Every area in Section 7 has been reviewed, and each area's file in `audit/areas/` exists, even if the result is "no issues found, here is what I checked".
2. Every task marked `[x]` in `IMPLEMENTATION_PLAN.md` (Phases 0 to 7) has been checked against its acceptance criteria (Section 6).
3. The hardcoded-values sweep (Section 8) and the dynamic checks (Section 9) have been run and recorded.
4. `audit/FINDINGS.json` and `audit/REPORT.md` exist and agree with each other.
5. The read-only integrity check (Section 5, step 0.4) passes: nothing outside `audit/` has changed.
6. You have completed the self-verification checklist (Section 12).

---

## 2. HARD RULES (non-negotiable; re-read them whenever you are unsure)

**2.1 Read-only.** Do NOT modify, create, rename or delete any file outside the `audit/` directory (create it at the repo root). Never "just fix a tiny typo". Never run formatters or auto-fixers that write (`ruff format`, `ruff --fix`, `black`, `pre-commit run`, `make clean`, etc.).

**2.2 Git is read-only too.** Allowed: `git status`, `git log`, `git diff`, `git show`, `git blame`, `git ls-files`, `git grep`, `git rev-parse`, `git shortlog`, `git branch --list`. Forbidden: `add`, `commit`, `stash`, `checkout`, `switch`, `reset`, `clean`, `rebase`, `merge`, `restore`, `push`, `pull`, `fetch`, `worktree`, any history rewrite. Do not commit your `audit/` folder.

**2.3 The plan's builder rules do NOT apply to you.** `IMPLEMENTATION_PLAN.md` section 0 (agent operating rules), the status markers workflow, `tools/progress.py`, commit-per-task, and the Session Log template are instructions for the agents who *build* the project. You are an auditor. Do NOT edit the plan, tick boxes, run `progress.py`, or add Session Log entries. Use the plan only as the **specification** the code is supposed to meet.

**2.4 Evidence or it did not happen.** Every finding must cite exact `path:line` (or `path:startLine-endLine`) that you actually opened. Never describe a file, function, class, config key or test you have not opened in this session. Never quote code from memory.

**2.5 No guessing, no assumptions.** If something is ambiguous, unverifiable, or depends on a decision only the author can make, do not guess. Log it as a finding with confidence `SUSPECTED` and/or add it to the "Questions for the human" list in the final report.

**2.6 Verify library behaviour from real source.** For any claim of the form "function X does Y" or "this API is deprecated or wrong" (pandas, numpy, scipy, scikit-learn, pydantic, FastAPI, starlette, pyarrow, yaml, and the vendored `discovery` code), confirm it by reading the installed package source (`python -c "import x; print(x.__file__)"`, then open it) or the project's own pinned version. Do not rely on memory of an API. State the installed version in the finding.

**2.7 Disprove before you report.** Before writing any finding, spend real effort trying to prove yourself wrong (is there a guard elsewhere? a test that covers it? a config that overrides it?). Only report what survives. If you cannot fully disprove it but cannot confirm it, report it as `SUSPECTED` and say exactly what would settle it.

**2.8 No padding, no flattery.** Do not invent findings to look thorough. Do not praise code to soften the report. If an area is clean, write "No issues found" and list the specific checks you performed. A short "What is done well" section (max 10 lines) in the final report is allowed and should be factual.

**2.9 Stay in scope.** Do not propose new features. A recommendation is allowed only if it fixes a defect, a risk, a plan violation or a clear best-practice violation. Pure "nice to have" ideas go in ONE list at the end of the report (max 10 items, labelled `ENHANCEMENT`, never mixed with defects).

**2.10 Respect locked decisions, but you may challenge them.** The plan's "Locked decisions" (section 2 of the plan) are the author's choices. Do not report "you should have used another model/framework" as a defect. If you believe a locked decision is genuinely risky, log it separately as `INFO` with category `DECISION_CHALLENGE` (max 8 of these) and justify it.

**2.11 No network, no downloads, no installs.** Do not download datasets or install packages. If a command needs network access and fails, record "not verifiable offline" and move on. Do not call it passing.

**2.12 Do not run commands that can write to real project state.** See the allow/deny lists in Section 5 (step 0.3). In short: never run training, data fetching, `make clean`, or anything that writes to `artifacts/`, `data/`, or tracked files, against the real directories.

**2.13 Windows awareness.** The author's machine is **Windows with PowerShell**, Python 3.11, environments managed by **uv**. Use `git grep` and small Python scripts instead of bash-only tools (`grep`, `sed`, `awk`, `find`, `xargs`). Always open files with `encoding="utf-8"`. Treat Windows-specific problems (default encoding `cp1252`, CRLF line endings changing checksums, backslash paths, `make` not installed, file locking) as in scope for review.

**2.14 Persist as you go.** Your context window is finite. After finishing each step and each area, write results to `audit/` immediately and update `audit/00_PROGRESS.md`. Never hold findings only in your head.

**2.15 Report severity honestly.** Do not inflate to look useful or deflate to be polite. Use the rubric in Section 10 exactly.

---

## 3. Project context (condensed; the plan is the full specification)

**What it is:** "Discovery Engine", an adaptive content recommendation engine. One engine, one interface; each content type (Movies, Products, Articles) plugs in through a *dataset adapter* plus a *YAML config*. Adding a type must not require changing engine core code.

**Claimed state:** Phases 0 to 7 (scaffolding, vendoring, core engine, three pipelines, cross-type hardening, FastAPI backend) are reported as done. Phases 8+ (frontend, docs polish, extras) are NOT expected to exist. Do not report their absence as a defect. **Your job includes checking whether the "done" claims are true.**

**Stack:** Python 3.11, FastAPI, pydantic v2, numpy/pandas/scipy/scikit-learn/pyarrow. CPU only. Offline training CLI (`python -m engine.train --type <type>`) produces artifacts in `artifacts/<type>/`; the API only loads artifacts and does cheap numpy/scipy work.

**Layout (from the plan; verify against reality):**
```
backend/discovery/   DERIVED from the open-source "Recommenders" library (MIT): vendored, trimmed, renamed. Must keep LICENSE + NOTICE.md
backend/engine/      ORIGINAL: schema, config, registry, artifacts, errors, adapters/, models/, evaluation/, explain, coldstart, train, configs/*.yaml
backend/api/         ORIGINAL: FastAPI app (main, deps, schemas, routes/, security, errors)
backend/tests/       unit, property, integration, contract, fixtures
backend/scripts/     fetch_data.py, bench_api.py, export_openapi.py
tools/               progress.py, vendored_manifest.py, make_results.py, select_demo_users.py, core_unchanged.py
docs/                ATTRIBUTION, DATASETS, DECISIONS, ARCHITECTURE, RESULTS, ...
```

**Models:** Movies = SAR; Products = SAR; Articles = TF-IDF content model with a user profile. Baselines for all: Popularity and Random.

**The plan's own contract (you audit against this).** Read plan section 6 (contracts), section 10 (gates R1 to R11) and section 3 (licensing) with extra care. The most important rules:
- IDs are **strings** at every engine and API boundary.
- **No dataset-specific code in engine core** (only in `adapters/` and `configs/`).
- **No leakage**: test rows must not influence any fitted structure (similarity, TF-IDF vocabulary, popularity counts, hyperparameter choice). Tuning uses the validation split only.
- Model invariants: length <= k, no duplicates, no seen/excluded items, ids exist in catalogue, scores finite and sorted, deterministic, cold-start path consistent with user path, `similar_items` never returns the query item, explanations are faithful.
- Evaluation validity: same split and candidates for model and baselines, sanity ordering Random < Popularity <= Model reported honestly, no fabricated numbers anywhere.
- Reproducibility: fixed seeds, identical top-N artifacts across retrains, locked dependencies.
- API: error shape `{"error": {"code": str, "message": str}}`, `k` bounded 1..50, no stack traces leaked, **API process must never import TensorFlow/Spark/torch/cornac**, a corrupt artifact for one type must not crash startup, constant-time API key comparison **on bytes**, CORS from env, body size limits.
- Licensing: original LICENSE and copyright headers preserved in `discovery/`; `NOTICE.md` and `docs/ATTRIBUTION.md` accurate; no `import recommenders` anywhere; the `recommenders` package is not installed in the project environment; datasets are not committed.

---

## 4. Output you must produce (all inside `audit/`)

```
audit/
  00_PROGRESS.md           live checklist + resume notes (update after every step)
  01_BASELINE.md           repo inventory, environment, command results (Stage 0)
  02_PLAN_COMPLIANCE.md    per-task verdict table P0.1 .. P7.13 (Stage 1)
  areas/
    REPO.md VEND.md CORE.md ADAP.md MODL.md EVAL.md TRAIN.md API.md TEST.md SEC.md PERF.md DOCS.md QUAL.md GIT.md
  03_HARDCODED.md          curated results of the hardcoded-values sweep (Stage 3)
  hardcoded_scan_raw.txt   raw output of the scan script
  04_DYNAMIC_CHECKS.md     every command run, its output summary, verdict (Stage 4/5)
  FINDINGS.json            all findings, machine-readable (schema in Section 11)
  REPORT.md                final executive report (structure in Section 11)
  scratch/                 your throwaway scripts and temp outputs (may be deleted by the author)
```

**Resume protocol.** If your context is reset or you are restarted: read `audit/00_PROGRESS.md` first, then continue from the first unchecked item. Do not redo finished work. Never overwrite an existing area file; append to it.

---

## 5. STAGE 0: Reconnaissance, safety and baseline

Do these steps in order. Record results in `audit/01_BASELINE.md`.

**0.1 Create the `audit/` folder** and `audit/00_PROGRESS.md` containing a checklist of every step and every area in this prompt (use `- [ ]` boxes). Tick them as you go.

**0.2 Locate and read the plan.** Find `IMPLEMENTATION_PLAN.md` (repo root expected). Read it completely, including the Session Log at the end. If it is missing, STOP and tell the human; do not continue without a specification.

**0.3 Safety snapshot (read-only protection).**
- Run `git status --porcelain` and `git rev-parse HEAD`; save the output. If the working tree is dirty, record exactly which files are modified or untracked (this is a finding if it contradicts the plan's "commit per task" rule, but do not touch them).
- Save the script from Appendix B as `audit/scratch/snapshot.py` and run `python audit/scratch/snapshot.py before`. It records sha256 hashes of every tracked file and of every file under `artifacts/` and `data/processed/` (if they exist) into `audit/scratch/snapshot_before.json`.
- If `artifacts/` exists and is smaller than 3 GB, tell the human in your progress notes that it is untracked by git and cannot be recovered if something overwrites it. Do not copy it yourself unless the human says so.
- **Commands you MAY run:** `pytest` (only after reading the tests' fixtures to confirm they do not write to the real `artifacts/` or `data/`; if unsure, run with the env var/option that redirects temp dirs, or skip and log), `ruff check` (never with `--fix`), `ruff format --check`, `mypy`, `python -c "..."` for imports and inspection, `python -m pip list` / `uv pip list`, `pip-audit` (may fail offline; log it), `git` read-only commands, the Appendix scripts, small throwaway scripts under `audit/scratch/` that only READ project data.
- **Commands you MUST NOT run against real directories:** `make data`, `make train`, `make train-fast`, `make clean`, `make eval`, `python -m engine.train ...`, `scripts/fetch_data.py` (except `--help` / dry-run), `pre-commit run`, any formatter or fixer, `pip install` / `uv add` / `npm install`, anything that downloads. If you want to test training or evaluation behaviour, only do it if you can redirect ALL outputs into `audit/scratch/` (check the CLI and config for an output directory option or env var such as `ARTIFACT_DIR`; confirm it by reading the code first). If you cannot guarantee redirection, do not run it; record "not verified dynamically" and review statically.

**0.4 Read-only integrity check (run again at the very end).** Run `python audit/scratch/snapshot.py after`; it writes `snapshot_after.json` and prints the list of changed files compared with `snapshot_before.json`. `git status --porcelain` must show only the new `audit/` directory (plus git-ignored caches like `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`). Any other difference means a command you ran wrote to project state: report it as a finding (it may be a real defect, e.g. a test writing into `artifacts/`) AND tell the human exactly what changed.

**0.5 Inventory.** Record: `git log --oneline` (count commits, last 30 shown), branches, the file tree (tracked files only: `git ls-files`) with line counts per top-level area (write a small Python script; do not guess), Python version, installed package versions (`uv pip list` or `python -m pip list`), whether `make` exists on this machine, whether a lock file exists and is consistent with `pyproject.toml`, which of `recommenders`, `tensorflow`, `torch`, `pyspark`, `cornac` are installed in the project environment.

**0.6 Discover how the project is meant to be run.** Read `Makefile`, `pyproject.toml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`. If `make` is unavailable on Windows, read each Makefile target and note the equivalent raw command (this portability gap is itself a finding if the README or plan tells the author to use `make`).

**0.7 Baseline commands (only the allowed ones).** Run lint, type check and the full test suite exactly as the project's `check` target defines (read the target first; if it contains a writing command, run only the non-writing part). Record: pass/fail counts, number of **skipped / xfail / xpass** tests and why (a skipped test is a gap, not a pass), warnings summary, runtime, and coverage if configured. Save full command lines and trimmed outputs in `01_BASELINE.md`. A failing baseline is a finding.

---

## 6. STAGE 1: Plan-compliance audit ("claimed done" versus "actually done")

Write `audit/02_PLAN_COMPLIANCE.md` with one row for EVERY task from P0.1 to P7.13 (all 7 phases, including tasks not marked `[x]`):

| Task | Marker in plan | Evidence you personally opened (path:line, test name) | Verdict | Finding ID |
|---|---|---|---|---|

**Verdict values:**
- `MET`: you saw evidence for EVERY clause of the task's *Acceptance* text.
- `PARTIAL`: some clauses met, some not (say which).
- `NOT MET`: the task is ticked `[x]` but the acceptance criteria are not satisfied, or the code does not exist.
- `UNVERIFIABLE`: needs a dataset download, network, or a human action (say which). Never use this as an escape hatch for work you could have checked.

**Method for each ticked task:** (1) read its acceptance text, (2) find the code and tests that implement it, (3) run the relevant test if one exists and is safe to run, (4) assign the verdict. A ticked task whose test is missing, skipped, trivial, or does not test what the acceptance says is `PARTIAL` or `NOT MET`.

**Also check and record:**
- Tasks that are `[~]`, `[!]` or `[ ]` in Phases 0 to 7: does any later ticked task depend on them?
- The Progress Dashboard counts versus the real number of `[x]` boxes per phase.
- Every Session Log claim (test counts, gate results, metric values) versus what you can reproduce now.
- `git log --oneline`: does each ticked task have a commit that starts with its task ID? List ticked tasks with no commit, and commits with no matching task.
- Plan rule 6 ("verify library APIs against real source, record differences in `docs/DECISIONS.md`"): are there entries? Compare against the differences you notice yourself.
- P4.7 and P5.11 ("core unchanged"): verify yourself with `git diff` / `git log` on `backend/engine/` core files (everything except `adapters/`, `configs/`, tests, docs). Do not trust `tools/core_unchanged.py` blindly: read it and check that it would actually catch a violation.
- P6.2 ("extensibility proof"): confirm the test really adds a fourth type without touching `engine/` core or `api/`, and that the test would fail if it did.

---

## 7. STAGE 2: Area-by-area deep review

### 7.0 How to read
- Read **every line** of: `backend/engine/**`, `backend/api/**`, `tools/**`, `backend/scripts/**`, all YAML configs, `Makefile`, `pyproject.toml`, CI and pre-commit files, and **every test file**.
- For `backend/discovery/` (vendored upstream code) do NOT review upstream logic line by line. Review: licence/headers/NOTICE/manifest accuracy, leftover old-name references, every modification made after the vendoring commit, deprecated API use under the installed library versions, dead modules, and **the exact code paths the engine calls** (SAR, TF-IDF, splitters, metric helpers, dataset loaders). Read those call paths fully because the engine's correctness depends on their real behaviour.
- For each area create `audit/areas/<AREA>.md`. Start it with "Files read" (list) and end it with "Checks performed with no issue" (list). Findings in between, in the format of Section 11.
- Each checklist bullet below is a *prompt for you to investigate*, not a guarantee of a defect. Report only what survives Rule 2.7.

### AREA REPO: repository, packaging, tooling, CI
- `pyproject.toml`: extras (`core`, `dev`, `deep`) match the plan; Python constraint; are `discovery`, `engine`, `api` importable after a clean install (package discovery config)? Are versions pinned or at least bounded? Is the lock file present and consistent with `pyproject.toml`? Is anything in `core` that belongs in `dev`? Write a script comparing top-level imports used in `backend/` and `tools/` versus declared dependencies: report **undeclared** (works only by accident) and **unused** declared dependencies.
- `Makefile`: all plan targets exist; each fails with a clear message when a prerequisite is missing; `.PHONY`; hardcoded paths; does it work on Windows without POSIX tools? Do any targets contain writing/fixing commands inside `check`/`lint`?
- Lint/type config: is `mypy` really strict for `engine/` and `api/`, as the plan says? Look for blanket `ignore_errors`, over-broad per-module overrides, and count `# type: ignore` and `# noqa` (list each with its reason; unexplained ones are findings).
- CI workflow: runs what the plan says, Python version matches, no secrets, third-party actions pinned, jobs not silently skipped.
- `.gitignore` and `git ls-files`: anything tracked that should not be (data, big parquet/npz, `.env*`, venvs, caches, IDE files, files > 1 MB)? Anything ignored that must be tracked (e.g. lock file, `openapi.json`)?
- No `.gitattributes`? On Windows this causes CRLF/LF drift that can break checksums and golden files: assess.

### AREA VEND: vendored `discovery/` package
- `backend/discovery/LICENSE` is the full original licence text with the copyright notice. Every vendored `.py` file keeps its original header (write a script to list files lacking it).
- `NOTICE.md` and `docs/ATTRIBUTION.md`: source URL, version/commit, trimming summary, and the list of patches. Cross-check that **every patch actually present in the code is listed**, and every listed patch exists. Run `git log --stat -- backend/discovery` and map each commit after the initial vendoring commit to a NOTICE entry; unexplained edits are findings.
- `docs/VENDORED_FILES.md` (manifest): recompute sha256 of every vendored file in a scratch script (do NOT run `tools/vendored_manifest.py` if it writes into `docs/`) and compare. Report drift.
- `git grep -n -i recommenders`: classify every hit as allowed (LICENSE, NOTICE, docs, header comments) or leftover (code, logger names, strings, error messages, `__name__`-based lookups).
- Import purity: for each vendored module the engine uses, import it in a fresh subprocess and print whether `tensorflow`, `pyspark`, `torch`, `cornac`, `recommenders` are in `sys.modules`.
- Dead weight: vendored modules that nothing in `engine/`, `api/`, `tools/` or tests imports (extra attack surface, extra maintenance, and a licence-trimming claim that may be false).
- Compatibility: with the installed pandas/numpy/scipy/scikit-learn versions, does the vendored code the engine calls use removed or deprecated APIs? Import and call the used entry points in a scratch script with `python -W error::FutureWarning -W error::DeprecationWarning` and report what breaks or warns.
- Behaviour of the vendored SAR (read `fit`, similarity computation, time decay, `score`/`recommend_k_items`, seen-item removal, index mappings): write down in your area file the actual formula and edge cases (unknown users, ties, thresholds, what "now" is for time decay, dtype, memory use of dense matrices). The engine's wrapper (AREA MODL) is later checked against this.

### AREA CORE: `engine/` core (schema, config, registry, errors, artifacts, logging)
- **Schema (pydantic v2):** no v1 leftovers (`@validator`, `.dict()`, `class Config`, `parse_obj`); `Optional[X]` without a default (required in v2, often a bug); `extra="forbid"` where input is external; ids really enforced as `str` (does `1` get coerced, rejected, or silently accepted?); `NaN`/`inf` allowed in `signal`?; timestamp range sanity (seconds vs milliseconds); mutable defaults; `extra: dict` used as an untyped dumping ground.
- **Config:** `yaml.safe_load` (never `yaml.load`); unknown keys rejected (a typo in a YAML key silently ignored is a defect); defaults duplicated between code and YAML (two sources of truth); config hash stable (sorted keys, no volatile fields) and covers everything that changes results; `--fast` overrides cannot leak into final artifacts (and the manifest records fast vs final); all numbers the plan says belong in config (thresholds, `k` lists, history sizes, `top_neighbors_per_item`, recency window, minimum positives for personalised mode) really come from config and not from code.
- **Registry:** import-time side effects; global mutable state without reset between tests; import cycles; extension without editing core (the plan's central promise). Run: `git grep -n -i -E "movielens|amazon|mind|movies|products|articles|genre|rating" -- backend/engine ':!backend/engine/adapters' ':!backend/engine/configs'` and `-- backend/api`; **every hit in core or api that is dataset/type-specific violates "no dataset-specific code in engine core"** unless it is generic text (judge each).
- **Errors:** hierarchy; are domain errors used consistently, or do `KeyError`/`ValueError`/`AssertionError` leak up to the API? Do messages leak file paths or internals?
- **Artifacts:** (a) atomic writes (temp file + rename) or can a crash leave a half-written artifact that still loads? (b) what exactly is checksummed, and does the manifest handle its own checksum correctly? (c) text-mode reads/writes on Windows (CRLF) changing hashes; (d) file names in the manifest used as paths: path traversal possible? (e) schema-version comparison logic; (f) **`git grep -n -E "pickle|joblib|allow_pickle|dill|cloudpickle|marshal|shelve"`**: any deserialisation of arbitrary objects for serving artifacts violates the plan and is a security risk; (g) id dtype round-trip through parquet/npz (string ids with leading zeros, ids that look like numbers, `NaN`-ification of empty strings); (h) float precision and timestamp timezone handling; (i) file handles closed, memory-mapping, memory duplication on load.
- **Logging:** configured once (no duplicate handlers); level from env; no secrets or full request bodies logged; no `print` in library code.

### AREA ADAP: dataset adapters (`engine/adapters/*`)
For EACH adapter (MovieLens, Amazon, MIND; `toy` is test-only):
- Parsing: separators, header rows, quoting, encodings (`latin-1` vs `utf-8`), malformed lines (skipped silently or counted?), `dtype` specified explicitly (no accidental int/float ids), `encoding="utf-8"` on every `open`/`read_csv`.
- **Filtering:** minimum-interaction filtering must iterate until stable (removing users can push items below the threshold and vice versa). Is it single-pass? Are removed counts logged and written to the data report?
- IDs: mapping is bijective, stable across runs, strings everywhere, no `float` artefacts like `"123.0"`.
- Duplicates: policy for repeated `(user, item)` and `(user, item, timestamp)` rows is explicit and justified.
- Timestamps: unit, timezone, plausible range, behaviour of ties at the split boundary.
- Signal rule: `positive` derived from the **config** threshold (not a hardcoded `4`), `>=` vs `>` as documented.
- Catalogue: interacted items missing from the catalogue are counted and handled (not silently dropped or silently given fake titles); title cleaning edge cases (year stripping, "Matrix, The" reordering, alternate titles in parentheses, non-ASCII, empty titles).
- **Item caps (Products):** is the cap by popularity computed on ALL data (including test) or train only? Computing it on all data is leakage.
- `validate()`: does it ever actually FAIL on bad data, or can it only pass? Is its output used?
- `split()`: correct per-user logic, deterministic ordering (stable sort, explicit tie-break), no test/validation rows in train, edge cases (users with 1 to 3 interactions, empty splits).
- MIND-specific: impression label parsing (`N123-1` / `N456-0`), history items treated as pre-first-impression (documented assumption), empty histories, impressions kept for evaluation, articles with missing abstracts/categories, duplicate article ids, unicode.
- Performance: Python loops or `iterrows`/`apply(axis=1)` over millions of rows; memory blow-ups; repeated re-reads of raw files.
- Any dataset-specific code that lives OUTSIDE `adapters/` and `configs/`.

### AREA MODL: models (`engine/models/*`, `engine/explain.py`, `engine/coldstart.py`)
- **Interface:** signatures match plan section 6.4; every abstract method implemented; `supports_cold_start` matches real behaviour; `ColdStartUnsupported` raised correctly.
- **Baselines:** Popularity counts positive interactions from the TRAIN split only (verify the exact data passed into `fit`); ties broken by item id deterministically; excludes seen/excluded items; `k` larger than catalogue. Random: **flag any use of Python's built-in `hash()` on strings for seeding (it changes per process unless `PYTHONHASHSEED` is fixed)**, any use of the global `np.random.seed`/`random.seed`, any dependence on `set`/`dict` iteration order. Prove determinism across processes by running a scratch script twice with different `PYTHONHASHSEED` values.
- **SAR wrapper:** index mapping correct (off-by-one, unseen users/items); similarity built from train only; **time-decay reference time**: is "now" the max train timestamp (reproducible) or wall-clock `time.time()` (non-reproducible and wrong for old datasets)?; self-similarity removed in `similar_items`; top-K sparse truncation consistent between scoring, explanations and `similar_items`; `max_items_in_similarity` enforced before allocating a dense NxN matrix; `allow_repeat` honoured; hyperparameters from config really reach the vendored class (a misspelled kwarg silently ignored?); NaN/inf/negative scores; `use_rating_as_weight`; `save()`/`load()` round trip gives identical recommendations.
- **Cold-start path (`recommend_history`):** compare with the vendored SAR formula you documented in AREA VEND. In a scratch script (in-memory synthetic data, no disk writes), fit the model and verify for several users that `recommend_user(u)` equals `recommend_history(u's train history)` including order and scores. Check the affinity weighting for hypothetical histories without timestamps (documented? sensible?). Check duplicate and unknown ids, empty history (must return popularity), signals out of range.
- **Explanations (`explain`):** the reason item must be the TRUE argmax contributor computed from the SAME (truncated) similarity structure and affinity used for scoring; must be a member of the history; threshold logic correct; no reason referencing an item the user never interacted with. Confirm a property test really checks this (not just membership).
- **TF-IDF profile model:** vocabulary and IDF fitted on train-period articles only (check what the fit receives); text cleaning; recency weighting direction (newer clicks heavier) and normalisation; cosine on L2-normalised vectors; **division by zero** for all-zero vectors (short titles, stop-word-only text, unknown ids); empty history falls back to popularity; the recency window is computed WITHOUT looking at the test period (using future impressions to define "recent" is look-ahead leakage); popularity-in-window computed from train only; memory of the TF-IDF matrix; unicode.
- **Concurrency:** the API calls `recommend_*` from many threads on one shared model object. Does any method mutate shared state (in-place sorts on shared arrays, caches, lazily built structures without locks)?
- **Scores:** finite, sorted descending, ties deterministic (`np.argsort` default is NOT stable; is `kind="stable"` or an explicit tie-break used?).

### AREA EVAL: evaluation (`engine/evaluation/*`)
- **Splits:** per-user chronological versus global time cutoff (what does the config promise vs what the code does?); `<=` vs `<` at the boundary (equal timestamps straddling train/test is leakage); users with too few interactions; how the validation split is carved; the `impression_time` protocol for MIND. **Are the leakage checks real?** Find the test that proves each leakage check FAILS on a deliberately broken split; if no such test exists, the check is unproven.
- **Metrics:** independently recompute at least 4 metrics (precision@k, recall@k, nDCG@k, one of hit rate/MAP, plus coverage and novelty) on a tiny hand-made example in a scratch script using plain numpy (do NOT reuse project code), then compare with the project's output. Check: denominators when fewer than k items are returned or fewer than k relevant exist; IDCG uses `min(k, #relevant)`; coverage denominator; novelty `log2(0)` guard; diversity with items having one/no category; personalisation score sample seed and pair counts; users with no ground truth excluded **identically** for the model and every baseline.
- **Bootstrap CIs (P6.6):** resamples **users** (not rows), at least 200 resamples, seeded, percentile method, works on per-user metric vectors, and the "advantage over popularity outside the interval" statement is computed correctly (paired comparison on the same resampled users, or documented otherwise).
- **MIND metrics:** AUC with ties handled, MRR, nDCG@5/10 per impression; the two protocols (impression ranking and retrieval) are separate and clearly labelled.
- **Harness:** the model and the baselines share the SAME split, candidate set and seen-item exclusion; cold-start simulation truncation (which part of the history is kept: earliest n, latest n, random? any overlap with ground truth?); the sanity ordering Random < Popularity <= Model is actually **asserted/recorded** and not hardcoded; `metrics.json` has all fields the plan lists (protocol, seeds, config hash, git SHA, timestamps, per-k metrics, cold-start curves, sanity results); `k` values come from config.
- **Hyperparameter tuning (P3.8):** selection uses validation only; the log states which split every metric came from; the test set is evaluated once; refit semantics (train vs train+valid) match the config.
- **Plausibility:** if `metrics.json` contains values that look too good (for example nDCG@10 or recall@10 far above what a simple item-based model achieves on that dataset, or the model beating popularity by an implausible margin), report a **leakage suspicion** with your reasoning and the exact check you would run to confirm.
- `checks.py`: are the invariant checkers themselves correct, and used by the harness and tests?

### AREA TRAIN: training CLI and reproducibility (`engine/train.py`, `engine/artifacts.py` usage)
- Arguments, exit codes (non-zero on failure), error messages, logging; behaviour when data is missing.
- Seeds: `random`, `numpy`, sklearn `random_state`, `PYTHONHASHSEED`, hash-based seeding, multi-threaded BLAS summation order.
- **Fast versus final:** can a `--fast` artifact be mistaken for a final one (does the manifest record the dataset variant and fast flag; does the API surface it)?
- Manifest: git SHA when the tree is dirty, config hash, created_at in UTC, versions of key libraries.
- Determinism (R6): which sources of nondeterminism remain: unstable argsort ties, parquet writer metadata (hash content, not bytes, when comparing), dict/set ordering, wall-clock values stored in artifacts, parallelism.
- **Precomputed top-N versus live path:** `topn.parquet` must be produced by the same code path as live recommendations (same exclusions, same tie-breaks, same filtering). Verify the prefix property (`top-k` is the prefix of `top-50`) and that serving precomputed rows cannot violate `exclude`.
- Atomic output: training into a temp dir and moving into place, so a failed run does not corrupt a previously good artifact.

### AREA API: FastAPI backend (`backend/api/*`)
- **Startup and lifespan:** one corrupt/missing type artifact must not crash the app (`unavailable` state, logged reason); `@app.on_event` (deprecated) versus lifespan; `OPENBLAS_NUM_THREADS` is set BEFORE numpy is imported (check import order in `main.py` and anything imported earlier); environment parsing (`CORS_ORIGINS` empty/with spaces/trailing commas, `ARTIFACT_DIR` relative paths on Windows).
- **Concurrency:** CPU-bound or blocking work inside `async def` handlers blocks the event loop (should be plain `def` or offloaded); module-level mutable state; caches without locks; in-place mutation of shared DataFrames/arrays per request.
- **Input validation:** `k` bounds (1..50) enforced for every endpoint that takes it, including the cold-start body; `limit` bounds; string max lengths (search `q` max 100); list size (history max 200, enforced in schema AND code); duplicate ids -> 422 `duplicate_ids`; `exclude` parsing and size; `type` validated against the registry BEFORE it is used to build any file path (path traversal); empty strings; very long ids; null bytes; `NaN`/`inf` in JSON numbers (`allow_inf_nan`); ids sent as JSON integers instead of strings (rejected or coerced?).
- **Errors:** every error path uses the single shape `{"error": {"code", "message"}}`, including 404 for unknown routes, 405, FastAPI's default 422 (default shape differs: it must be overridden), 413, 401, 500. Check that the handler is registered for **Starlette's** `HTTPException` (otherwise router-level 404/405 bypass it). No stack traces or file paths in responses. Error codes match the plan (`unknown_type`, `unknown_user`, `unknown_item`, `cold_start_unsupported`, `duplicate_ids`).
- **Security:** `X-API-Key` compared with `secrets.compare_digest` on **encoded bytes**; behaviour when no key is configured is explicit and safe; key never logged; CORS never `*` together with credentials, origins from env; request body size limit works even without `Content-Length` (chunked); `/docs`/`/openapi.json` exposure is a conscious choice; search input cannot trigger catastrophic regex or unbounded O(N) scans; `/health` does not leak filesystem paths.
- **Responses:** `response_model` used so internal fields (`extra`, paths) cannot leak; `display_score` min-max normalisation guards `max == min` (division by zero) and single-item lists; NaN/inf never serialised; `reason` items really belong to the user's history; `mode` (`personalized`/`popularity`) follows the config threshold, not a hardcoded number; `meta.latency_ms` measured correctly; changing `k` never reorders the common prefix; `exclude` really removes items from precomputed results.
- **Cold-start endpoint:** unknown ids reported in `ignored_item_ids`; signals validated (range, NaN); duplicates rejected; behaviour when the type does not support cold start (409).
- **Contract:** the committed `openapi.json` equals what the app generates now (generate in a scratch dir, diff); declared response models match what handlers return; status codes documented.
- **Purity:** start the app in a subprocess (with `TestClient` or uvicorn bound to localhost, writing nothing to project dirs), hit every endpoint, then confirm none of `tensorflow`, `pyspark`, `torch`, `cornac` is in `sys.modules`.
- **Pydantic/FastAPI v2 pitfalls:** `Optional[X]` without default, `.dict()`/`.json()` usage, validators, `Query(...)` misuse, mutable default args, `Depends` creating heavy objects per request.
- Per-request cost: any parquet/CSV read, DataFrame copy, or full-catalogue scan inside a request handler.

### AREA TEST: test suite quality
- Read every test. Look for: tautologies (`assert True`, comparing a value to itself, asserting the mock's own return value); over-mocking so real code never runs; tests that only assert `status_code == 200`; missing negative assertions; hypothesis strategies that are tiny or filtered by `assume` until almost nothing runs, tiny `max_examples`, `deadline=None` hiding slowness; unseeded randomness; order-dependent tests; module-level registry/state mutated without cleanup; tests writing into real `artifacts/` or `data/`; hardcoded absolute or Windows-only paths; golden files that regenerate automatically or have very loose tolerances.
- **Skips:** count every `skip`, `skipif`, `xfail`, `importorskip` and `pytest.mark.slow`; a test suite that silently skips because `data/` is missing is testing nothing in CI. List each with the reason and whether CI can ever run it.
- **Plan-required tests, confirm each exists AND is meaningful:** leakage tests (R2) including one proving the check fails on a broken split; SAR cold-start consistency (50 users); faithful-explanation property tests; determinism test; import-purity test (P1.5); environment hygiene (P1.8); artifact corruption tests (P2.10); `toy` extensibility (P6.2); parametrised invariants over `registry.types()` (P6.5); API fuzz (P7.10); runtime purity (P7.12); golden regression (P3.12); hand-computed metric tests (P1.7, P2.7).
- **Mutation spot-check (do in scratch, never edit project files):** for each of these 6 behaviours, break it in memory (monkeypatch in a scratch script that imports the project and then runs the relevant test functions or equivalent assertions) and see whether any test would fail: (1) the leakage check, (2) seen-item exclusion, (3) cold-start vs user consistency, (4) API-key comparison, (5) `k` bounds, (6) popularity computed from train only. Report every behaviour that nothing protects.
- **Test-integrity forensics (the plan forbids weakening tests):** `git log -p -- backend/tests` and `git log --diff-filter=D --name-only -- backend/tests`: find commits that removed assertions, loosened tolerances, added `skip`/`xfail`, or deleted tests. Each is a finding with the commit hash.
- Coverage: if configured, run it (non-writing mode, output into `audit/scratch/`), list modules in `engine/` and `api/` below 80% and the uncovered error paths.

### AREA SEC: security and dependencies
- `git grep` for secrets: `-E "(api[_-]?key|secret|token|passwd|password)\s*[:=]"`, private-key markers, `.env*` tracked; also search history: `git log -p -S"API_KEY" --all` and similar (report hit counts, never print real secrets in your report; mask them).
- Unsafe constructs: `yaml.load` (non-safe), `eval`, `exec`, `pickle`/`joblib` loads, `subprocess` with `shell=True`, `os.system`, `tempfile.mktemp`, `assert` used for validation (removed under `python -O`), `requests` without `timeout=`, `verify=False`.
- **Downloads/archives (`scripts/fetch_data.py`, adapters):** checksum verification of downloaded files; zip/tar extraction safe against path traversal (`extractall` without member checks); URLs from config validated; resumable downloads can't be poisoned.
- API-level: items in AREA API Security; unbounded inputs; log injection (user-controlled strings logged raw); verbose errors.
- Dependencies: run `pip-audit` if available (log "not verifiable offline" if it fails); list dependencies that are unpinned, abandoned, or have known issues you can verify from the installed version.

### AREA PERF: performance and resources
- Complexity: nested Python loops over users/items, dense `N x N` matrices, `iterrows`/`apply(axis=1)`, repeated DataFrame filtering inside request handlers, full-catalogue scans for search, loading artifacts per request, copies of large frames per call.
- Memory: peak memory at training versus `max_items_in_similarity`; serving memory with all types loaded (measure RSS in a subprocess if artifacts exist, otherwise estimate from array shapes and say it is an estimate).
- Latency: if real artifacts exist, time `/v1/recommend` (precomputed and live paths), cold-start POST, search, similar, using an in-process `TestClient` in a scratch script; compare with the plan's R8 budgets (p95 < 150 ms; cold-start < 300 ms; RSS < 2 GB; `--fast` training < 10 min). If artifacts do not exist, say "not measured" instead of guessing.
- Read `scripts/bench_api.py`: does it measure what it claims (warm-up, enough requests, percentiles computed correctly, RSS of the right process)?

### AREA DOCS: documentation versus reality
- `docs/DECISIONS.md`: entries exist and are accurate for the deviations you found; each has context/decision/consequences.
- `docs/ATTRIBUTION.md`, `NOTICE.md`, `DATASETS.md`: accurate, complete, dataset licence terms and citations present for datasets actually used.
- **Fabricated or untraceable numbers (plan rule 5):** every number in `docs/RESULTS.md`, the README (if any), the Session Log and `docs/DECISIONS.md` must trace to a `metrics.json` or another pipeline-produced file. Check a sample of at least 15 numbers by finding their source. A number with no source is **CRITICAL**.
- Docstrings and comments that contradict the code; README commands (if a README exists) that do not work as written.

### AREA QUAL: general code quality across `engine/`, `api/`, `tools/`, `scripts/`
Dead code; copy-pasted logic across adapters or models (extract candidates); very long or complex functions (use `ruff check --select C901,PLR0911,PLR0912,PLR0913,PLR0915` as a read-only measurement; no `--fix`); broad `except Exception`/bare `except` that swallows errors; `print` instead of logging; mutable default arguments; public functions without type hints; `Any` overuse; misleading names; commented-out code; leftover TODO/FIXME/HACK (list them all); import-time side effects (file or env reads at import); resource leaks (`open` without context manager); naive `datetime.now()`/`utcnow()` (deprecated) instead of timezone-aware UTC; `os.path` and `pathlib` mixed; stringly-typed enums; boolean flag arguments; `assert` used for runtime validation; inconsistent error handling styles; functions that both compute and perform I/O.

### AREA GIT: repository history hygiene
Commit message convention (task ID prefix per the plan); giant or mixed commits; large or binary files ever committed (write a Python script over `git rev-list --objects --all` + `git cat-file --batch-check` to list blobs > 1 MB, even if later deleted); `.env` or secrets ever committed; ticked tasks without commits; missing `.gitattributes` (CRLF hazards on Windows); branch state. (You may not check out old commits, so judge whether each commit is coherent by reading its diff with `git show --stat`, not by building it.)

---

## 8. STAGE 3: Hardcoded-values sweep

Goal: find everything that is hardcoded but should be configurable, derived, or named; and everything environment-specific that will break on another machine.

**Step 8.1:** Save the script in Appendix A as `audit/scratch/hardcode_scan.py` and run it from the repo root: `python audit/scratch/hardcode_scan.py > audit/hardcoded_scan_raw.txt`. It prints candidate lines by category. It is a *detector*, not a judge: expect false positives.

**Step 8.2:** Triage EVERY category of the raw output into `audit/03_HARDCODED.md`. For each hit decide:
- `OK`: legitimate constant (mathematical, protocol, test data, an obviously named constant in one place).
- `SHOULD_BE_CONFIG`: a value the plan says belongs in YAML config, or that a user might reasonably change (thresholds, `k` lists, history sizes, minimum positives for personalised mode, window sizes, neighbour counts, seeds, file names, ports).
- `SHOULD_BE_ENV`: environment-dependent (paths, URLs, origins, keys, hostnames, ports).
- `SHOULD_BE_NAMED_CONSTANT`: magic number used in more than one place or whose meaning is unclear.
- `DUPLICATED_SOURCE_OF_TRUTH`: the same value defined in code and YAML (or in two modules); they will drift apart.
- `ENV_SPECIFIC`: absolute paths, `C:\`, `/home/`, backslash separators, `localhost` baked into logic, OS-specific assumptions.
- `TYPE_SPECIFIC_IN_CORE`: dataset/type names, column names, or rating thresholds inside engine core or API code.

**Step 8.3:** Beyond the script, manually check these known hot spots and record the result for each: the positive-signal threshold; split ratio and seed; `k` lists and the `1..50` API bound (one definition or many?); similarity parameters; time-decay coefficient; `top_neighbors_per_item`; `max_items_in_similarity`; recency window; history cap (200); minimum positives for personalised mode; search limits; default ports; artifact directory; CORS origins; API version prefix `/v1`; supported type names (derived from the registry or typed out?); file names of artifacts; number of demo users; the bootstrap resample count; `display_score` scaling.

**Step 8.4:** Group repeated hits into ONE finding with a list of all locations (do not create 40 findings for the same pattern).

---

## 9. STAGES 4 and 5: Dynamic verification and adversarial probing

Record everything in `audit/04_DYNAMIC_CHECKS.md`: the exact command, working directory, an output excerpt, and a verdict (`PASS`, `FAIL`, `NOT RUN (reason)`). Obey Section 5 step 0.3 (allow/deny lists) at all times. All scratch scripts live in `audit/scratch/`, import the project read-only, and write only inside `audit/scratch/`.

### Stage 4: verification runs (run those that are safe; mark the others `NOT RUN` with a reason)
1. Lint, format-check and type-check commands exactly as the project defines them (non-writing variants only). Record the number of errors by rule.
2. Full test suite. Run it a second time straight after. If `pytest-randomly` is installed, the two runs will use different orders; otherwise also run once more passing the test files explicitly in reverse alphabetical order. This detects order dependence and flaky tests. Report any test that fails in one run and passes in another.
3. `python -W error::DeprecationWarning -W error::FutureWarning -c "import engine, api.main"` (adjust to real module names) and report warnings that turn into errors.
4. Import-purity subprocess check for `engine`, `api.main` and each vendored module in use.
5. Environment hygiene: `python -c "import importlib.util as u; print(u.find_spec('recommenders'))"` must print `None`; also check the `tensorflow`, `torch`, `pyspark`, `cornac` packages are not installed in this environment (informational).
6. Determinism check: if you can run the training CLI with ALL output redirected into `audit/scratch/` (confirmed by reading the code), train the smallest available type in fast mode twice and compare **contents** of `topn.parquet` (load with pandas and compare frames, not file bytes). Otherwise mark `NOT RUN` and instead review determinism statically (AREA TRAIN).
7. Cross-process determinism of the baselines and the SAR wrapper in a scratch script with `PYTHONHASHSEED=0` versus `PYTHONHASHSEED=1`.
8. Artifact loader corruption tests in a **copy** of one small artifact directory placed under `audit/scratch/`: flip one byte of a file, delete a file, edit the manifest version, add a path-traversal file name in the manifest. Each must raise `ArtifactError` with an actionable message.
9. OpenAPI contract: generate the schema in-process, write it to `audit/scratch/openapi_now.json`, and diff it against the committed `openapi.json`.
10. Metrics recomputation: independent recomputation of metrics on a tiny example (see AREA EVAL).
11. Real-artifact sanity (only if `artifacts/<type>/` exists): load each type through the project loader; for 20 random users per type check all R3 invariants (length <= k, no duplicates, no seen items, ids exist, finite sorted scores, `similar_items` excludes the query item) using YOUR OWN assertion code, not the project's checker.
12. Coverage and benchmarks as described in AREA TEST and AREA PERF, if feasible.

### Stage 5: adversarial probing of the API ("break it")
Using FastAPI's `TestClient` (in-process, read-only) against the real app, try at least the following and record the status code, the body shape and whether it matched expectations. Any 500, any non-standard error shape, any stack trace, any hang is a finding.
- Every endpoint x every registered type x `k` in {-1, 0, 1, 50, 51, 10**9, "abc", 1.5, null}.
- Unknown type; type with path characters (`../`, `..\\`, `%2e%2e`, absolute paths, very long strings, unicode, null byte).
- Unknown user/item; empty-string ids; whitespace ids; ids of 10,000 characters; ids sent as numbers.
- Cold-start: empty history; only unknown ids; duplicate ids; exactly 200 and 201 entries; signals NaN, inf, negative, huge, strings; `exclude` containing history items and unknown items; malformed JSON; wrong content-type; body 1 MB+ (to test the size limit); history items given as bare strings instead of objects.
- Search: empty `q`, one character, 100 and 101 characters, regex metacharacters (`(a+)+$`, `.*`, `[`), unicode with accents and combining characters, emoji, SQL-like strings; `limit` of 0, -1, 1000.
- API key: missing, wrong, empty, non-ASCII (`"é"`, emoji), extremely long, with whitespace; with the feature on and off.
- Consistency: request recommendations for a user, then pass one result in `exclude`: it must disappear; compare `k=5` with the first 5 of `k=10` (same prefix); repeat the same request 20 times and from 8 threads (use `concurrent.futures`): results must be identical.
- Corrupt artifact: in a **copy** under `audit/scratch/`, corrupt one type's artifact and start the app against that directory (via the documented env var): the app must start, mark that type `unavailable`, and still serve the others.

---

## 10. Severity and confidence rubric (use exactly these definitions)

**Severity**
- `CRITICAL`: the system can silently produce wrong, misleading or untrustworthy results (data leakage, inflated or fabricated metrics, wrong recommendations, wrong explanations); licence or attribution violation; exploitable security hole; data loss or corruption; crash in normal use; a plan task ticked `[x]` whose acceptance criteria are clearly not met in a way that matters.
- `HIGH`: likely bug or contract violation that appears on common edge cases; reproducibility failure; non-determinism; violated plan invariant (R1 to R11); test suite that cannot catch an important failure; hardcoded value that will break on another machine or config.
- `MEDIUM`: best-practice violation or robustness gap that increases risk or maintenance cost; weak or misleading tests; duplicated sources of truth; performance risk; portability problems.
- `LOW`: minor smell, small inefficiency, naming, missing type hints, small inconsistencies.
- `INFO`: an observation, question, or a `DECISION_CHALLENGE`; not a defect by itself.

**Confidence**
- `VERIFIED`: you reproduced it by running something, or proved it unambiguously by reading code and confirmed no guard exists.
- `LIKELY`: strong code-reading evidence, not run.
- `SUSPECTED`: plausible but needs a dataset, an environment, or an author decision to confirm. State exactly what would settle it.

**Categories (tags):** `CORRECTNESS`, `LEAKAGE`, `REPRODUCIBILITY`, `SECURITY`, `LICENSE`, `HARDCODED`, `CONFIG`, `ERROR_HANDLING`, `CONCURRENCY`, `PERFORMANCE`, `TESTING`, `PLAN_VIOLATION`, `DOCS`, `PORTABILITY`, `MAINTAINABILITY`, `TYPING`, `DEPENDENCIES`, `DECISION_CHALLENGE`.

---

## 11. Finding format, JSON schema, and final report

### 11.1 Every finding in `audit/areas/*.md` uses this block (all fields mandatory)

```
### F-<AREA>-<NNN>: <short, specific title>
- Severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
- Confidence: VERIFIED | LIKELY | SUSPECTED
- Category: <one or two tags from Section 10>
- Location: <path:line-range>  (list all, if several)
- Plan reference: <task ID / gate R# / plan section, or "none">
- What is wrong (evidence): <what the code does, quoting at most 8 lines, with line numbers>
- Why it matters: <2 to 4 plain-language sentences; explain as to a capable beginner; describe the concrete failure>
- How I verified it: <command run / test / reasoning, and what I did to try to disprove it>
- What good looks like: <describe the correct behaviour or pattern; short illustrative snippet allowed (max 10 lines); do NOT apply it>
- Fix effort: S (< 30 min) | M (< half a day) | L (> half a day)
- Depends on / blocks: <other finding IDs, or none>
```

IDs: `F-<AREA>-<NNN>` with the area codes of Section 7 (`REPO, VEND, CORE, ADAP, MODL, EVAL, TRAIN, API, TEST, SEC, PERF, DOCS, QUAL, GIT`), plus `PLAN` (Stage 1) and `HARD` (Stage 3). Numbering restarts per area and never changes once written.

**Grouping rule:** the same defect pattern in many places is ONE finding with all locations. Different root causes are separate findings. Do not split one cause into several findings to inflate counts.

### 11.2 `audit/FINDINGS.json`

A single JSON array. One object per finding, with these keys (types in parentheses):
`id` (string), `title` (string), `severity` (string), `confidence` (string), `categories` (string[]), `locations` (string[] of `path:line` or `path:start-end`), `plan_reference` (string|null), `evidence` (string), `why_it_matters` (string), `verification` (string), `recommended_direction` (string), `effort` ("S"|"M"|"L"), `depends_on` (string[]), `area` (string), `status` (always `"open"`).
Validate it with a script: it must parse, every `id` must be unique, every ID referenced in `depends_on` must exist, and the counts per severity must equal the counts in `REPORT.md`.

### 11.3 `audit/REPORT.md` structure (in this order)

1. **Executive summary** (max 15 lines): overall trustworthiness verdict for the backend in plain language (for example: "metrics cannot be trusted until F-EVAL-003 is resolved"), counts by severity, counts by area.
2. **Top 10 risks**, ranked, each with ID, one-sentence impact, and why it ranks where it does.
3. **Plan-compliance summary**: tasks `MET` / `PARTIAL` / `NOT MET` / `UNVERIFIABLE` per phase, and the list of ticked tasks that are not truly done.
4. **Trustworthiness of the numbers**: can the reported metrics be believed? List every leakage or evaluation-validity concern and your confidence.
5. **Findings index**: a table of ALL findings (ID, severity, confidence, title, location), sorted by severity then area.
6. **Hardcoded-values summary** (link to `03_HARDCODED.md`).
7. **Recommended fix roadmap for Phase 2**: ordered batches. Batch 1 = anything that makes results wrong or untrustworthy (CRITICAL leakage/correctness/licence/security); Batch 2 = reproducibility and contract violations; Batch 3 = tests that must be strengthened BEFORE refactors (so fixes are protected); Batch 4 = hardcoded/config/portability; Batch 5 = maintainability and style. For each batch list finding IDs, the reason for the order, and which findings must be fixed together. Note any finding whose fix will change published metrics (so results must be regenerated).
8. **Questions for the human**: every decision or fact you could not determine alone (numbered, each answerable in one line).
9. **What I did NOT review or could not verify** (honest coverage statement): files skipped, commands not run and why, datasets/artifacts that were absent.
10. **What is done well** (max 10 lines, factual).
11. **Enhancement ideas** (max 10, clearly labelled as not defects).
12. **Commands run**: link to `04_DYNAMIC_CHECKS.md`, plus the read-only integrity result.

---

## 12. Self-verification checklist (complete BEFORE you declare done)

Copy this list into `audit/00_PROGRESS.md` and tick each item only if true:

- [ ] I opened and read the entire plan, including the Session Log.
- [ ] Every file listed in AREA "Files read" was actually opened by me.
- [ ] Every finding cites `path:line` that I opened, and I re-opened the cited lines for every CRITICAL and HIGH finding to confirm they say what I claim.
- [ ] For every CRITICAL and HIGH finding I tried to disprove it and wrote down how.
- [ ] No finding relies on a library behaviour I did not verify in installed source (Rule 2.6).
- [ ] The hardcoded sweep was run, and ALL categories were triaged, not just the first few.
- [ ] I produced a verdict row for every task P0.1 to P7.13.
- [ ] I checked that metrics and numbers in docs trace to pipeline output (at least 15 samples).
- [ ] I ran or consciously skipped each Stage 4 and Stage 5 item and recorded why.
- [ ] `FINDINGS.json` validates, and its severity counts equal those in `REPORT.md`.
- [ ] The read-only integrity check passed (or the deviation is reported and explained).
- [ ] The report states plainly what I did not cover.
- [ ] I did not edit the plan, tick markers, run `progress.py`, commit, or modify any project file.

If you are running low on context or quota: stop starting new areas, finish the current area file, update `00_PROGRESS.md` with exactly where you stopped and what remains, still write `FINDINGS.json` and a `REPORT.md` marked **PARTIAL** (sections 1 to 9 at minimum), and say so in your final message.

---

## 13. Final message in the chat (keep it short)

When finished, reply with only: (1) the path to `audit/REPORT.md`; (2) severity counts; (3) the top 5 risks in one line each; (4) the result of the read-only integrity check; (5) the number of open questions for the human; (6) anything that was NOT covered. Do not paste the full report into chat.

---

## Appendix A: `audit/scratch/hardcode_scan.py` (save exactly, then run from the repo root)

```python
"""Read-only scanner for hardcoded values. Prints candidates; a human/agent judges them."""
import re
import subprocess
import sys

# Only scan tracked, text-like source files.
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
files = [f for f in files if f.endswith((".py", ".yaml", ".yml", ".toml", ".cfg", ".ini", "Makefile", ".json", ".md"))]
skip = ("backend/discovery/", "uv.lock", "package-lock.json", "openapi.json", ".md")  # .md only listed for URL scan below

CATEGORIES = {
    "ABSOLUTE_PATH": r"(?:[A-Za-z]:[\\/]|/home/|/Users/|/tmp/|\\\\)[^\s'\"]*",
    "URL_OR_HOST": r"https?://[^\s'\"]+|localhost|127\.0\.0\.1|0\.0\.0\.0",
    "PORT": r"\bport\s*[=:]\s*\d{2,5}\b|:\d{4,5}\b",
    "SECRET_LIKE": r"(?i)(api[_-]?key|secret|token|passw(or)?d)\s*[:=]\s*['\"][^'\"]+['\"]",
    "TYPE_SPECIFIC": r"(?i)\b(movielens|movies?|products?|articles?|amazon|mind|rating|genre)\b",
    "MAGIC_NUMBER": r"(?<![\w.\"'])(?:[2-9]|\d{2,})(?:\.\d+)?(?![\w.\"'])",
    "SEED_LITERAL": r"(?i)seed\s*[=:(]\s*\d+|random_state\s*=\s*\d+",
    "BROAD_EXCEPT": r"except\s*:|except\s+Exception\b|except\s+BaseException\b",
    "PRINT_CALL": r"^\s*print\(",
    "TODO_MARKER": r"(?i)\b(TODO|FIXME|HACK|XXX)\b",
    "SUPPRESSION": r"#\s*(type:\s*ignore|noqa|pragma:\s*no cover)",
    "ASSERT_RUNTIME": r"^\s*assert\s",
    "UNSAFE_CALL": r"\b(eval|exec|pickle|cPickle|dill|joblib\.load|yaml\.load|os\.system|allow_pickle)\b|shell\s*=\s*True",
    "NAIVE_TIME": r"datetime\.(now|utcnow)\(\s*\)|time\.time\(\)",
}
SCOPE = {  # restrict noisy categories to code areas where they matter
    "TYPE_SPECIFIC": ("backend/engine/", "backend/api/", "tools/"),
    "MAGIC_NUMBER": ("backend/engine/", "backend/api/", "tools/", "backend/scripts/"),
    "ASSERT_RUNTIME": ("backend/engine/", "backend/api/"),
    "PRINT_CALL": ("backend/engine/", "backend/api/"),
}
EXCLUDE_TYPE_SPECIFIC = ("backend/engine/adapters/", "backend/engine/configs/", "backend/tests/")

for cat, pat in CATEGORIES.items():
    rx = re.compile(pat)
    print(f"\n===== {cat} =====")
    for f in files:
        if any(s in f for s in skip) and not (cat == "URL_OR_HOST" and f.endswith(".md")):
            continue
        if cat in SCOPE and not f.startswith(SCOPE[cat]):
            continue
        if cat == "TYPE_SPECIFIC" and f.startswith(EXCLUDE_TYPE_SPECIFIC):
            continue
        if cat in ("MAGIC_NUMBER", "ASSERT_RUNTIME", "PRINT_CALL") and "/tests/" in f:
            continue
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"!! cannot read {f}: {exc}", file=sys.stderr)
            continue
        for n, line in enumerate(lines, 1):
            if rx.search(line) and not line.lstrip().startswith(("#", "//")) or (cat in ("TODO_MARKER", "SUPPRESSION") and rx.search(line)):
                print(f"{f}:{n}: {line.strip()[:160]}")
```

## Appendix B: `audit/scratch/snapshot.py` (read-only integrity snapshot)

```python
"""Usage: python audit/scratch/snapshot.py before|after   -> writes audit/scratch/snapshot_<name>.json"""
import hashlib
import json
import pathlib
import subprocess
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "before"
roots = ["artifacts", "data/processed"]
out = {}

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
for f in tracked:
    p = pathlib.Path(f)
    if p.is_file():
        out[f] = sha(p)
for r in roots:
    for p in pathlib.Path(r).rglob("*") if pathlib.Path(r).exists() else []:
        if p.is_file():
            out[p.as_posix()] = sha(p)

pathlib.Path("audit/scratch").mkdir(parents=True, exist_ok=True)
pathlib.Path(f"audit/scratch/snapshot_{name}.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
print(f"{len(out)} files hashed -> audit/scratch/snapshot_{name}.json")
if name == "after" and pathlib.Path("audit/scratch/snapshot_before.json").exists():
    before = json.loads(pathlib.Path("audit/scratch/snapshot_before.json").read_text(encoding="utf-8"))
    changed = sorted(k for k in set(before) | set(out) if before.get(k) != out.get(k))
    print("CHANGED FILES:", changed if changed else "none")
```
