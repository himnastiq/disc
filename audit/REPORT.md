# Discovery Engine — Phase 1 Audit Report

**Date:** 2026-10-26  
**Repository:** `E:\discover`  
**HEAD:** `50d2fc11856784377158fb639f1de5a45f486424`  
**Scope:** Read-only audit of Phases 0–7 (backend, vendored code, evaluation, training, API, tests, security, performance, docs, git).  
**Plan:** `IMPLEMENTATION_PLAN.md`, read in full including the Session Log.  
**Out of scope:** Phases 8+ (frontend/deployment); not counted as defects.

---

## Executive summary

The backend is functional and unusually well tested for a project of this size: lint, format, strict typing, OpenAPI freshness, vendored-manifest integrity, and the full suite (439 passed, 1 skipped) all pass. The artifact checksum system and API error/security handling are solid, and most plan tasks are genuinely implemented.

However, the project is **not ready to stand behind its published data-integrity and conformance claims**. The audit found:

- **4 HIGH** issues: arbitrary `eval()` on downloaded Amazon data; test-set contamination in the Amazon item cap; MIND history backdating that can leak future clicks; and a CONFORMANCE document that certifies PASS/0 FAIL with false or missing evidence.
- **11 MEDIUM** issues: invalid tuning threshold scoring, several articles-evaluation integrity/reproducibility defects, serving-config reconstruction gaps, non-atomic artifact writes, no dependency lock, CI excluding the acceptance tests, and a capped `total_matches` contract bug.
- **5 LOW** issues: documentation errors, private-field coupling, path containment, and runtime asserts.

**Verdict:** PASS WITH MAJOR CAVEATS for the implemented backend; **FAIL** for the claim that R2/R8/R10 are fully conformant and for P5.3 acceptance. No CRITICAL finding was assigned because the `eval()` exploit requires an attacker to influence the dataset source; under a hostile-network threat model F-001 should be treated as CRITICAL.

### Severity counts

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 11 |
| LOW | 5 |
| **TOTAL** | **20** |

These counts match `audit/FINDINGS.json` exactly.

### Severity rubric used

- **CRITICAL:** directly exploitable remote code execution/data destruction with no preconditions.
- **HIGH:** security or data-integrity defect that can change published results, block correct serving, or materially mislead reviewers.
- **MEDIUM:** material correctness/reproducibility defect with bounded or latent impact.
- **LOW:** maintainability, documentation, or minor contract issue.

---

## Top 5 risks

1. **F-001 — `eval()` on untrusted Amazon data (HIGH).** A downloaded line can execute arbitrary Python during data prep/training. No checksum protects the download. Fix before any network-connected training run.
2. **F-002 + F-003 — test leakage in two adapters (HIGH).** Amazon’s item cap uses test interactions; MIND backdates later history into train and globally dedupes. Both can inflate published metrics and violate R2.
3. **F-004 — false conformance certification (HIGH).** `docs/CONFORMANCE.md` claims R2/R8/R10 PASS and 0 FAIL while P5.3 is unchecked, R8 numbers contradict generated RESULTS, and R10 cites files/tests that do not exist.
4. **Evaluation integrity cluster (MEDIUM).** Tuning threshold trials use fixed labels (F-006); articles evaluation can fall back to train impressions (F-007), uses process-randomized `hash()` for Random (F-008), omits cold-start exclusions (F-009), and hardcodes `leakage_check_passed: true` (F-015).
5. **Reproducibility/operations cluster (MEDIUM).** No lock file (F-012), CI excludes 42 real-data tests (F-013), artifact writes are non-atomic (F-011), and serving-config reconstruction ignores two tuned params (F-010).

---

## Findings

| ID | Severity | Area | Finding | Key evidence |
|---|---|---|---|---|
| F-001 | HIGH | ADAP/SEC | Untrusted Amazon data executed with `eval()` | `amazon.py:51`; no checksum in `fetch_data.py:98-110` |
| F-002 | HIGH | ADAP/TRAIN | Amazon item cap computed before split using test interactions | `amazon.py:243-247`; split at `train.py:169-175` |
| F-003 | HIGH | ADAP/EVAL | MIND backdates later history and globally dedupes, leaking future clicks | `mind.py:312`, `mind.py:355-359`; P5.3 unchecked at plan:420 |
| F-004 | HIGH | DOCS | CONFORMANCE certifies PASS/0 FAIL with false or missing evidence | `CONFORMANCE.md:75,81,83,90-97`; `RESULTS.md:214,228` |
| F-005 | MEDIUM | ADAP | Product interactions omit required `positive` field | `amazon.py:138-144` vs `schema.py:29` |
| F-006 | MEDIUM | EVAL/TRAIN | Tuning threshold trials scored against fixed positive labels | `tuning.py:205-209`; labels from `movielens.py:222` |
| F-007 | MEDIUM | EVAL | Articles impression eval falls back to all impressions, including train | `articles_eval.py:431-433` |
| F-008 | MEDIUM | EVAL | Articles Random baseline uses process-randomized `hash()` | `articles_eval.py:116-122`; three processes differ |
| F-009 | MEDIUM | EVAL | Articles cold-start curve omits full-history exclusions; silently drops failures | `articles_eval.py:492-497,505-506` vs `harness.py:260-268` |
| F-010 | MEDIUM | CORE/TRAIN | Serving config reconstruction ignores `similarity_type`/`timedecay_formula` | `config.py:164-176`; `train.py:190-196` |
| F-011 | MEDIUM | CORE/TRAIN | Artifact save is not atomic | `artifacts.py:113-118,121-122,184` |
| F-012 | MEDIUM | REPO/SEC | Dependency versions are not locked | `pyproject.toml:11-46`; no lock; `.gitignore:70-71` false claim |
| F-013 | MEDIUM | TEST | CI deselects 42 real-data tests incl. P5.3/P6.3 | `ci.yml:54`; `test_articles_split_leakage.py:13`; `test_determinism.py:21` |
| F-014 | MEDIUM | API | Search `total_matches` is capped by `limit` | `metadata.py:247,252`; 59 matches reported as 1 at limit=1 |
| F-015 | MEDIUM | EVAL | Articles metrics hardcode `leakage_check_passed: true` | `articles_eval.py:552-560` |
| F-016 | LOW | DOCS | Production MIND command points to nonexistent script | `DATASETS.md:72` vs `Makefile:29` |
| F-017 | LOW | DOCS | ARCHITECTURE claims interactions are split-flagged | `ARCHITECTURE.md:37`; no split column in parquet |
| F-018 | LOW | CORE | Manifest verification joins unvalidated relative paths | `artifacts.py:201-203` |
| F-019 | LOW | API | Item detail reaches into private `ItemSearchIndex._entries` | `metadata.py:286-294` |
| F-020 | LOW | QUAL | Runtime asserts in library code disappear under `-O` | `amazon.py:261,267`; `mind.py:392,398`; `tfidf.py:444` |

Detailed evidence, impact, and recommendations are in `FINDINGS.json`; per-area narratives are in `audit/areas/*.md`.

---

## Area verdicts

| Area | Verdict | Findings |
|---|---|---|
| REPO | PASS WITH FINDINGS | F-012 |
| VEND | PASS | none |
| CORE | PASS WITH FINDINGS | F-010, F-011, F-018 |
| ADAP | FAIL WITH FINDINGS | F-001, F-002, F-003, F-005 |
| MODL | PASS | none direct (F-008/F-010 adjacent) |
| EVAL | FAIL WITH FINDINGS | F-006, F-007, F-008, F-009, F-015 |
| TRAIN | PASS WITH FINDINGS | F-002, F-006, F-010, F-011 |
| API | PASS WITH FINDINGS | F-014, F-019 |
| TEST | PASS WITH FINDINGS | F-013 |
| SEC | FAIL WITH FINDINGS | F-001, F-012, F-013 |
| PERF | PASS WITH CAVEAT | docs overclaim F-004; not independently rerun |
| DOCS | FAIL WITH FINDINGS | F-004, F-016, F-017 |
| QUAL | PASS WITH FINDINGS | F-019, F-020; F-001 hot spot |
| GIT | PASS | none |

---

## Plan compliance

Full table: `audit/02_PLAN_COMPLIANCE.md`.

**87 tasks audited: 76 PASS, 8 PARTIAL, 2 FAIL, 1 BLOCKED.**

- **FAIL:** P0.3 (no lock file), P5.3 (real-data R2 acceptance not met; plan marker still `[ ]`).
- **BLOCKED:** P5.1 (real MIND files unavailable; manual download documented).
- **PARTIAL:** P0.8 (no checksums), P3.8 (tuning threshold), P4.2 (cap/positive), P5.8 (articles evaluation), P5.12 (phase gate accepted on synthetic), P6.3 (determinism not CI-enforced), P6.5 (product schema), P7.3 (`total_matches`).

The plan’s own dashboard/status is therefore not a reliable completion signal for these items.

---

## Hardcoded sweep

Full triage: `audit/03_HARDCODED.md`. Raw scan: `audit/hardcoded_scan_raw.txt` (1,190 lines, 14 categories).

- No production secrets/credentials found; the only `SECRET_LIKE` hit is a test literal.
- One genuine unsafe call: `amazon.py:51` `eval` (F-001).
- Two problematic exception swallows: `config.py:175-176` (F-010) and `articles_eval.py:505-506` (F-009).
- 658 magic-number hits are mostly thresholds/tests; notable hardcoded evaluation caps at `train.py:247` and the search rank offset at `search.py:55`.
- 24 broad excepts, 47 suppressions, 16 runtime asserts, 14 naive-time calls — triaged; no additional high-severity issue beyond the above.

---

## Dynamic verification

Full record: `audit/04_DYNAMIC_CHECKS.md`.

- `ruff check`, `ruff format --check`, `mypy engine/ api/` → PASS.
- Full pytest → **439 passed, 1 skipped, 1 warning in 836.64 s**.
- CI-equivalent (`-m "not real_data"`) → **397 passed, 1 skipped, 42 deselected**.
- OpenAPI check → PASS; vendored manifest → PASS (22 files); `make_results --check` → PASS.
- Artifact delete/byte-flip/schema-version tamper → all detected as `ArtifactCorruptError`.
- API probes: k bounds 422, unknown type/user/item 404, cold-start 200/201/dupes correct, exclude removes item, k-prefix stable, metrics byte-equal, API-key 401/401/200.
- Reproduced F-014 (59 matches → `total_matches: 1` at limit=1) and F-008 (three different hashes across processes).

**Not run / blocked:** `pip-audit` (PyPI timeout), full 500-request benchmark, clean-room rebuild (~7.5 min), schemathesis, upstream vendored diff, real MIND data, coverage report. See the dynamic-check file for reasons.

---

## Open questions (6)

1. **F-001 threat model:** Is Amazon data ever fetched over an untrusted network/proxy in the intended deployment? If yes, should F-001 be raised to CRITICAL?
2. **Products schema:** Is the missing `positive` column intentional (derive from signal) or an oversight? This determines whether F-005 is a schema bug or a documented exception.
3. **P5.3 acceptance:** Is a synthetic-fixture R2 test acceptable, or does “R2 test on real data” strictly require real MIND files? The plan marker and Session Log disagree.
4. **Articles evaluation status:** Are articles metrics explicitly demo-only and therefore exempt from P6.6 CIs and full protocol parity, or should they be made comparable to movies/products?
5. **Artifact durability:** Is atomic artifact replacement a deployment requirement, or is a failed training run expected to be rerun manually?
6. **`total_matches` contract:** Should the API return the pre-limit total (recommended) or rename the field to `returned_matches`? The current schema says “Total number of matches”.

---

## Not covered

- **Real MIND data / P5.3:** unavailable; the central leakage claim could not be tested on real data.
- **Dependency vulnerabilities:** `pip-audit` failed on network timeout; status unknown.
- **Vendored upstream provenance:** no independent diff against Recommenders 1.2.1 (no network/package).
- **Full performance benchmark:** not rerun; relied on generated `docs/RESULTS.md`.
- **Clean-room rebuild:** not rerun (opt-in, ~7.5 min).
- **Schemathesis:** not installed/run; Hypothesis fuzzing ran in the suite.
- **Frontend/Phases 8+:** out of scope.
- **Coverage percentage:** no coverage gate/report configured.
- **Historical git secret scan:** current tree is clean; history not exhaustively scanned.

---

## Read-only integrity

`snapshot_before.json` was reused from the start of the audit. After all audit files were written, `python audit/scratch/snapshot.py after` hashed 276 tracked/artifact/data files and reported:

```text
CHANGED FILES: none
```

`git status --short` shows only the pre-existing untracked `AUDIT_PROMPT.md` and the new untracked `audit/` directory. No tracked file, artifact, dataset, plan marker, or project source was modified. No commit was made. **Integrity check: PASS.**

---

## Environment

Windows, Python 3.11.7 (64-bit). Key versions: numpy 2.4.6, pandas 3.1.0, scipy 1.17.1, scikit-learn 1.9.1, pyarrow 26.0.0, pydantic 2.14.1, PyYAML 6.0.3, fastapi 0.162.0, starlette 1.9.0, uvicorn 0.54.0, joblib 1.6.0, pytest 9.1.1, hypothesis 6.170.9, httpx 0.28.1, ruff 0.17.2, mypy 2.4.0, pip-audit 2.10.1, matplotlib 3.11.2. `recommenders` is not installed.
