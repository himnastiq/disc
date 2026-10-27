# AREA EVAL — Evaluation harness, splits, metrics, articles evaluation

**Verdict:** FAIL WITH FINDINGS — 5 MEDIUM.

## Files read
- `backend/engine/evaluation/harness.py`
- `backend/engine/evaluation/splits.py`
- `backend/engine/evaluation/metrics.py`
- `backend/engine/evaluation/checks.py`
- `backend/engine/evaluation/articles_eval.py`
- `backend/engine/tuning.py`
- `backend/tests/integration/test_articles_split_leakage.py`
- `backend/tests/integration/test_articles_consistency.py`
- `artifacts/{movies,products,articles}/metrics.json`

## Findings
### F-006 — Tuning scores threshold trials against fixed `positive` labels (MEDIUM)
`backend/engine/tuning.py:201` changes `candidate_spec.signal.positive_threshold`, but `tuning.py:205-209` builds validation positives as:

```python
if "positive" in valid_df.columns:
    pos_valid = valid_df[valid_df["positive"] == True]
else:
    pos_valid = valid_df[valid_df["signal"] >= thresh]
```

MovieLens artifacts have a `positive` column computed once at the original threshold (`movielens.py:222`). For every trial with `positive_threshold = 3.5`, the code still scores against the 4.0 labels. Products have no `positive` column, so they take the correct threshold-aware branch (see F-005).

**Impact:** The threshold dimension of the movie grid search is invalid; a 3.5 trial cannot be compared fairly with a 4.0 trial. The chosen “best” threshold may be wrong, and the reported tuning rationale is misleading.

**Recommendation:** Always derive `pos_valid` from `signal >= thresh` for the trial, or recompute the label column per candidate.

### F-007 — Articles impression evaluation falls back to all impressions, including train (MEDIUM)
`backend/engine/evaluation/articles_eval.py:431-433` selects impressions with `timestamp > train_max_ts`, then, if the list is empty, assigns `test_impressions = impressions` — the full set, including training-period impressions.

**Impact:** On a short or poorly split dataset, the “test” impression ranking is computed on train impressions, inflating AUC/MRR/nDCG. The fallback is silent and is recorded as a normal evaluation.

**Recommendation:** Fail or emit a prominent warning when there are no post-train impressions; never evaluate on train impressions.

### F-008 — Articles Random baseline uses built-in `hash()` and is not reproducible (MEDIUM)
`backend/engine/evaluation/articles_eval.py:116-122` scores the Random baseline with:

```python
ctx = f"imp:{imp_id}:{user_id}:{c}:{seed}"
h_val = int(abs(hash(ctx))) % 10000000
```

Python’s string `hash()` is randomized per process by `PYTHONHASHSEED`. I ran the same expression in three processes and got `5076166`, `6895007`, and `6011368`.

**Impact:** The articles Random baseline and any metric derived from it change across processes. P5.8’s “compare against Random under identical candidates” and P6.3’s reproducibility claim are weakened. The project already has a deterministic `RandomModel` using SHA-256 (`baselines.py:195-210`); this code bypasses it.

**Recommendation:** Use `RandomModel` or `hashlib.sha256(ctx.encode()).digest()` for the baseline.

### F-009 — Articles cold-start curve is not protocol-identical to the shared harness (MEDIUM)
`backend/engine/evaluation/harness.py:260-268` builds `exclude_seen` from the user’s full training history and passes it to `recommend_history`. `backend/engine/evaluation/articles_eval.py:492-497` passes only `history=hist_sample` and `k=eval_k`; it does not pass `exclude_ids`.

In addition, `articles_eval.py:505-506` catches every exception from `recommend_history` and `continue`s, silently dropping failed users from the curve.

**Impact:** Articles cold-start hit-rate/NDCG/recall are computed with a different candidate set than movies/products, and failed users are omitted rather than penalized. The cross-type cold-start table is not apples-to-apples.

**Recommendation:** Reuse the harness’s cold-start loop or pass the same full-history exclusion set, and count failures explicitly.

### F-015 — Articles metrics hardcode `leakage_check_passed: True` (MEDIUM)
`backend/engine/evaluation/articles_eval.py:552-560` builds `sanity_checks` and sets:

```python
"leakage_check_passed": True,
```

No R2 check is called in this function. The value is unconditional.

**Impact:** `artifacts/articles/metrics.json` and the API `/metrics` endpoint assert a leakage check that never ran. Combined with F-003 and F-013, this is a false assurance.

**Recommendation:** Call `check_leakage`/`check_r2_no_leakage` on the actual split and store the real result; fail the pipeline on leakage.

## Positives verified
- `check_r1_data_validity`, `check_r2_no_leakage`, and `check_r3_model_invariants` are reusable and used by tests/harness.
- The shared harness uses the same split and candidate protocol for baselines and the primary model, and reports coverage/novelty/diversity/personalisation.
- Movies and products metrics include `bootstrap_resamples: 500` and `bootstrap_ci: 0.95`; both articles protocols include `*_ci95` fields computed with 500 resamples.
- Sanity checks report `popularity_beats_random`, `model_beats_popularity`, and per-metric CI separation honestly (movies: only recall separates; products: all five separate).
- `docs/RESULTS.md` regenerates identically with `python tools/make_results.py --check`.

## Uncovered / notes
- Real MIND data was unavailable, so impression-time behavior was exercised only on the synthetic fixture/artifacts.
- I did not rerun the full evaluation pipeline; findings are static plus artifact inspection.
