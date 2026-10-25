# Review report

- Date: 2026-10-25
- Machine: QUANTUM-BYTE
- Python: Python 3.11.7 (project venv `.\.venv\Scripts\python.exe`)
- Project root: `E:\discover`

## 1. Summary table

| Step | Check (short name) | Verdict |
|---|---|---|
| 0 | Environment / `.venv` present, Python runs | PASS |
| 1.1 | `git status --short` clean | FAIL |
| 1.2 | `git log --oneline -15` | PASS |
| 2 | Plan done-count vs dashboard | PASS |
| 3.1 | `ruff check backend` | PASS |
| 3.2 | `ruff format --check backend` | PASS |
| 3.3 | `mypy engine/ api/` | PASS |
| 3.4 | `pytest tests/ -q -rs` (full suite) | PASS |
| 4.1 | No `import recommenders` / `from recommenders` | PASS |
| 4.2 | `engine/config.py` names no content types | PASS |
| 4.3 | No `\|\| true` in CI workflow | PASS |
| 4.4 | `Project_details.md` absent | PASS |
| 4.5 | `.gitattributes` present | PASS |
| 4.6 | `backend\engine\configs\toy.yaml` absent | FAIL |
| 4.7 | `tools\vendored_manifest.py --check` | PASS |
| 4.8 | `tools\core_unchanged.py` | PASS |
| 4.9 | `backend\README.md` present | PASS |
| 5.1 | Artifacts exist per content type | PASS |
| 5.2 | `metrics.json` users > 1000 and CIs (movies/products) | PASS |
| 5.3 | Articles labelled synthetic in artifacts | PASS |
| 5.4 | `docs\RESULTS.md` readable | PASS |
| 5.5 | No "beats Popularity" / "decisively" / "3.5x" claims | PASS |
| 5.6 | Synthetic label near Articles section | PASS |
| 6.1 | Spot-check test inventory | PASS |
| 6.2 | `pytest -k leak` | PASS |
| 6.3 | `pytest -k consistency` | PASS |
| 6.4 | `pytest -k explain` | PASS |
| 6.5 | `pytest -k determin` | PASS |
| 7.1 | `backend\api\main.py` >= 30 lines | PASS |
| 7.2 | `backend\tests\contract` exists | PASS |
| 7.3 | `pytest tests\contract -q` | FAIL |

## 2. Progress

- Done tasks (Command 2.1): **73**
- Total tasks (Command 2.2): **129**
- Dashboard "Overall" Done row in the Command 2.4 output: **73**
- Match: **Yes** (73 = 73). Dashboard bar in that same output: `[###########---------] 56%  (73/129 tasks)`.
- In-progress / blocked tasks from Command 2.3: Command 2.3 printed **nothing**. A narrower read-only check (`Select-String -Path IMPLEMENTATION_PLAN.md -Pattern '\[!\] \*\*P5'`) found one blocked task:
  - `- [!] **P5.1**` Dataset step (MIND manual download blocked; HTTP 409/401 on automated Azure blob access).

Note: while this review was running, `IMPLEMENTATION_PLAN.md` changed on disk. A read made after Command 2.4 shows Phase 7 `Done = 2` and Overall `74 / 129 (57%)`, whereas the Command 2.4 output captured `Done = 1` for Phase 7 and Overall `73`. See Problem 9.

## 3. Problems found

1. **Check 1.1 – working tree is dirty (uncommitted work).**
   ```
    M backend/api/errors.py
    M backend/api/main.py
    M backend/api/schemas.py
    M backend/tests/integration/test_products_gate.py
   ?? backend/tests/unit/test_api_errors.py
   ```
   Severity: MEDIUM.

2. **Check 3.4 – one test is skipped.** The suite reports `307 passed, 1 skipped` and the skip reason is:
   ```
   SKIPPED [1] tests\integration\test_clean_room.py:29: Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py
   ```
   SKIPPED TESTS: `tests/integration/test_clean_room.py::<test at line 29>` (clean-room rebuild, ~7.5m, requires `RUN_CLEAN_ROOM=1`).
   Severity: MEDIUM (skipped test).

3. **Check 4.6 – `backend\engine\configs\toy.yaml` still exists** (`Test-Path` printed `True`, expected `False`). The artifact tree also contains a `toy` folder (`artifacts\toy\...`, see 5.1), which matches this leftover.
   Severity: LOW.

4. **Check 7.3 – 11 contract tests fail.** Failure kinds in the output:
   ```
   E                   AttributeError: 'ContentTypeSpec' object has no attribute 'name'
   E       assert 404 == 200
   E       where 404 = <Response [404 Not Found]>.status_code
   E       KeyError: 'metrics'
   ```
   Final line:
   ```
   11 failed, 8 passed, 1 warning in 6.89s
   ```
   Failing tests: `test_types_endpoint_contract`; `test_item_detail_endpoint_contract[movies|products|articles]`; `test_search_endpoint_contract[movies|products|articles]`; `test_search_hierarchical_ranking_and_normalization`; `test_metrics_endpoint_contract[movies|products|articles]`.
   Severity: HIGH (failing tests).

5. **Checks 3.4 vs 7.3 – same tests give opposite results.** The full-suite run ended with:
   ```
   307 passed, 1 skipped, 1 warning in 214.75s (0:03:34)
   ```
   with no failures (that run includes `tests/contract`), while the directory run of the same contract tests ended with:
   ```
   11 failed, 8 passed, 1 warning in 6.89s
   ```
   The suite is order/state dependent (or the files changed between the two runs; see Problem 9). A green full-suite result cannot currently be relied on.
   Severity: HIGH.

6. **Check 5.4 – RESULTS.md marks a target as "Verified" although the measured value misses it.** Exact row:
   ```
   | **Long-Tail Volume Share** | `43.0%` (6400/8000 items) | > 50% tail volume | Verified |
   ```
   `43.0%` is below the stated `> 50%` target but the status column says `Verified`.
   Severity: HIGH (false claim in RESULTS.md).

7. **Check 5.4 – RESULTS.md products section names the wrong dataset.** Section heading:
   ```
   ## 2. Products Pipeline (Amazon Instruments + SAR)
   ```
   while the provenance table and artifact say `video_games`:
   ```
   | **Products** | `video_games` | `3a183b5` | `4113810a` | `42` | Chronological per-user split (budget-capped) |
   ```
   Severity: MEDIUM (misleading dataset label).

8. **Check 5.4 – "Model > Popularity Point Estimate" sanity check labelled `Passed` while several table rows are negative.** Exact line and rows:
   ```
   - **Sanity Check (Model > Popularity Point Estimate):** `Passed`
   ```
   ```
   | **NDCG@5** | 0.0042 | 0.0545 [0.0484, 0.0612] | **0.0517 [0.0455, 0.0577]** | **-5.2%** | No significant difference (CIs overlap) |
   | **Precision@5** | 0.0041 | 0.0484 [0.0429, 0.0539] | **0.0459 [0.0409, 0.0508]** | **-5.2%** | No significant difference (CIs overlap) |
   ```
   (also `Precision@10 -1.1%`, `Precision@20 -2.0%`). The blanket "Passed" wording is not supported by every metric in the same table.
   Severity: MEDIUM.

9. **Check 2.4 / general – `IMPLEMENTATION_PLAN.md` was modified during the review.** Command 2.4 captured:
   ```
   | | **Overall** | **73** | | | **129** | **56%** |
   ```
   A later read of the same file shows:
   ```
   | | **Overall** | **74** | | | **129** | **57%** |
   ```
   (Phase 7: `1` → `2`). This is consistent with the uncommitted `backend/api/*` files reported in 1.1: work is in progress while the review runs.
   Severity: MEDIUM.

## 4. Things that look good

- Step 0: required layout present; `.venv` exists; Python 3.11.7 runs.
- 1.2: history is coherent (P7.1 and P6.x commits present, 15 shown).
- 2.1/2.2/2.4: dashboard matched the done-count at the time of the check (73/129).
- 3.1: `All checks passed!`; 3.2: `100 files already formatted`.
- 3.3: `Success: no issues found in 40 source files`.
- 3.4: 307 tests pass, 0 failures, 0 errors.
- 4.1: no vendored `recommenders` imports.
- 4.2: `engine/config.py` contains none of `"movies"`, `"articles"`, `"products"`.
- 4.3: CI has no `|| true` suppressions.
- 4.7: vendored manifest is up to date.
- 4.8: core-unchanged check passes, with changes documented in `DECISIONS.md`.
- 5.2: movies (1,918 users) and products (1,534 users) have bootstrap CIs (`bootstrap_resamples: 500`, `bootstrap_ci: 0.95`, `*_ci95` fields).
- 5.3 / 5.6: Articles are explicitly labelled `SYNTHETIC DEMO (not MIND)` in artifacts and in `RESULTS.md`.
- 5.5: no "beats Popularity", "decisively" or "3.5x" wording remains.
- 6.2–6.5: leak (18), consistency (15), explain (9) and determinism (5) test groups all pass.
- 7.1/7.2: API app is 108 lines; contract test folder exists.

## 5. Not checked / unsure

- **Command 2.3 – UNSURE.** The command printed nothing, but a narrower `Select-String` and the dashboard both show `P5.1` as blocked; either the shell quoting of `(~|!)` was mangled in this harness or the file changed between calls.
- **Checks 3.4 vs 7.3 – UNSURE on cause.** I cannot tell from the output alone whether the contract failures in isolation are order/state dependent, caused by the uncommitted `api/*` edits, or both.
- **Articles evaluation (5.2) – not real evidence by design.** `evaluated_test_users: 3`, `evaluated_impressions: 9`, dataset `SYNTHETIC DEMO (not MIND)`. This is disclosed in artifacts and docs, so it is not a verdict failure, but it supports nothing about real MIND quality.
- `artifacts\toy\*` exists (5.1) although `toy.yaml` should be absent (4.6); the two findings are the same leftover config.

## 6. Raw output

### Command 0.1
```
Path       
----       
E:\discover
```

### Command 0.2
```
.github
.hypothesis
.mypy_cache
.ruff_cache
.venv
artifacts
backend
data
docs
frontend
tools
.gitattributes
.gitignore
.pre-commit-config.yaml
IMPLEMENTATION_PLAN.md
LICENSE
Makefile
README.md
```

### Command 0.3
```
True
```

### Command 0.4
```
Python 3.11.7
```

### Command 1.1
```
 M backend/api/errors.py
 M backend/api/main.py
 M backend/api/schemas.py
 M backend/tests/integration/test_products_gate.py
?? backend/tests/unit/test_api_errors.py
```

### Command 1.2
```
44ac703 P7.1: FastAPI app skeleton with lifespan artifact loader and corrupt directory resilience
5595b53 P6.8: Phase 6 Gate and five Break-Your-Own-Work rituals across all domains
951165a FIX-27: Update Session Log with entries for P6.1 to P6.5, P6.6 to P6.7, and FIX-23 to FIX-26; add api/ to core_unchanged allowed patterns
113e55d FIX-26: Products Video Games headline artifacts, SAR serving latency optimization (p95 1.33 ms vs 150 ms target), and D-013 recording
3a183b5 FIX-25: Label Articles as SYNTHETIC DEMO everywhere and clarify it is not real evidence
3705981 FIX-24: Label Articles dataset as synthetic fixture across artifacts and docs
3ceb794 FIX-23: Remove hardcoded verdicts and claims from make_results.py and RESULTS.md
b38aaf8 P6.7: Comprehensive failure-mode and known limitations review in DECISIONS.md
14251bf P6.6: Statistical honesty reporting with bootstrap 95% CIs across all domains in RESULTS.md
b5a2e22 docs: regenerate RESULTS.md and figures with bootstrap CIs
90b281a P6.5: Parametrised cross-type consistency tests over registry.types() and R3 invariant suite
d23da3a FIX-22: Re-open P5.3, document Phase 5 status, and pause pending real MIND files
50f9146 P6.4: Clean-room rebuild verification, performance benchmark, and test suite hardening
f00a8fe FIX-21: Correct overclaims in D-010, D-011, and Session 7 log
889813f FIX-20: Video Games products training, peak memory measurement, and D-013 correction
```

### Command 2.1
```
73
```

### Command 2.2
```
129
```

### Command 2.3
```
(no output)
```

Alternative read-only check allowed for an ENV/UNSURE situation:
```
IMPLEMENTATION_PLAN.md:206:- [!] **P5.1** Dataset step: verified vendored helpers (`download_mind`, `extract_mind` in `discovery.datasets.mind`); recorded license (MSR License for Data) and citation in `docs/DATASETS.md`. Automated anonymous Azure blob access is restricted by Microsoft (HTTP 409/401); documented manual download instructions (Hugging Face / Kaggle to `data/raw/mind/train/` and `data/raw/mind/dev/`) in `fetch_data.py` and `docs/DATASETS.md`; verified offline fixture in `backend/tests/fixtures/mind/` loads cleanly. *Acceptance:* files load or blocked note written.
```

### Command 2.4 (first 30 and last 30 lines)
```
# Discovery Engine: Adaptive Content Recommendation Engine
## Implementation Plan (single source of truth for the coding agent)

> **Read this whole file section by section before writing any code.** Sections 0 to 3 are mandatory reading at the start of every session. You may be one of several agent sessions running on different accounts, so this file and the git history are the only shared memory.

---

## 0. Agent operating rules (READ FIRST, EVERY SESSION)

1. **This file is the source of truth.** At the start of every session: read sections 0 to 3, the Progress Dashboard, and the last 3 entries of the Session Log (end of file). Then continue from the first unfinished task of the lowest-numbered unfinished phase.
2. **Status markers** (use exactly these):
   - `[ ]` not started
   - `[~]` in progress (add a one-line note under it saying what is done and what remains)
   - `[!]` blocked (add a note saying why and what the human must do; then move on to a task that does not depend on it)
   - `[x]` done (acceptance criteria met AND tests pass)
3. **After every task:** update its marker, run `python tools/progress.py` (created in task P0.6; until then, update the dashboard by hand), and make a git commit whose message starts with the task ID, e.g. `P3.5: SAR wrapper with cold-start scoring`.
4. **Never tick a task whose tests fail.** Never delete, skip, or weaken a test to make something pass. If a test is wrong, fix it and explain why in the Session Log.
5. **No fabricated results.** Every number shown anywhere (README, UI, RESULTS.md) must come from a file produced by the pipeline (`artifacts/<type>/metrics.json`). No placeholder or invented metrics, ever. If something cannot be computed, mark it `[!]` and say why.
6. **Verify library APIs against the real source.** This plan names Recommenders classes and functions from memory (for example `SAR`, `TfidfRecommender`, `python_chronological_split`). Names or signatures may differ in the version you vendor. Read the source before using it and adjust. Record any difference in `docs/DECISIONS.md`.
7. **Stay in scope.** Do not add features that are not in this plan without writing a decision entry in `docs/DECISIONS.md`. Optional work lives only in Phase 12 and starts only after Phases 0 to 11 are complete.
8. **Robustness is the main goal of this project.** After every phase you must run the Phase Gate (section 10) and record the results in the Session Log. Recommendation quality and correctness matter more than UI polish. See section 10 for the "break your own work" ritual.
9. **Ask the human only for:** manual dataset downloads, API keys, and tasks marked `HUMAN`. For everything else make a reasonable decision, document it, and continue.
10. **End of session / low quota protocol:** stop starting new tasks when you suspect quota is running low. Finish or cleanly revert the current task, make sure the working tree builds and tests pass, commit, mark unfinished tasks `[~]` with notes, and append a Session Log entry using the template at the end of this file.
11. **Order of work is fixed:** backend recommendation engine first (Phases 0 to 7), frontend second (Phases 8 to 10), documentation and showcase prep (Phase 11), optional extras last (Phase 12).
12. **Every phase must end with something that runs.** If the project is stopped after any phase, there must be a working, documented state to demonstrate.

---

## Progress Dashboard

[middle cut]
| 5 | Articles pipeline (MIND + TF-IDF content model) | 10 | 0 | 1 | 12 | 83% |
| 6 | Cross-type hardening and evidence | 8 | 0 | 0 | 8 | 100% |
| 7 | FastAPI backend | 1 | 0 | 0 | 13 | 7% |
| 8 | Frontend scaffolding | 0 | 0 | 0 | 9 | 0% |
| 9 | Frontend features | 0 | 0 | 0 | 12 | 0% |
| 10 | Integration and robustness audit | 0 | 0 | 0 | 8 | 0% |
| 11 | Documentation and showcase preparation | 0 | 0 | 0 | 8 | 0% |
| 12 | Optional stretch (only after Phases 0 to 11 are complete) | 0 | 0 | 0 | 5 | 0% |
| | **Overall** | **73** | | | **129** | **56%** |

`[###########---------] 56%  (73/129 tasks)`
<!-- PROGRESS:END -->

---

## 1. Project overview

**Name:** Discovery Engine. Use this exact name (title case) in the README, the UI header and browser tab title, the About tab, the API title (`FastAPI(title="Discovery Engine")`), the report assets, and the demo script. Repository and folder name: `discovery-engine`. Note that `discovery/` (the vendored, renamed Recommenders package) and `engine/` (original code) are internal package names and are different from the project name; never present `discovery/` as the project itself.

**Goal:** an engine that adapts to the content type and produces personalised recommendations. A user selects a content type (Movies, Products, Articles) and a user, and sees that user's profile and personalised recommendations, with explanations, comparisons against non-personalised baselines, a cold-start demo, and an honest evaluation of every model.

**Context:** a college showcase project (non-commercial). Evaluators will look at (a) whether it works, (b) whether it genuinely adapts across content types through one engine, and (c) whether the recommendation quality is measured honestly and the design decisions are justified.

**Core idea:** one *engine* with one interface. Each content type plugs in through a *dataset adapter* (data to unified schema) plus a *config file* (signal rules, model choice, hyperparameters, split strategy, card type). Adding a content type must not require changing engine core code. Phase 6 proves this with a test.

**Non-goals:** user accounts/login, real-time learning from live traffic, production deployment, commercial use, image/audio analysis, LLM-based recommendation.

---

## 2. Locked decisions
```

### Command 3.1
```
All checks passed!
```

### Command 3.2
```
100 files already formatted
```

### Command 3.3
```
pyproject.toml: note: unused section(s): module = ['sklearn', 'tests.*']
Success: no issues found in 40 source files
```

### Command 3.4
```
.................s.............................................................................................. [ 36%]
................................................................................................................ [ 72%]
....................................................................................                             [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================================== short test summary info ===============================================
SKIPPED [1] tests\integration\test_clean_room.py:29: Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py
307 passed, 1 skipped, 1 warning in 214.75s (0:03:34)
```

Counts: **307 passed, 0 failed, 1 skipped**.

### Command 4.1
```
(no output)
```

### Command 4.2
```
(no output)
```

### Command 4.3
```
(no output)
```

### Command 4.4
```
False
```

### Command 4.5
```
True
```

### Command 4.6
```
True
```

### Command 4.7
```
Manifest check passed: docs/VENDORED_FILES.md is up to date.
```

### Command 4.8
```
Comparing diff between base '6da1d3a' and target 'HEAD'...
[NOTE] Core files modified (11), but documented in DECISIONS.md.

[SUCCESS] Core Unchanged Check PASSED.
All changes since Phase 3 (6da1d3a) are strictly restricted to:
  - adapters/ (AmazonProductsAdapter)
  - configs/ (products.yaml)
  - tests/ (products split leakage, amazon adapter, product checks)
  - docs/ (DATASETS.md, DECISIONS.md)
  - tools/ & scripts/ (product_checks.py, fetch_data.py)
Zero core engine abstractions were modified.
```

### Command 4.9
```
True
```

### Command 5.1
```
FullName                                                    Length
--------                                                    ------
E:\discover\artifacts\articles\data_report.json                502
E:\discover\artifacts\articles\demo_users.json                1248
E:\discover\artifacts\articles\interactions.parquet           3479
E:\discover\artifacts\articles\items.parquet                 10161
E:\discover\artifacts\articles\manifest.json                  1708
E:\discover\artifacts\articles\metrics.json                  19013
E:\discover\artifacts\articles\topn.parquet                   3165
E:\discover\artifacts\articles\users.parquet                  4488
E:\discover\artifacts\articles\model\idf.npy                   264
E:\discover\artifacts\articles\model\item_ids.json             144
E:\discover\artifacts\articles\model\item_titles.json         1141
E:\discover\artifacts\articles\model\model_meta.json          3007
E:\discover\artifacts\articles\model\tfidf_matrix.npz         1243
E:\discover\artifacts\articles\model\vocabulary.json           287
E:\discover\artifacts\movies\data_report.json                  609
E:\discover\artifacts\movies\demo_users.json                  1389
E:\discover\artifacts\movies\interactions.parquet          5436688
E:\discover\artifacts\movies\items.parquet                  269520
E:\discover\artifacts\movies\manifest.json                   1666
E:\discover\artifacts\movies\metrics.json                   10469
E:\discover\artifacts\movies\topn.parquet                   290394
E:\discover\artifacts\movies\tuning.json                     6457
E:\discover\artifacts\movies\users.parquet                  146908
E:\discover\artifacts\movies\model\index2item.json           71576
E:\discover\artifacts\movies\model\index2user.json          112546
E:\discover\artifacts\movies\model\item_frequencies.npy      31192
E:\discover\artifacts\movies\model\item_similarity.npz     1054932
E:\discover\artifacts\movies\model\model_meta.json        12015915
E:\discover\artifacts\movies\model\user_affinity.npz       5402774
E:\discover\artifacts\products\data_report.json                523
E:\discover\artifacts\products\demo_users.json                1514
E:\discover\artifacts\products\interactions.parquet        1305839
E:\discover\artifacts\products\items.parquet                450778
E:\discover\artifacts\products\manifest.json                 1677
E:\discover\artifacts\products\metrics.json                 13782
E:\discover\artifacts\products\topn.parquet                 300655
E:\discover\artifacts\products\tuning.json                   6468
E:\discover\artifacts\products\users.parquet                575479
E:\discover\artifacts\products\model\index2item.json        198893
E:\discover\artifacts\products\model\index2user.json        711697
E:\discover\artifacts\products\model\item_frequencies.npy     64128
E:\discover\artifacts\products\model\item_similarity.npz    2394341
E:\discover\artifacts\products\model\model_meta.json        4759612
E:\discover\artifacts\products\model\user_affinity.npz      857407
E:\discover\artifacts\toy\demo_users.json                      305
E:\discover\artifacts\toy\interactions.parquet                4639
E:\discover\artifacts\toy\items.parquet                       6214
E:\discover\artifacts\toy\manifest.json                        999
E:\discover\artifacts\toy\metrics.json                        1852
E:\discover\artifacts\toy\topn.parquet                         3383
E:\discover\artifacts\toy\users.parquet                        2432
E:\discover\artifacts\toy\model\popularity_model.json         3557
```

Content types with artifacts: **movies, products, articles** (plus `toy`).

### Command 5.2 – movies (first 30 and last 30 lines)
```
{
  "protocol": {
    "split_strategy": "chronological",
    "split_ratio": 0.8,
    "allow_repeat": false,
    "positive_threshold": 4.0,
    "total_interactions": 999611,
    "total_items": 3883,
    "evaluated_test_users": 1918,
    "total_test_users": 2000,
    "bootstrap_resamples": 500,
    "bootstrap_ci": 0.95
  },
  "seeds": {
    "split_seed": 42,
    "model_seed": 42
  },
  "config_hash": "5611260fd9470eee2079073b9f61b67d114a59258490b76146fa90b0fcc4a14d",
  "git_sha": "58be077eae00a7d2a124f81445dc9c536ced4d94",
  "created_at": "2026-10-25T09:50:39.482974+00:00",
  "content_type": "movies",
  "dataset_variant": "1m",
  "k_values": [
    5,
    10,
    20
  ],
  "models": {
    "popularity": {
      "5": {
[middle cut]
        "hit_rate": 0.17362,
        "hit_rate_ci95": [
          0.15693,
          0.19266
        ],
        "coverage": 0.01957249549317538,
        "novelty": 8.369621734223456,
        "diversity": 0.7332471428571428,
        "personalisation": 0.7043116375528435
      },
      "10": {
        "precision": 0.04181,
        "precision_ci95": [
          0.03803,
          0.04594
        ],
        "recall": 0.04452,
        "recall_ci95": [
          0.03894,
          0.04943
        ],
        "ndcg": 0.05464,
        "ndcg_ci95": [
          0.04923,
          0.06063
        ],
        "map": 0.02582,
        "map_ci95": [
          0.02236,
          0.0292
```

- Dataset name: `1m` (MovieLens variant, `dataset_variant: "1m"`).
- Users evaluated: `evaluated_test_users: 1918` (> 1000).
- "bootstrap"/"ci"/"confidence": **yes** — `bootstrap_resamples: 500`, `bootstrap_ci: 0.95`, and `*_ci95` arrays.

### Command 5.2 – products (first 30 and last 30 lines)
```
{
  "protocol": {
    "split_strategy": "chronological",
    "split_ratio": 0.8,
    "allow_repeat": false,
    "positive_threshold": 4.0,
    "total_interactions": 216994,
    "total_items": 8000,
    "evaluated_test_users": 1534,
    "total_test_users": 2000,
    "bootstrap_resamples": 500,
    "bootstrap_ci": 0.95
  },
  "seeds": {
    "split_seed": 42,
    "model_seed": 42
  },
  "config_hash": "4113810a78b3f7a63148a1fb12c45ef4acb29edb4e309fea28840f25cdd807b9",
  "git_sha": "3a183b5bb2cd1699baabab958db98a6e0522074b",
  "created_at": "2026-10-25T13:44:50.152570+00:00",
  "content_type": "products",
  "dataset_variant": "video_games",
  "k_values": [
    5,
    10,
    20
  ],
  "models": {
    "popularity": {
      "5": {
[middle cut]
        "hit_rate": 0.01825,
        "hit_rate_ci95": [
          0.01173,
          0.02542
        ],
        "coverage": 0.001125,
        "novelty": 8.638246664430197,
        "diversity": 0.8429506929590016,
        "personalisation": 0.05928451782723141
      },
      "10": {
        "precision": 0.00359,
        "precision_ci95": [
          0.00274,
          0.00456
        ],
        "recall": 0.03238,
        "recall_ci95": [
          0.02483,
          0.04159
        ],
        "ndcg": 0.0163,
        "ndcg_ci95": [
          0.01198,
          0.02172
        ],
        "map": 0.01095,
        "map_ci95": [
          0.00757,
          0.01465
```

- Dataset name: `video_games` (`dataset_variant: "video_games"`).
- Users evaluated: `evaluated_test_users: 1534` (> 1000).
- "bootstrap"/"ci"/"confidence": **yes** — `bootstrap_resamples: 500`, `bootstrap_ci: 0.95`, `*_ci95` arrays.

### Command 5.2 – articles (first 30 and last 30 lines)
```
{
  "protocol": {
    "split_strategy": "impression_time",
    "split_ratio": 0.8,
    "allow_repeat": false,
    "positive_threshold": 1.0,
    "total_interactions": 25,
    "total_items": 15,
    "evaluated_test_users": 3,
    "evaluated_impressions": 9,
    "dual_protocol": true
  },
  "protocols": {
    "impression_ranking": {
      "description": "MIND-style candidate ranking per impression",
      "evaluated_impressions": 9,
      "models": {
        "popularity": {
          "auc": 0.5278,
          "auc_ci95": [
            0.2778,
            0.75
          ],
          "mrr": 0.6296,
          "mrr_ci95": [
            0.4444,
            0.8148
          ],
          "ndcg@5": 0.7249,
          "ndcg@5_ci95": [
[middle cut]
          "mrr": 1.0,
          "mrr_ci95": [
            1.0,
            1.0
          ],
          "ndcg@5": 1.0,
          "ndcg@5_ci95": [
            1.0,
            1.0
          ],
          "ndcg@10": 1.0,
          "ndcg@10_ci95": [
            1.0,
            1.0
```

- Dataset name: `SYNTHETIC DEMO (not MIND)` (from `dataset_variant` further in the file).
- Users evaluated: `evaluated_test_users: 3`; impressions: `9`.
- "bootstrap"/"ci"/"confidence": `*_ci95` keys are present; `bootstrap` was not visible in the first 80 lines.

### Command 5.3
```
artifacts\articles\manifest.json:7:  "dataset_variant": "SYNTHETIC DEMO (not MIND)",
artifacts\articles\manifest.json:24:  "is_synthetic": true,
artifacts\articles\manifest.json:25:  "synthetic_fixture": true,
artifacts\articles\manifest.json:26:  "synthetic_demo": true,
artifacts\articles\manifest.json:27:  "label": "SYNTHETIC DEMO"
artifacts\articles\metrics.json:410:  "dataset_variant": "SYNTHETIC DEMO (not MIND)",
artifacts\articles\metrics.json:777:  "is_synthetic": true,
artifacts\articles\metrics.json:778:  "synthetic_fixture": true,
artifacts\articles\metrics.json:779:  "synthetic_demo": true,
artifacts\articles\metrics.json:780:  "label": "SYNTHETIC DEMO",
artifacts\articles\metrics.json:781:  "provenance_banner": "SYNTHETIC DEMO: Evaluated on synthetic offline fixture 
(backend/tests/fixtures/mind/). Results are for demonstration purposes only, not real-world evidence."
```

### Command 5.4 (first 30 and last 30 lines)
```
# Discovery Engine: Comprehensive Evaluation & Cross-Type Results

> **Single Source of Truth:** This file is auto-generated by `python tools/make_results.py` directly
> from production pipeline artifacts (`artifacts/{movies,products,articles}/metrics.json`).
> Contains strictly zero fabricated or hand-typed metrics.

## Provenance & Run Metadata

| Content Type | Dataset Variant | Git Commit | Config Hash | Seed | Evaluation Protocol |
|---|---|---|---|---|---|
| **Movies** | `1m` | `58be077` | `5611260f` | `42` | Chronological per-user split (80/20) |
| **Products** | `video_games` | `3a183b5` | `4113810a` | `42` | Chronological per-user split (budget-capped) |
| **Articles** | `SYNTHETIC DEMO (not MIND)` | `90b281a` | `b9ac2896` | `42` | Dual protocol: Impression ranking + 24h Window retrieval |

---

## Executive Summary

Discovery Engine unifies three fundamentally disparate recommendation regimes under a single extensible architecture:

1. **Movies (Collaborative Filtering)**: Evaluated on 1m (999,611 interactions, 1,918 test users). Coverage ratio SAR/Popularity is 5.7x. NDCG@10: 0.0592 [0.0541, 0.0644] vs Popularity 0.0546 [0.0492, 0.0606] (No significant difference (CIs overlap)). Recall@10: 0.0645 [0.0577, 0.0716] vs Popularity 0.0445 [0.0389, 0.0494] (Model better (CIs separate)).
2. **Products (E-Commerce)**: Evaluated on video_games (216,994 interactions, 1,534 test users). HitRate@10: 0.0861 [0.0740, 0.1017] vs Popularity 0.0358 [0.0267, 0.0450] (Model better (CIs separate)). NDCG@10: 0.0453 [0.0377, 0.0544] vs Popularity 0.0163 [0.0120, 0.0217] (Model better (CIs separate)).
3. **Articles (Content & Recency)**: Evaluated on SYNTHETIC DEMO (not MIND) (9 impressions). Impression AUC: 0.9722 [0.9167, 1.0000] vs Popularity 0.5278 [0.2778, 0.7500] (Model better (CIs separate)). Impression MRR: 1.0000 [1.0000, 1.0000] vs Popularity 0.6296 [0.4444, 0.8148] (Model better (CIs separate)).

![Cross-Domain Recommendation Performance](figures/ranking_comparison.png)

---

## 1. Movies Pipeline (MovieLens + SAR)

Evaluated using identical candidate retrieval pool against positive holdout ratings ($\ge 4.0$).

[middle cut]
Evaluated using a rigorous **Dual-Protocol Architecture** tailored for news consumption:

### Protocol (a): Impression Ranking (MIND Protocol)
Ranks candidates within each impression log (1 positive click amongst negative impressions).

| Model | AUC (95% CI) | MRR (95% CI) | nDCG@5 (95% CI) | nDCG@10 (95% CI) | Statistical Verdict (vs Pop) |
|---|---|---|---|---|---|
| **Random** | `0.2778 [0.0556, 0.5000]` | `0.5185 [0.3704, 0.7037]` | `0.6313 [0.5291, 0.7641]` | `0.6313 [0.5291, 0.7641]` | No significant difference (CIs overlap) |
| **Popularity** | `0.5278 [0.2778, 0.7500]` | `0.6296 [0.4444, 0.8148]` | `0.7249 [0.5873, 0.8624]` | `0.7249 [0.5873, 0.8624]` | Baseline |
| **TF-IDF Profile** | **`0.9722 [0.9167, 1.0000]`** | **`1.0000 [1.0000, 1.0000]`** | **`1.0000 [1.0000, 1.0000]`** | **`1.0000 [1.0000, 1.0000]`** | Model better (CIs separate) |

### Protocol (b): 24h Recency Window Candidate Retrieval
Ranks candidate pool strictly restricted to articles published/clicked within the active 24h recency window.

| Metric @ K | Random Baseline | Popularity Baseline (95% CI) | TF-IDF Profile (95% CI) | Gain vs Popularity | Statistical Verdict |
|---|---|---|---|---|---|
| **HitRate@5** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **NDCG@5** | 0.1667 | 0.3333 [0.0000, 0.6667] | **0.3333 [0.0000, 0.6667]** | **0.0%** | No significant difference (CIs overlap) |
| **Recall@5** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **Precision@5** | 0.0667 | 0.0667 [0.0000, 0.2000] | **0.0667 [0.0000, 0.2000]** | **0.0%** | No significant difference (CIs overlap) |
| **HitRate@10** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **NDCG@10** | 0.1667 | 0.3333 [0.0000, 0.6667] | **0.3333 [0.0000, 0.6667]** | **0.0%** | No significant difference (CIs overlap) |
| **Recall@10** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **Precision@10** | 0.0333 | 0.0333 [0.0000, 0.1000] | **0.0333 [0.0000, 0.1000]** | **0.0%** | No significant difference (CIs overlap) |
| **HitRate@20** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **NDCG@20** | 0.1667 | 0.3333 [0.0000, 0.6667] | **0.3333 [0.0000, 0.6667]** | **0.0%** | No significant difference (CIs overlap) |
| **Recall@20** | 0.3333 | 0.3333 [0.0000, 1.0000] | **0.3333 [0.0000, 1.0000]** | **0.0%** | No significant difference (CIs overlap) |
| **Precision@20** | 0.0167 | 0.0167 [0.0000, 0.0500] | **0.0167 [0.0000, 0.0500]** | **0.0%** | No significant difference (CIs overlap) |

![News Articles Dual Protocol](figures/articles_protocols.png)
```

### Command 5.5
```
(no output)
```

### Command 5.6
```
docs\RESULTS.md:13:| **Articles** | `SYNTHETIC DEMO (not MIND)` | `90b281a` | `b9ac2896` | `42` | Dual protocol: 
Impression ranking + 24h Window retrieval |
docs\RESULTS.md:23:3. **Articles (Content & Recency)**: Evaluated on SYNTHETIC DEMO (not MIND) (9 impressions). 
Impression AUC: 0.9722 [0.9167, 1.0000] vs Popularity 0.5278 [0.2778, 0.7500] (Model better (CIs separate)). 
Impression MRR: 1.0000 [1.0000, 1.0000] vs Popularity 0.6296 [0.4444, 0.8148] (Model better (CIs separate)).
docs\RESULTS.md:88:> **SYNTHETIC DEMO (not MIND):** These evaluation artifacts were generated using synthetic offline 
fixture data (`backend/tests/fixtures/mind/`) because real MIND dataset files were unavailable during automated 
download. **These results are not evidence of real-world quality.** Real benchmark evaluation will be conducted once 
MIND dataset files are placed in `data/raw/mind/`.
docs\RESULTS.md:190:3. **Articles (SYNTHETIC DEMO (not MIND), N=9 impressions):**
```

### Command 6.1
```
backend\tests\integration\test_articles_consistency.py:69:def test_articles_cold_start_consistency_flat_weighting(
backend\tests\integration\test_articles_consistency.py:142:def 
test_articles_cold_start_consistency_real_mind_fixtures() -> None:
backend\tests\integration\test_articles_gate.py:63:def test_gate_r2_no_leakage_impression_time_split() -> None:
backend\tests\integration\test_articles_gate.py:145:def test_gate_r5_cold_start_consistency_and_attribution() -> None:
backend\tests\integration\test_articles_gate.py:196:def test_ritual_1_leaked_test_articles_isolation() -> None:
backend\tests\integration\test_articles_split_leakage.py:15:def 
test_articles_mind_validation_report_and_leakage_passes() -> None:
backend\tests\integration\test_articles_split_leakage.py:61:def test_articles_deliberate_leakage_detected() -> None:
backend\tests\integration\test_determinism.py:58:def test_pipeline_determinism_movies(tmp_path: Path) -> None:
backend\tests\integration\test_determinism.py:64:def test_pipeline_determinism_products(tmp_path: Path) -> None:
backend\tests\integration\test_determinism.py:70:def test_pipeline_determinism_articles(tmp_path: Path) -> None:
backend\tests\integration\test_movies_split_leakage.py:15:def test_movies_100k_chronological_split_leakage_passes() -> 
None:
backend\tests\integration\test_movies_split_leakage.py:51:def test_movies_1m_chronological_split_leakage_passes() -> 
None:
backend\tests\integration\test_movies_split_leakage.py:68:def 
test_movies_split_leakage_detection_on_deliberate_contamination() -> None:
backend\tests\integration\test_phase6_gate.py:286:def test_phase6_gate_break_ritual_1_shuffled_label_near_random(
backend\tests\integration\test_products_gate.py:201:def test_gate_future_temporal_leakage_isolation(
backend\tests\integration\test_products_split_leakage.py:15:def 
test_products_instruments_validation_report_and_leakage_passes() -> None:
backend\tests\integration\test_products_split_leakage.py:61:def test_products_deliberate_leakage_detected() -> None:
backend\tests\integration\test_sar_consistency.py:48:def test_sar_cold_start_consistency_synthetic_ci_flat_weighting(
backend\tests\integration\test_sar_consistency.py:92:def 
test_sar_cold_start_consistency_shipped_config_timedecay_synthetic_ci(
backend\tests\integration\test_sar_consistency.py:198:def 
test_sar_cold_start_consistency_50_known_users_flat_weighting(
backend\tests\integration\test_sar_consistency.py:240:def test_sar_cold_start_consistency_timedecay_affinities(
backend\tests\unit\test_amazon_adapter.py:218:def 
test_amazon_adapter_chronological_split_no_leakage(amazon_fixture_dir: Path) -> None:
backend\tests\unit\test_api_startup.py:46:def test_api_startup_with_corrupt_artifact_dir(
backend\tests\unit\test_artifacts.py:103:def test_schema_version_mismatch_raises_artifact_corrupt_error(
backend\tests\unit\test_artifacts.py:121:def test_missing_file_raises_artifact_corrupt_error(
backend\tests\unit\test_artifacts.py:136:def test_bit_flip_corruption_raises_artifact_corrupt_error(
backend\tests\unit\test_baselines.py:117:def test_cold_start_consistency_popularity(
backend\tests\unit\test_checks.py:85:def test_r2_leakage_check() -> None:
backend\tests\unit\test_config.py:31:    def test_config_hash_deterministic(self):
backend\tests\unit\test_sar.py:127:def test_sar_popular_deterministic(fitted_sar_model: SarModel) -> None:
```

### Command 6.2
```
..................                                                                                               [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
18 passed, 290 deselected, 1 warning in 52.02s
```

### Command 6.3
```
...............                                                                                                  [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
15 passed, 293 deselected, 1 warning in 10.85s
```

### Command 6.4
```
.........                                                                                                        [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
9 passed, 299 deselected, 1 warning in 4.36s
```

### Command 6.5
```
.....                                                                                                            [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 303 deselected, 1 warning in 100.03s (0:01:40)
```

### Command 7.1
```
108
```

### Command 7.2
```
True
```

### Command 7.3 (first 30 and last 30 lines)
```
.F....FFF..FFFF.FFF                                                                                              [100%]
====================================================== FAILURES =======================================================
____________________________________________ test_types_endpoint_contract _____________________________________________

api_client = <starlette.testclient.TestClient object at 0x000001FF99B48590>

    def test_types_endpoint_contract(api_client: TestClient) -> None:
        """Verify /v1/types contract and counts."""
>       resp = api_client.get("/v1/types")
               ^^^^^^^^^^^^^^^^^^^^^

tests\contract\test_api_metadata.py:53: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
..\.venv\Lib\site-packages\httpx\_client.py:1053: in get
    return self.request(
..\.venv\Lib\site-packages\starlette\testclient.py:518: in request
    return super().request(
..\.venv\Lib\site-packages\httpx\_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
..\.venv\Lib\site-packages\httpx\_client.py:928: in send
    raise exc
..\.venv\Lib\site-packages\httpx\_client.py:922: in send
    response.read()
..\.venv\Lib\site-packages\httpx\_models.py:881: in read
    self._content = b"".join(self.iter_bytes())
                    ^^^^^^^^^^^^^^^^^^^^^
..\.venv\Lib\site-packages\httpx\_models.py:897: in iter_bytes
    for raw_bytes in self.iter_raw():
..\.venv\Lib\site-packages\httpx\_models.py:951: in iter_raw
    for raw_stream_bytes in self.stream:
[middle cut]
[2026-10-25 19:49:54] [INFO] [httpx] HTTP Request: GET http://testserver/v1/metrics?type=articles "HTTP/1.1 200 OK"
-------------------------------------------------- Captured log call --------------------------------------------------
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/v1/metrics?type=articles "HTTP/1.1 200 OK"
---------------------------------------------- Captured stdout teardown -----------------------------------------------
[2026-10-25 19:49:54] [INFO] [engine.api.main] Discovery Engine API shutting down.
------------------------------------------------ Captured log teardown ------------------------------------------------
INFO     engine.api.main:main.py:111 Discovery Engine API shutting down.
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================================== short test summary info ===============================================
FAILED tests/contract/test_api_metadata.py::test_types_endpoint_contract - AttributeError: 'ContentTypeSpec' object h...
FAILED tests/contract/test_api_metadata.py::test_item_detail_endpoint_contract[movies] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_item_detail_endpoint_contract[products] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_item_detail_endpoint_contract[articles] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_search_endpoint_contract[movies] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_search_endpoint_contract[products] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_search_endpoint_contract[articles] - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_search_hierarchical_ranking_and_normalization - assert 404 == 200
FAILED tests/contract/test_api_metadata.py::test_metrics_endpoint_contract[movies] - KeyError: 'metrics'
FAILED tests/contract/test_api_metadata.py::test_metrics_endpoint_contract[products] - KeyError: 'metrics'
FAILED tests/contract/test_api_metadata.py::test_metrics_endpoint_contract[articles] - KeyError: 'metrics'
11 failed, 8 passed, 1 warning in 6.89s
Exited with code 1
```
