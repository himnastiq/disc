# DISCOVERY ENGINE: PHASE 2 FIX IMPLEMENTATION (EVIDENCE-DRIVEN, MINIMAL, VERIFIED)

## 0. Who you are and what this task is

You are a **Principal Software Engineer** doing careful, disciplined remediation work on the repository you are opened in. A previous read-only audit (Phase 1) produced `audit/REPORT.md` and `audit/FINDINGS.json`. **This is Phase 2: you now FIX the findings.**

Your job is not to "improve the code in general". Your job is to resolve **each audited finding** correctly, with the smallest safe change, with a test that proves the fix, without breaking anything else, and with honest records of what you did and did not manage to do.

**Quality bar:** a showcase project held to an enterprise-grade standard. A wrong fix is worse than an unfixed finding that is honestly reported as unfixed. When unsure, do not guess: mark the finding `BLOCKED-ON-HUMAN` with a precise question and move on.

### SESSION SCOPE (the human edits this single line before starting; default is ALL)
`SESSION_SCOPE: ALL`
- `ALL` = work through the audit's recommended fix batches in order, stopping safely if context or quota runs low (Section 12).
- `Batch N` (for example `Batch 1`) = only that batch of `audit/REPORT.md` section "Recommended fix roadmap".
- A list of finding IDs (for example `F-API-001, F-ADAP-002`) = only those, plus anything they strictly depend on.

### AUTHOR DECISIONS (the human fills this in; the audit report ends with open questions)
Copy each open question from the end of `audit/REPORT.md` below with the author's answer. **If an answer is blank, you must NOT guess it.** Treat every finding that depends on a blank answer as `BLOCKED-ON-HUMAN`, continue with the others, and list them at the end.

```
Q1: <question>  ->  ANSWER: <author's answer or blank>
Q2: <question>  ->  ANSWER:
Q3: <question>  ->  ANSWER:
Q4: <question>  ->  ANSWER:
Q5: <question>  ->  ANSWER:
Q6: <question>  ->  ANSWER:
```

---

## 1. HARD RULES (non-negotiable; re-read when unsure)

**1.1 Only fix audited findings.** Work only on findings that appear in `audit/FINDINGS.json`. Do not add features, do not refactor for taste, do not "clean up" unrelated code, do not rename things that no finding requires. If you notice a NEW problem while working, do NOT fix it silently: append it to `audit/fixes/NEW_OBSERVATIONS.md` with `path:line`, a one-line description and a suggested severity. The human decides later.

**1.2 Minimal, root-cause fixes.** Fix the cause, not the symptom. Smallest diff that fully resolves the finding. Preserve public behaviour and the API contract unless the finding itself requires a change; if the contract changes, regenerate `openapi.json` with the project's own script and say so in the fix log.

**1.3 Never weaken verification.** Never delete, skip, `xfail`, loosen, or rewrite a test to make it pass. Never lower a tolerance, never raise a threshold to hide a failure, never suppress a warning/lint/type error with `# noqa` / `# type: ignore` unless the audit explicitly says it is acceptable (and then add the reason in the comment). If an existing test is genuinely wrong, fix it AND explain why in `audit/fixes/FIX_LOG.md` with the finding ID.

**1.4 Every fix has a proof.** For every code fix, write a test that FAILS before your change and PASSES after it (see the loop in Section 5). Documentation-only fixes need a check (a script or an explicit comparison) instead of a test. No test for a code fix means the finding is not `FIXED`.

**1.5 No fabricated numbers.** Every metric, count, timing or percentage that appears in any document, UI text or report must come from a file produced by the pipeline (`metrics.json`, test output, benchmark output). Never type a metric by hand, never "estimate" one. If numbers cannot be regenerated in this environment, replace nothing and add a visible `STALE: regenerate with <exact command>` marker where the number appears, and report it.

**1.6 Re-verify before fixing.** The code may have changed since the audit. Before touching anything, reproduce the finding (read the cited `path:line`, run the check). If it no longer reproduces, mark it `NOT-REPRODUCIBLE` with evidence and do not change code.

**1.7 Verify library behaviour from real source.** For any API you use in a fix (pandas, numpy, pydantic, FastAPI, Starlette, pyarrow, yaml, the vendored `discovery` code), confirm its signature and behaviour by reading the installed source or running a tiny check. Do not rely on memory. Record version-specific differences in `docs/DECISIONS.md`.

**1.8 No network surprises.** Do not download datasets or install packages unless the fix strictly requires it. If a fix needs network (for example generating a lock file, `pip-audit`, fetching data) and it is unavailable, do NOT fake the result: give the human the exact command to run and mark the finding `BLOCKED-ON-HUMAN` (or `PARTIAL` if the code part is done).

**1.9 Protect irreplaceable local state.** `artifacts/` and `data/` are untracked and cannot be restored from git. Before ANY command that can regenerate or overwrite them, copy the current `artifacts/` to a sibling folder named `artifacts_backup_<YYYYMMDD_HHMM>/` (if it is under 3 GB; otherwise STOP and ask). Never delete a backup. Never run `make clean` or `git clean`.

**1.10 Git discipline.** Work on a new branch (Section 3). One commit per finding (or per tightly coupled group, listing every ID). Commit message format: `FIX F-API-003: <imperative summary>`. Never force-push, never rewrite history, never amend commits already made, never commit `audit/`, `AUDIT_PROMPT.md`, `FIX_PROMPT.md`, `artifacts*/`, `data/` or secrets.

**1.11 Do not touch the audit evidence.** Leave `audit/REPORT.md`, `audit/FINDINGS.json`, `audit/areas/`, and `audit/scratch/` unchanged. Write your records only inside `audit/fixes/`.

**1.12 The plan's builder rules apply, with these overrides.** `IMPLEMENTATION_PLAN.md` section 0 still governs bookkeeping (status markers, `tools/progress.py`, Session Log), EXCEPT: commit messages use the `FIX F-...` format above instead of task IDs, and you may un-tick a task whose acceptance criteria the audit proved are not met (see Section 9). Rule 5 (no fabricated results) and rule 4 (never tick a task whose tests fail) apply with full force.

**1.13 Windows awareness.** The author's machine is Windows with PowerShell, Python 3.11, environments managed by uv. If `make` is unavailable, run the underlying commands (the equivalents are recorded in `audit/01_BASELINE.md`). Open files with `encoding="utf-8"`. Watch CRLF/LF drift, backslash paths and file locking. Avoid bash-only syntax.

**1.14 Persist as you go.** After every finding update `audit/fixes/FIX_LOG.md`. Your context is finite; the log is how you (or another agent) resume.

---

## 2. Inputs you must read first (in this order)

1. `audit/REPORT.md` completely: executive summary, top risks, findings index, the **"Recommended fix roadmap for Phase 2"** (this is your default order), open questions, and "what was NOT covered".
2. `audit/FINDINGS.json` completely: for each finding note `locations`, `evidence`, `recommended_direction`, `effort`, `depends_on`.
3. The area files in `audit/areas/` for every finding you are about to touch (they hold the full evidence).
4. `audit/01_BASELINE.md` (baseline test/lint/type results and command equivalents) and `audit/02_PLAN_COMPLIANCE.md` (which plan tasks the audit rated PARTIAL/FAIL/BLOCKED).
5. `IMPLEMENTATION_PLAN.md` (the specification the fixes must satisfy; sections 3, 6 and 10 especially).
6. `docs/DECISIONS.md` (so you do not contradict earlier decisions).

**Orientation only (the report is authoritative).** The audit summary named these as the top risks; make sure your plan covers them and treats them with the priority they deserve:
(1) `eval()` on downloaded Amazon data (remote code execution risk) around `amazon.py:51`;
(2) test-set leakage: the Amazon item cap uses test interactions, MIND history is backdated in a way that breaks the R2 guarantee;
(3) `docs/CONFORMANCE.md` falsely certifies R2/R8/R10 as PASS with 0 FAIL;
(4) Articles evaluation defects: train-impression fallback, nondeterministic Random baseline, missing exclusions, a hardcoded leakage flag;
(5) reproducibility/ops gaps: no lock file, CI excludes 42 real-data tests, non-atomic artifact writes, serving config ignoring two tuned parameters.

---

## 3. Setup procedure (do this once, record it in `audit/fixes/FIX_LOG.md`)

**3.1 Create the working area:** `audit/fixes/` with `FIX_LOG.md`, `NEW_OBSERVATIONS.md`, `FINDINGS_STATUS.json` (a copy of the finding IDs with a `status` field you will update; never edit the original `FINDINGS.json`).

**3.2 Check the git state:** `git status --porcelain` and `git branch --show-current`. Expected: only untracked `audit/`, `AUDIT_PROMPT.md` (and this file). If TRACKED files are modified or staged, STOP and tell the human; do not proceed on a dirty tracked tree.

**3.3 Create the branch:** `git switch -c fix/audit-findings` (if it exists, use `fix/audit-findings-2`). Record the base commit hash.

**3.4 Reproduce the baseline:** run the same lint, type-check and test commands as `audit/01_BASELINE.md`. Record test counts (passed / failed / skipped / xfail) and the lint/type error counts. **This is your regression floor:** after every batch the number of passing tests must not drop, skips must not rise, and lint/type errors must not rise. A baseline that differs from the audit's baseline is itself worth noting.

**3.5 Back up local state:** if `artifacts/` exists, copy it (Rule 1.9). Note whether real datasets exist under `data/raw/` (this decides which verifications are possible).

**3.6 Build the work plan:** from the report's roadmap, write the ordered list of findings you will address this session into `FIX_LOG.md`, mark each with its batch, dependencies, effort, and whether it needs an author decision or network. Fixes that change published metrics (leakage and evaluation fixes) must be grouped so the results are regenerated ONCE after them (Section 8).

---

## 4. Ordering rules (how to prioritise)

Default order = the report's "Recommended fix roadmap". Apply these overrides in this precedence:

1. **Risk beats label.** The audit used HIGH/MEDIUM/LOW labels, but its own rubric reserves CRITICAL for exploitable security holes, silent wrong results (data leakage, inflated or fabricated numbers), licence violations, and false certification. Treat any finding of those kinds as top priority even if it is labelled HIGH. You may record a higher severity in `FINDINGS_STATUS.json` with a one-line reason; never record a lower one.
2. **Fix-then-measure order.** Security fixes first (smallest, independent), then leakage/evaluation-validity fixes (they change metrics), then determinism/reproducibility, then contract/behaviour fixes in the API, then tests that were too weak to catch these bugs, then configuration/hardcoded/portability, then maintainability.
3. **Tests before refactors.** If a finding says a behaviour is unprotected by tests, add the protecting test FIRST, then do any refactor that touches that behaviour.
4. **Respect dependencies.** Honour each finding's `depends_on`. If A blocks B, do A first. If two findings share one root cause, fix them together in one commit and list both IDs.
5. **Cheap and safe next to expensive and risky.** Within a batch, do `S` effort items before `L`. Do not start an `L` item you cannot finish and verify in the remaining context: break it into verified steps or mark `PARTIAL` with exact remaining work.

---

## 5. THE FIX LOOP (apply to every finding, in this exact order)

For finding `F-XXX-NNN`:

1. **Read** the finding (JSON + area file) and open every cited `path:line` yourself.
2. **Re-verify** it reproduces (Rule 1.6). Not reproducible: log `NOT-REPRODUCIBLE` with evidence, stop here.
3. **Check decisions.** Does the finding or its fix depend on an AUTHOR DECISION? If the answer is blank, mark `BLOCKED-ON-HUMAN` with the exact question, stop here. If the finding offers several fix options, choose the **least invasive option that fully resolves the risk**, record the choice and the rejected options as a new entry in `docs/DECISIONS.md` (`D-NNN`, context / options / decision / consequences / related finding), and flag it in the final report so the human can veto.
4. **Write the failing test first.** Add a test that demonstrates the defect (place it in the matching tests folder: unit, property, integration or contract). Run it and **confirm it fails for the right reason** (the assertion about the defect, not an import error or typo). Save the failing output excerpt in the log.
5. **Implement the minimal fix.** Touch only what is needed. Keep style and typing consistent with the surrounding code (strict typing for `engine/` and `api/`).
6. **Run the new test:** it must pass. Then run the tests of the affected module, then the full suite, lint and type checks. Compare with the regression floor (3.4). Any new failure: find the cause; do not move on until resolved or the fix is reverted (`git restore` of YOUR OWN uncommitted change is allowed).
7. **Try to break your own fix.** Write down three ways the fix could still be wrong or incomplete (examples: other call sites with the same pattern, Windows path/encoding behaviour, empty/huge/unicode input, a different content type, the fast vs final pipeline) and check each with a command or a test. Fix what you find.
8. **Sweep for siblings.** Search the repository for the same defect pattern elsewhere (`git grep`). If the audit grouped locations, make sure ALL are fixed. Add any new location you discover to the log (and to `NEW_OBSERVATIONS.md` if it is outside the finding's scope).
9. **Review your own diff:** `git diff` must contain only intended changes (no stray formatting, no unrelated edits, no debug prints, no files outside the intended folders). Fix before committing.
10. **Commit** with `FIX F-XXX-NNN: <summary>` and a body listing: what changed, the test added, and verification commands.
11. **Log** in `audit/fixes/FIX_LOG.md` and update `FINDINGS_STATUS.json`: `status` in { `FIXED`, `PARTIAL`, `BLOCKED-ON-HUMAN`, `NOT-REPRODUCIBLE`, `WONT-FIX` (with reason approved by the audit or by an author decision) }, commit hash, test names added, the commands you ran, remaining risk.

**Definition of `FIXED`:** the failing test now passes; full suite, lint and type checks are no worse than baseline; the same pattern was swept; no unrelated diff; the finding is logged with evidence. Anything less is `PARTIAL`.

---

## 6. Playbooks for the finding types in this audit

Use these as guidance only where the corresponding finding exists. The finding's evidence and the real code always win over this text.

**6.1 Unsafe evaluation or deserialisation (the `eval()` finding, pickle/joblib, `yaml.load`).**
- Replace the unsafe call with a safe parser appropriate to the data (for example `json.loads` per line, or `ast.literal_eval` only if the data truly is a Python literal and its structure is validated afterwards). Confirm the real file format by reading the adapter and a fixture, not by memory.
- Add a test that feeds a **malicious payload** (for example a string that would execute `__import__('os')...` or create a marker file in a temp dir) and asserts it is rejected or treated as plain data and that nothing executed.
- Validate the parsed structure (types, required keys) and count/skip malformed lines explicitly (log counts, do not swallow silently).
- Sweep the whole repo (`git grep -n -E "\beval\(|\bexec\(|pickle|joblib\.load|yaml\.load\b|allow_pickle"`), including tools and scripts.

**6.2 Data leakage (item cap using test rows, backdated history, train-impression fallback, hardcoded leakage flag).**
- Fix the data flow so that **only the training split** can influence any fitted or selected structure: item caps, vocabularies, popularity, similarity, recency windows, hyperparameter selection.
- Replace any hardcoded `leakage_ok = True`-style flag with a **real computed check** that compares actual frames/timestamps, and prove with a test that the check FAILS on a deliberately broken split fixture and passes on a clean one (plan R2).
- Add a "perturbation" test: change or remove test rows and assert that the fitted artifact (capped item list, similarity, vocabulary, popularity) is **identical**. This is the strongest guard.
- Re-run the leakage checks on the real splits if data exists (Section 8). If you cannot, say so; never mark an R2 gate passed without running it.

**6.3 Evaluation-validity defects (nondeterministic Random baseline, missing exclusions, unfair candidate sets).**
- Random baseline: seed per user from a **stable hash** (for example `hashlib` over the user id plus the global seed), never Python's built-in `hash()` on strings, never global RNG state. Test determinism across two processes with different `PYTHONHASHSEED` values.
- Model and baselines must share the same split, candidate set, and seen/excluded item exclusion. Test it by asserting equal candidate sets (or a documented, justified difference).
- Ties: use stable sorts or explicit tie-breaks (`np.argsort(kind="stable")`, `np.lexsort`).
- Independently re-check each corrected metric against a hand-computed value (plain numpy in the test).

**6.4 False or untraceable documentation (`docs/CONFORMANCE.md`).**
- First find how the file is produced. If a script generates it, fix the script so every status is **derived from a real, runnable check** (and `FAIL` or `NOT-VERIFIED` is a possible output). If it is hand-written, rewrite each status to only what you have evidence for now, with the command and date next to it.
- Gates that cannot be run here (no data, no network) are `NOT-VERIFIED`, never `PASS`.
- Add a small consistency test or script that fails if CONFORMANCE statuses contradict the pipeline outputs (for example claims R8 PASS while the benchmark file is missing).

**6.5 Reproducibility and operations (lock file, atomic writes, config parity, CI coverage).**
- Atomic artifact writes: write into a temporary directory in the same parent, `fsync`/close, then `os.replace` into place; on failure leave the previous artifact untouched. Test with a simulated failure mid-write (monkeypatch an exception) and assert the old artifact still loads. Remember Windows: replacing a directory needs care (rename old to a backup name, move new into place, remove backup), so test on this platform.
- Serving config parity: any parameter the training/tuning used must be read from the **same config/manifest** at serving time. Add a test asserting that every tuned parameter in the manifest reaches the loaded model object.
- Lock file: generate with the project's tool (`uv lock`); if no network, hand the human the exact command (Rule 1.8). Add a check that the lock file matches `pyproject.toml`.
- CI vs real-data tests: do NOT commit datasets. Propose the least invasive design (for example a `realdata` marker, clearly documented, run by `make gates` locally, with CI running small committed fixtures that exercise the same code paths), record it in `docs/DECISIONS.md`, and make sure tests that skip for missing data say so loudly instead of silently passing.

**6.6 API fixes.** After any change under `api/`: regenerate and re-check `openapi.json` with `scripts/export_openapi.py`; run the contract and property tests; re-run the adversarial probes relevant to the fix (invalid `k`, unknown type, malformed JSON, non-ASCII API key); assert error shapes remain `{"error": {"code", "message"}}`; assert the process still never imports `tensorflow`, `pyspark`, `torch`, `cornac`.

**6.7 Hardcoded values and configuration.** Move values into the YAML config (validated by pydantic) or env vars with sensible, documented defaults; keep ONE source of truth; update every call site; add a test that changing the config value changes behaviour; make unknown config keys fail loudly where the audit says typos are silently ignored. Update the `configs/*.yaml` and `docs` accordingly.

**6.8 Weak tests.** Strengthen tests rather than adding new redundant ones: assert actual values, add negative cases, raise hypothesis `max_examples`, remove silent skips (turn them into explicit, documented markers). After strengthening, run the audit's "mutation spot-check" idea: temporarily break the behaviour in a scratch script (never in the repo) and confirm the strengthened test fails.

**6.9 Portability (Windows).** Specify `encoding="utf-8"`; use `pathlib`; add `.gitattributes` if the audit asked for it (for example `* text=auto eol=lf` for tracked text/checksummed files) and verify no existing checksummed file changes unexpectedly; make Makefile-dependent instructions work with raw commands as well.

**6.10 Plan violations in vendored code or licence files.** Do not rewrite upstream logic. Fix headers, `NOTICE.md`, `ATTRIBUTION.md`, `VENDORED_FILES.md` (regenerate with `tools/vendored_manifest.py`), leftover old-name references, and any undocumented patch (document it or revert it). Never remove the original LICENSE or copyright headers.

---

## 7. Batch gate (after EACH batch, before starting the next)

Run and record in `FIX_LOG.md`:
1. Full test suite, lint, format-check, type-check; compare to the regression floor. Required: passing tests >= baseline, no new skips/xfails, no new lint/type errors.
2. Import purity subprocess check (`tensorflow`, `pyspark`, `torch`, `cornac`, `recommenders` not imported by `engine`/`api`).
3. `git diff <base>..HEAD --stat`: confirm only intended areas changed; no accidental changes under `backend/discovery/` except finding-related ones.
4. The audit's hardcode scanner (`python audit/scratch/hardcode_scan.py`) on the new tree: counts per category must not increase.
5. A mini "break your own work" note: three ways this batch could have introduced a regression, each checked.
6. Update the dashboard honestly (Section 9) only after the gate passes.

If the gate fails, fix or revert the offending commit's changes with a NEW commit (`git revert <hash>` is allowed on your own branch) before continuing.

---

## 8. Metrics regeneration protocol (after the leakage/evaluation fixes are gated)

Leakage and evaluation fixes change the published numbers. Expect them to usually go DOWN. That is correct and must be reported honestly.

1. **Preconditions:** the relevant fixes are committed and passed the batch gate; artifacts are backed up (Rule 1.9); check whether the real datasets exist under `data/raw/`.
2. **Snapshot "before":** copy every `artifacts/<type>/metrics.json` and `docs/RESULTS.md` into `audit/fixes/metrics_before/`.
3. **Re-run the pipeline** with the project's documented commands, `--fast` first to validate the flow, then the final (non-fast) run if time and data allow. If data or time is missing, do not fake anything: add `STALE: regenerate with <exact command>` markers (Rule 1.5) and list the commands for the human.
4. **Verify the regenerated results:** (a) the leakage check runs for real on the real split and passes; (b) sanity ordering Random < Popularity <= Model is recorded as computed (if the model no longer beats popularity, report it honestly, do NOT tune on test, add the finding to `docs/DECISIONS.md` as the plan's R4 requires); (c) retrain twice and compare **contents** of `topn.parquet` (load with pandas, compare frames; parquet bytes may differ); (d) bootstrap intervals regenerated.
5. **Golden files:** they will legitimately change. Update them ONLY through the project's own documented regeneration path, in a separate commit `FIX GOLDEN: <reason>`, and put a before/after table in the log that ties each change to a specific finding. Never regenerate a golden file just to make a failing test pass without that explanation.
6. **Regenerate documents with the scripts** (`tools/make_results.py`, the CONFORMANCE generator if one exists, the vendored manifest script). Never hand-edit numbers (Rule 1.5).
7. **Record a before/after table** (headline metrics per type and `k`, with source file paths) in `FIX_LOG.md` and `FIX_REPORT.md`.

---

## 9. Plan and documentation bookkeeping

- Read `audit/02_PLAN_COMPLIANCE.md`. For each task the audit rated PARTIAL, FAIL or BLOCKED: after the related fixes, re-check the acceptance text yourself. Re-tick `[x]` ONLY if every clause is satisfied with evidence; otherwise leave or set `[~]` (with a one-line note of what is done/remaining) or `[!]` (with what the human must do).
- Run `python tools/progress.py` twice (the second run must change nothing) and commit the plan/dashboard changes as `FIX BOOKKEEPING: <summary>`.
- Add one Session Log entry at the end of the plan using the plan's own template: "Phase 2 fix session", with completed/partial/blocked items, decisions (`D-NNN` links), gate results with evidence, five "break your own work" hypotheses and outcomes, test status, next steps.
- Every deviation, rejected option and library-version difference goes into `docs/DECISIONS.md`.
- Update `docs/ATTRIBUTION.md`, `NOTICE.md`, `VENDORED_FILES.md` only if a finding touched vendored files.

---

## 10. Closing the audit's coverage gaps (do after the batches, read-only unless noted)

The audit listed things it could not cover. Try each; if impossible here, give the human the exact command and say why.

1. `pip-audit` (needs network). If it fails, record the failure and the command.
2. Exhaustive git-history secret scan: write a scratch script over `git log -p --all` patches matching key/token/password/private-key patterns; **mask any hit** in your output; report counts and locations only.
3. Test coverage percentage: run the project's coverage command with the data file redirected into `audit/fixes/coverage/` (set `COVERAGE_FILE`); list `engine/` and `api/` modules under 80% and the uncovered error paths.
4. Full API benchmark (`scripts/bench_api.py`) if artifacts exist; compare with plan R8 budgets; report measured values only.
5. Acceptance check for plan task P5.3 (MIND time protocol) on the real MIND data if present.
6. Clean-room rebuild (fresh clone, fresh venv, README commands). Needs network for installs: if unavailable, document the exact steps for the human.
7. `schemathesis` against the OpenAPI schema if it is installed; do not install it.
8. Upstream diff of the vendored package: needs the upstream source; give the human the command, do not guess.

New problems found go to `NEW_OBSERVATIONS.md`.

---

## 11. Final verification and mini re-audit

1. Re-run every command from the audit's verification that produced a failure or finding, and map each result to its finding ID.
2. Re-run (or adapt from `audit/scratch/`, reading each script first) the adversarial API probes for every area you touched; there must be no 500s, no stack traces, and the error shape must be uniform.
3. Review the whole branch diff (`git diff <base>..HEAD --stat`, then read the diff area by area): no unrelated edits, no debug leftovers, no secrets, no large files, nothing committed from `artifacts/`, `data/`, `audit/`.
4. Ensure `audit/fixes/FINDINGS_STATUS.json` gives every audited finding a terminal status, and the counts match `FIX_REPORT.md`.
5. Run the full check one last time and record counts versus the regression floor.
6. Do NOT merge the branch. Leave it for the human to review.

---

## 12. Low context / low quota protocol

When you suspect context or quota is running low: stop starting new findings; finish or cleanly revert the current one (the tree must build and tests must pass at every commit); update `FIX_LOG.md` with a section **"RESUME HERE"** (next finding, current state, pending decisions, commands to run); write `FIX_REPORT.md` marked **PARTIAL**; and say so in your final message. **Resume protocol for a new session:** read `audit/fixes/FIX_LOG.md` first, confirm the branch and `git log`, rebuild the regression floor from the log, and continue from "RESUME HERE". Do not redo finished work.

---

## 13. Deliverables (inside `audit/fixes/` unless noted)

- `FIX_LOG.md`: live, chronological, one block per finding: status, commit hash, files changed, failing-test excerpt before the fix, passing result after, commands run, the three "break your own fix" checks and their outcomes, remaining risk.
- `FINDINGS_STATUS.json`: all audited finding IDs with `status`, `commit`, `tests_added`, `notes`, optional `severity_override` with reason.
- `NEW_OBSERVATIONS.md`: new problems you saw but did not fix.
- `FIX_REPORT.md` (final), in this order: (1) summary with counts by status and by severity and test/lint/type counts before vs after; (2) table of finding, status, commit, tests added; (3) metrics before vs after from pipeline files, with paths; (4) decisions made (`D-NNN`) that the human should confirm or veto; (5) `BLOCKED-ON-HUMAN` items with exact questions or commands; (6) summary of new observations; (7) honest residual risks; (8) audit coverage gaps closed and still open; (9) plan bookkeeping changes; (10) how to review this branch (suggested commit order).

---

## 14. Self-verification checklist (complete before you declare done)

Copy into `FIX_LOG.md` and tick only what is true:
- [ ] I read the full report, the findings JSON, the baseline and the plan compliance file.
- [ ] Every audited finding has a terminal status in `FINDINGS_STATUS.json`.
- [ ] Every `FIXED` finding has a test that failed before and passes now, and I saved the evidence.
- [ ] No test was deleted, skipped, loosened or marked xfail to get green.
- [ ] Passing tests >= baseline; skips, lint errors and type errors are not higher than baseline.
- [ ] No number in any document was typed by hand; stale numbers carry a STALE marker.
- [ ] No claim of PASS exists anywhere (including `docs/CONFORMANCE.md`) that I did not verify by running a check.
- [ ] I swept the repo for the same defect patterns as each fixed finding.
- [ ] The branch diff contains no unrelated changes, secrets, data, artifacts or audit files.
- [ ] Every decision and rejected option is in `docs/DECISIONS.md` and listed in the report.
- [ ] Every blank AUTHOR DECISION was left unguessed and its findings marked `BLOCKED-ON-HUMAN`.
- [ ] I did not merge, force-push, or rewrite history.

---

## 15. Final message in the chat (keep it short)

Reply only with: (1) path to `audit/fixes/FIX_REPORT.md`; (2) counts by status (FIXED / PARTIAL / BLOCKED-ON-HUMAN / NOT-REPRODUCIBLE / WONT-FIX); (3) test, lint and type counts before vs after; (4) headline metric changes in one line per type (from pipeline files); (5) the branch name and the number of commits; (6) the questions and commands the human must act on; (7) anything unfinished or unverified. Do not paste the full report.
