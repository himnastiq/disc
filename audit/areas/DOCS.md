# AREA DOCS — Documentation versus reality

**Verdict:** FAIL WITH FINDINGS — 1 HIGH, 2 LOW.

## Files read
- `README.md`
- `docs/CONFORMANCE.md`
- `docs/DATASETS.md`
- `docs/ARCHITECTURE.md`
- `docs/RESULTS.md`
- `docs/ATTRIBUTION.md`
- `docs/VENDORED_FILES.md`
- `docs/DECISIONS.md`
- `docs/DEMO_SCRIPT.md`
- `docs/vendored_modules.txt`
- `IMPLEMENTATION_PLAN.md` (including Session Log)
- `artifacts/*/metrics.json` (spot-checked >15 values against RESULTS)

## Findings
### F-004 — CONFORMANCE certifies PASS/0 FAIL with false or missing evidence (HIGH)
`docs/CONFORMANCE.md:75` marks R2 (No Leakage) **PASS** and cites `test_articles_split_leakage.py`, but P5.3 is unchecked in `IMPLEMENTATION_PLAN.md:420`, the test is `real_data` and excluded from CI, and the adapter backdates later history (F-003).

`docs/CONFORMANCE.md:81` claims R8 “actual < 5 ms” and “~340 MB”. The generated `docs/RESULTS.md:214` reports **87.23 ms** p95 and `docs/RESULTS.md:228` reports **796.4 MB** RSS.

`docs/CONFORMANCE.md:83` marks R10 PASS and links to root `NOTICE.md` and `ATTRIBUTION.md`, which do not exist (the real files are `backend/discovery/NOTICE.md` and `docs/ATTRIBUTION.md`), and to `backend/tests/contract/test_licensing.py`, which does not exist.

`docs/CONFORMANCE.md:84` says `secrets.compare_digest`; the code uses `hmac.compare_digest` (`backend/api/security.py:33`), a harmless wording error but another sign the table was not verified.

`docs/CONFORMANCE.md:90-97` concludes **0 FAIL** and “CONFORMANT”, despite the unchecked P5.3 and the missing test/file references.

**Impact:** The document is the project’s primary conformance claim. It overstates R2, R8, and R10 and gives false assurance to reviewers/users. This is a high-severity documentation-integrity issue even though it does not execute code.

**Recommendation:** Regenerate the table from verified evidence, mark P5.3/R2 as PARTIAL/FAIL, replace R8 numbers with generated RESULTS values, fix the R10 links, and add the missing licensing test or remove the citation.

### F-016 — Production MIND command points to a nonexistent script (LOW)
`docs/DATASETS.md:72` says:

```bash
python backend/scripts/train.py --type articles
```

There is no `backend/scripts/train.py`; the supported command is `cd backend && python -m engine.train --type articles` (see `Makefile:29`). A user following the docs gets `No such file or directory`.

### F-017 — ARCHITECTURE claims interactions are split-flagged (LOW)
`docs/ARCHITECTURE.md:37` says `interactions.parquet` contains “train + test interactions (flagged)”. The actual columns are:
- movies: `user_id, item_id, signal, timestamp, positive`
- products: `user_id, item_id, signal, timestamp`
- articles: `user_id, item_id, signal, timestamp, positive`

There is no split/partition flag in any of them. The split is recomputed at evaluation time, not stored in the artifact.

## Positives verified
- `README.md` is honest about the articles pipeline being a synthetic demo and about non-commercial use.
- `docs/RESULTS.md` is generated and `python tools/make_results.py --check` reports it up to date; more than 15 spot-checked numbers (interaction counts, item counts, metrics, RSS, p95) trace to `metrics.json`/benchmark output.
- `docs/ATTRIBUTION.md`, `backend/discovery/NOTICE.md`, and `docs/VENDORED_FILES.md` are complete and consistent with the vendored package.
- `docs/DATASETS.md` correctly documents MovieLens/Amazon/MIND terms and the manual MIND download.
- `docs/DECISIONS.md` contains ADR-style entries for known limitations.

## Uncovered / notes
- I did not verify every number in `docs/RESULTS.md` (spot-check only, >15).
- I did not review the two historical review documents in `docs/reviews/` as current claims.
