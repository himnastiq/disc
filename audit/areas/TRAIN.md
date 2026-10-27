# AREA TRAIN — Training CLI, tuning, artifacts

**Verdict:** PASS WITH FINDINGS — 2 MEDIUM, 1 HIGH (shared with ADAP).

## Files read
- `backend/engine/train.py`
- `backend/engine/tuning.py`
- `backend/engine/artifacts.py`
- `backend/engine/config.py`
- `backend/engine/configs/*.yaml`
- `tools/make_results.py`
- `artifacts/*/manifest.json`, `tuning.json`, `metrics.json`, `data_report.json`

## Findings
### F-002 — Amazon cap is applied before the split (HIGH, also in ADAP)
`train.py:169-175` splits after `adapter.interactions()` has already capped items using all interactions. See AREA ADAP for the full analysis.

### F-006 — Tuning threshold trials use fixed labels (MEDIUM, also in EVAL)
`tuning.py:205-209` ignores the trial threshold when a `positive` column exists. See AREA EVAL.

### F-010 — Tuning output cannot be fully reconstructed at serving time (MEDIUM, also in CORE)
`train.py:190-196` writes five tuned parameters, but `config.py:164-174` re-applies only three. See AREA CORE.

### F-011 — Artifact writes are not atomic (MEDIUM, also in CORE)
`artifacts.py:113-118` and `artifacts.py:184`. See AREA CORE.

## Positives verified
- `python -m engine.train --type X [--fast] [--seed N]` is implemented with argparse, config loading, adapter validation, split, tuning, fit, evaluation, artifact save, and a printed summary.
- Structured logging uses `log_event` and a consistent formatter.
- The manifest records schema version, content type, model, config hash, git SHA, dataset variant/name, section heading, creation time, and per-file SHA-256.
- Artifacts include `items.parquet`, `interactions.parquet`, `users.parquet`, `topn.parquet`, `model/`, `metrics.json`, `demo_users.json`, `data_report.json`, and `tuning.json` where applicable.
- `tools/make_results.py --check` reports `docs/RESULTS.md` up to date and regenerates figures deterministically.
- Current committed `tuning.json` best params match the YAML defaults for movies/products, so the F-010 latent bug is not currently breaking startup.
- Products manifest records tuned `top_neighbors_per_item = 100`; serving reconstruction applies that value.

## Uncovered / notes
- I did not retrain the full 1M/8k pipelines. The 439-test suite includes fast/golden/determinism tests, and artifacts were inspected directly.
- Training wall-clock and peak memory were not independently measured; `docs/RESULTS.md` reports the project’s benchmark numbers.
