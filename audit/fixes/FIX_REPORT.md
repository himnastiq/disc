# Phase 2 Fix Implementation Report: Discovery Engine

**Branch:** `fix/audit-findings`  
**Base Commit:** `50d2fc11856784377158fb639f1de5a45f486424`  
**Scope:** `SESSION_SCOPE: ALL`  
**Date:** 2026-10-27  
**Operating Environment:** Windows 11 (x64), PowerShell, Python 3.11.7 (`.venv\Scripts\python.exe`)

---

## 1. Executive Summary

Phase 2 remediation resolved audited findings from `audit/REPORT.md` and `audit/FINDINGS.json` with minimal, evidence-driven root-cause fixes, failing test proofs before changes, and passing verification after changes.

### Status Counts
| Status | Critical | High | Medium | Low | Total |
|---|---|---|---|---|---|
| **FIXED** | 0 | 4 | 9 | 5 | **18** |
| **BLOCKED-ON-HUMAN** | 0 | 0 | 2 | 0 | **2** |
| **PARTIAL** | 0 | 0 | 0 | 0 | **0** |
| **NOT-REPRODUCIBLE** | 0 | 0 | 0 | 0 | **0** |
| **WONT-FIX** | 0 | 0 | 0 | 0 | **0** |
| **Total Audited** | **0** | **4** | **11** | **5** | **20** |

### Test, Lint, and Type Verification Before vs. After
| Verification Gate | Baseline (Audit) | Post-Fix (Phase 2) | Delta / Outcome |
|---|---|---|---|
| **Fast Test Suite** (`not real_data`) | 397 passed, 1 skipped | 416 passed, 1 skipped | **+19 passing tests**, 0 new skips, 0 failures |
| **Extended Test Suite** (with real data) | 439 passed, 1 skipped | 458 passed, 1 skipped | **+19 passing tests**, 0 new skips, 0 failures |
| **Ruff Linter** (`ruff check backend/`) | 0 errors | 0 errors | Clean |
| **Ruff Formatter** (`ruff format --check backend/`) | 0 errors | 0 errors | Clean |
| **Mypy Type-Checker** (`backend/engine backend/api`) | 0 errors (45 files) | 0 errors (45 files) | Clean strict typing |
| **OpenAPI Export Check** (`scripts/export_openapi.py`) | Pass | Pass | Clean |
| **Import Purity** (TF/PySpark/Torch/Cornac) | None imported | None imported | Zero deep learning imports |

---

## 2. Table of Findings and Remediation Records

| Finding ID | Title | Severity | Status | Commit | Proofs & Tests Added |
|---|---|---|---|---|---|
| **F-001** | Untrusted Amazon data executed with `eval()` | HIGH | FIXED | `eb731d3` | `test_parse_dict_line_rejects_arbitrary_code_execution`, SHA-256 download checks in `fetch_data.py` |
| **F-002** | Amazon item cap computed before split using test interactions | HIGH | FIXED | `d542a9e` | `test_amazon_adapter_item_cap_does_not_leak_test_interactions`, `test_amazon_adapter_item_cap_perturbation_invariance` |
| **F-003** | MIND history backdating and global dedupe leak future clicks | HIGH | FIXED | `b193e92` | `test_mind_adapter_subsequent_history_not_backdated_before_earlier_sessions`, `test_articles_mind_validation_report_and_leakage_passes` |
| **F-004** | CONFORMANCE certifies PASS/0 FAIL with false or missing evidence | HIGH | FIXED | `1f4e5fc` | Alignment with measured p95/RSS metrics in `RESULTS.md`, corrected attribution links, `hmac.compare_digest` |
| **F-005** | Products interactions parquet omits `positive` column | MEDIUM | BLOCKED-ON-HUMAN | — | Awaiting human decision on Author Decision Q2 (see Section 5) |
| **F-006** | SAR hyperparameter tuning scores trials against fixed labels | MEDIUM | FIXED | `42a84cf` | `test_tuning_validation_positives_derived_from_trial_threshold` in `test_tuning.py` |
| **F-007** | Articles evaluation falls back to train impressions on missing post-train | MEDIUM | FIXED | `164cb76` | `test_articles_eval_rejects_train_impression_fallback` in `test_articles_eval.py` |
| **F-008** | Articles Random baseline uses nondeterministic built-in `hash()` | MEDIUM | FIXED | `834faef` | `test_articles_random_baseline_deterministic_across_processes` in `test_articles_eval.py` |
| **F-009** | Articles cold-start curve evaluates on seen training items | MEDIUM | FIXED | `d1ec719` | `test_articles_cold_start_curve_protocol_passes_exclude_ids` in `test_articles_eval.py` |
| **F-010** | Serving config ignores tuned `similarity_type` and `timedecay_formula` | MEDIUM | FIXED | `58c8a43`<br>`749e93a` | `test_resolve_serving_config_restores_tuned_hyperparameters`, `test_resolve_serving_config_corrupt_tuning_json` |
| **F-011** | Artifact writes are non-atomic; crash leaves corrupt directory | MEDIUM | FIXED | `4f7405e`<br>`91a493f` | `test_atomic_artifact_save_failure_leaves_target_untouched`, auxiliary model folder staging protection |
| **F-012** | pyproject.toml has unpinned dependencies and no lockfile committed | MEDIUM | BLOCKED-ON-HUMAN | — | Offline sandbox cannot resolve PyPI dependencies; exact command provided in Section 5 |
| **F-013** | CI excludes 42 real-data tests including split leakage and determinism | MEDIUM | FIXED | `33cb8f3` | `test_articles_mind_fixture_split_leakage`, `test_pipeline_determinism_toy` added to CI default suite |
| **F-014** | `/items/search` reports `total_matches` capped by `limit` | MEDIUM | FIXED | `d63f3a4` | `test_search_total_matches_independent_of_limit` in `test_api_metadata.py` |
| **F-015** | Articles evaluation hardcodes `leakage_check_passed: True` | MEDIUM | FIXED | `f2e7607` | `test_articles_eval_detects_real_split_leakage` in `test_articles_eval.py` |
| **F-016** | DATASETS.md points to non-existent `scripts/train_articles.py` | LOW | FIXED | `94a60cd` | Updated command in `docs/DATASETS.md:72` to `python -m engine.train --type articles` |
| **F-017** | ARCHITECTURE.md falsely claims interactions are flagged with split | LOW | FIXED | `a26f72e` | Clarified dynamic split generation in `docs/ARCHITECTURE.md:37` |
| **F-018** | Artifact manifest path traversal vulnerability | LOW | FIXED | `fca869f` | `test_verify_artifacts_rejects_path_traversal` in `test_artifacts.py` |
| **F-019** | `/items/{id}` does linear scan of private `_entries` | LOW | FIXED | `c1f2a0c` | `test_item_detail_does_not_access_private_entries`, public O(1) lookup in `ItemSearchIndex` |
| **F-020** | Production adapters and models rely on bare `assert` | LOW | FIXED | `cc57111`<br>`03440a9` | `test_amazon_adapter_validates_fit_with_runtime_error`, `test_mind_adapter_validates_fit_with_runtime_error`, `test_tfidf_model_validates_fit_with_runtime_error` |

---

## 3. Pipeline Metrics Before vs. After (Pipeline Files)

All metrics below are extracted directly from `artifacts/<type>/metrics.json` and compared against the baseline snapshot in `audit/fixes/metrics_before/<type>/metrics.json`. Figures and `docs/RESULTS.md` were regenerated using `tools/make_results.py`.

### Movies Pipeline (`artifacts/movies/metrics.json`)
| Model | Metric | Before Fix | After Fix | Notes |
|---|---|---|---|---|
| **SAR** | NDCG@10 | 0.05922 | **0.10208** | Evaluated on clean temporal split |
| **SAR** | MAP@10 | 0.02801 | **0.05524** | Consistent ranking improvement |
| **SAR** | Recall@10 | 0.06451 | **0.12565** | |
| **SAR** | Hit Rate@10 | 0.28259 | **0.38225** | |
| **Popularity** | NDCG@10 | 0.05464 | **0.07264** | Model strictly beats Popularity |
| **Random** | NDCG@10 | 0.00417 | **0.00454** | Sanity ordering: Random < Popularity < Model |

### Products Pipeline (`artifacts/products/metrics.json`)
| Model | Metric | Before Fix | After Fix | Notes |
|---|---|---|---|---|
| **SAR** | NDCG@10 | 0.04533 | **0.06871** | Item cap strictly train-only (F-002 fixed) |
| **SAR** | MAP@10 | 0.03390 | **0.05038** | Zero test rows leaked into similarity pool |
| **SAR** | Recall@10 | 0.07993 | **0.12739** | |
| **SAR** | Hit Rate@10 | 0.08605 | **0.13093** | |
| **Popularity** | NDCG@10 | 0.01630 | **0.04705** | Model strictly beats Popularity |
| **Random** | NDCG@10 | 0.00036 | **0.00467** | Sanity ordering: Random < Popularity < Model |

### Articles Pipeline (`artifacts/articles/metrics.json`)
*Key finding: The Phase 1 audit revealed that previous articles metrics were artificially inflated by history backdating (`F-003`) and train impression fallback (`F-007`). Remediating both yields genuine, uncorrupted evaluation numbers.*

#### Impression Ranking Protocol
| Model | Metric | Before Fix (Inflated) | After Fix (Verified) | Root Cause of Change |
|---|---|---|---|---|
| **Evaluated Impressions** | Count | 9 | **100** | Full post-train test split evaluated |
| **TF-IDF Profile** | AUC | 0.9722 | **0.5544** | Honest test-time ranking; no backdated clicks |
| **TF-IDF Profile** | MRR | 1.0000 | **0.3148** | Realistic ranking on unseen impressions |
| **TF-IDF Profile** | nDCG@5 | 1.0000 | **0.2801** | |
| **TF-IDF Profile** | nDCG@10 | 1.0000 | **0.3412** | Model strictly beats Popularity (0.2698) |
| **Popularity** | AUC | 0.5278 | **0.4689** | |
| **Random** | AUC | 0.2778 | **0.5397** | Seeded with stable SHA-256 (F-008) |

#### Retrieval Protocol (Candidate Pool Ranking)
| Model | Metric | Before Fix (Inflated) | After Fix (Verified) | Notes |
|---|---|---|---|---|
| **TF-IDF Profile** | NDCG@10 | 0.33333 | **0.00631** | Train impression fallback eliminated (F-007) |
| **TF-IDF Profile** | Recall@10 | 0.33333 | **0.02000** | Strict test window positives only |
| **Popularity** | NDCG@10 | 0.33333 | **0.00000** | |
| **Random** | NDCG@10 | 0.16667 | **0.00000** | |

---

## 4. Architecture Decision Records (`docs/DECISIONS.md`)

The following decisions were documented in `docs/DECISIONS.md`:
- **`D-020`**: *Post-split train-only item cap for Amazon products adapter (`F-002`).* Moved popularity cap strictly into `AmazonProductsAdapter.split()` on `train_df`, ensuring zero test rows influence item vocabulary.
- **`D-021`**: *Strict chronological anchoring and deduplication of MIND history (`F-003`).* Anchored newly observed history clicks between previous session timestamp `prev_ts` and current impression `imp_ts`; preserved earliest interactions via `keep="first"`.
- **`D-022`**: *Atomic artifact persistence with pre-population and rollback protection (`F-011`).* Staged in temporary directories, copied pre-staged auxiliary subfolders (`model/`), and swapped atomically with rollback handling.
- **`D-023`**: *Decoupling search total match count from pagination limit in `ItemSearchIndex` (`F-014`, `F-019`).* Return candidate match count prior to slicing; exposed public O(1) lookups.
- **`D-024`**: *CI test isolation for split leakage and determinism without external datasets (`F-013`).* Decoupled fixture split leakage and determinism tests from `real_data` marker so pull requests verify core invariants offline.

---

## 5. Items Blocked on Human Action

Per Rule 1.1, Rule 1.8, and prompt Section 0, the following two findings are marked `BLOCKED-ON-HUMAN` without guessing author intent:

### 1. `F-005`: Products interactions parquet omits `positive` column
- **Context:** `artifacts/products/interactions.parquet` contains `["user_id", "item_id", "signal", "timestamp"]` but omits the `positive` boolean column present in movies and articles interactions.
- **Author Decision Q2:** *"Products schema: missing positive column intentional or oversight?"*
- **Action Required:**
  - If **intentional**: approve updating `engine/schema.py` or configuration to permit optional `positive` columns.
  - If **oversight**: approve adding `positive = (signal >= positive_threshold)` in `AmazonProductsAdapter.prepare()` and regenerating products interactions parquet.

### 2. `F-012`: Lockfile generation (`uv.lock`)
- **Context:** `backend/pyproject.toml` specifies lower version bounds; `uv lock` requires external network connectivity to query PyPI metadata and compute resolved pins.
- **Action Required:** On a machine with active network access, run:
  ```powershell
  cd backend
  uv lock
  git add uv.lock
  git commit -m "FIX F-012: commit resolved uv.lock dependency lockfile"
  ```

---

## 6. Summary of New Observations (`audit/fixes/NEW_OBSERVATIONS.md`)

- **`backend/engine/artifacts.py:110` & `backend/engine/train.py:180` (MEDIUM):** `primary_model.save()` writes into `artifacts/<type>/model/` before `save_artifacts()` is called. In atomic staging, pre-existing subfolders must be cloned into `.tmp_*` prior to atomic swap.
- **`backend/api/routes/metadata.py:286` (MEDIUM):** Private `_entries` linear scan in `/items/{item_id}` could raise `TypeError` if search index was unbuilt. Remediated in F-019 via public O(1) dictionary lookups.
- **`backend/tests/unit/test_config.py:101` (LOW):** Unit test fixture expected `trial["validation_metrics"]["eval_users"]` instead of canonical `trial["evaluated_users"]`.
- **`backend/engine/articles_eval.py:425` (LOW):** Missing explicit `import logging` caused `NameError` on leakage failure logging.
- **`backend/discovery/datasets/mind.py:280` (LOW):** Dict lookup pattern drift flagged by Ruff `SIM910`.

---

## 7. Residual Risks

1. **Schema divergence in `interactions.parquet`:** Products artifacts lack the boolean `positive` column pending Author Decision Q2 (`F-005`).
2. **Unpinned environment lockfile:** Dependency lockfile is not committed pending manual `uv lock` execution with network access (`F-012`).
3. **MIND full dataset acquisition:** Automated anonymous download of raw MIND news files from Microsoft Azure remains restricted (HTTP 409/401); operators must manually place files in `data/raw/mind/` per `docs/DATASETS.md` instructions.

---

## 8. Audit Coverage Gaps

- **Exhaustive Git Secret Scan:** Closed. Executed regex pattern scanner across full git history (`git log -p --all`). Zero leaked credentials or private keys discovered (only test mock tokens and environment lookups).
- **CI Test Isolation for Split Leakage:** Closed. Ported fixture split leakage test (`test_articles_mind_fixture_split_leakage`) and toy pipeline determinism (`test_pipeline_determinism_toy`) into default CI suite.
- **P5.3 Real-Data Acceptance:** Closed. Verified `test_articles_mind_validation_report_and_leakage_passes` executes cleanly on real MIND interactions in 35.76s.
- **Dependency Vulnerability Scan (`pip-audit`):** Open. Blocked by disabled network access in the sandbox environment.
- **OpenAPI Fuzzing (`schemathesis`):** Open. Optional tool not installed in dev environment.
- **Vendored Upstream Diff:** Open. Requires network access to clone upstream Recommenders repository.

---

## 9. Plan and Bookkeeping Updates

- **Plan Markers Updated in `IMPLEMENTATION_PLAN.md`:**
  - `P5.3` ticked `[x]` (acceptance criteria satisfied and verified on real MIND data).
  - `P0.3` set to `[!]` (blocked on human running `uv lock`).
  - `P4.2` set to `[~]` (item cap leakage fixed, positive schema pending Q2).
  - `P6.5` set to `[~]` (products positive schema pending Q2).
- **Progress Dashboard:** Updated to **83/129 tasks done** (idempotent run verified via `tools/progress.py`).
- **Session Log:** Appended Session 27 entry covering Phase 2 remediations, findings F-001..F-020, decisions D-020..D-024, and break-your-own-fix checks.

---

## 10. Suggested Commit Review Order

To review the branch `fix/audit-findings` from base commit `50d2fc1`, inspect commits in chronological sequence:

1. `eb731d3`: `FIX F-001: replace eval with safe parser and verify download checksums`
2. `d542a9e`: `FIX F-002: enforce post-split train-only item cap in amazon adapter`
3. `b193e92`: `FIX F-003: anchor mind history timestamps monotonically without future leakage`
4. `42a84cf`: `FIX F-006: derive tuning validation positives dynamically from trial threshold`
5. `164cb76`: `FIX F-007: eliminate train impression fallback in articles evaluation`
6. `834faef`: `FIX F-008: make articles random baseline deterministic across processes via sha256`
7. `d1ec719`: `FIX F-009: exclude seen training items from articles cold-start curve evaluation`
8. `58c8a43`: `FIX F-010: reconstruct tuned similarity type and timedecay formula in serving config`
9. `4f7405e`: `FIX F-011: implement atomic stage and swap directory writes for artifacts`
10. `91a493f`: `FIX F-011: preserve pre-staged auxiliary model artifacts during atomic swap`
11. `fca869f`: `FIX F-018: reject path traversal and absolute paths in artifact manifest verification`
12. `cc57111`: `FIX F-020: replace bare assert with runtime error in adapters and tfidf model`
13. `03440a9`: `FIX F-020: add unit tests asserting runtime error on unfitted predict calls`
14. `d63f3a4`: `FIX F-014: decouple search total matches count from pagination limit`
15. `c1f2a0c`: `FIX F-019: replace private entries scan in item detail with public o1 lookup`
16. `f2e7607`: `FIX F-015: replace hardcoded leakage flag with computed verification in articles eval`
17. `33cb8f3`: `FIX F-013: run fixture split leakage and determinism tests in default ci suite`
18. `94a60cd`: `FIX F-016: correct articles training command in DATASETS.md`
19. `a26f72e`: `FIX F-017: clarify interaction split computation in ARCHITECTURE.md`
20. `1f4e5fc`: `FIX F-004: align CONFORMANCE.md with verified pipeline metrics and correct links`
21. `e31b360`: `FIX GOLDEN: regenerate RESULTS.md and evaluation figures via tools/make_results.py`
22. `4f3133b`: `FIX BOOKKEEPING: update plan markers, progress dashboard, and decision records for Phase 2 remediations`
23. `749e93a`: `FIX F-010: align resolve_serving_config time_decay_coefficient update with train.py`
