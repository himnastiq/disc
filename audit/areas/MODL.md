# AREA MODL — Models, explanations, cold start

**Verdict:** PASS — no direct model defect found; two adjacent issues are reported under CORE/EVAL.

## Files read
- `backend/engine/models/base.py`
- `backend/engine/models/sar.py`
- `backend/engine/models/tfidf.py`
- `backend/engine/models/baselines.py`
- `backend/engine/explain.py`
- `backend/engine/coldstart.py`
- `backend/tests/unit/test_baselines.py`
- `backend/tests/unit/test_tfidf_model.py`
- `backend/tests/integration/test_sar_consistency.py`
- `backend/tests/integration/test_cross_type_consistency.py`

## Assessment
- `SarModel` wraps the vendored SAR implementation, fits from config params, excludes seen items unless `allow_repeat`, stores sparse top-neighbour similarity, and implements `popular`, `similar_items`, and `recommend_history`.
- `recommend_history` builds a sparse affinity vector and multiplies it by the item similarity matrix (`sar.py:285-301`), removes history/excluded items (`sar.py:303-305`), sorts deterministically by `(-score, item_id)` (`sar.py:327`), and pads with popularity if fewer than `k` candidates remain (`sar.py:329-333`).
- `TfidfProfileModel` fits its vocabulary on train-period articles, stores sparse vectors/vocabulary, builds user profiles from clicked history, and supports exclusion lists.
- `RandomModel` is genuinely deterministic: it derives a seed with SHA-256 over `seed:context` (`baselines.py:195-197`) and uses `random.Random` (`baselines.py:210`). This contrasts with the articles evaluation’s separate use of built-in `hash()` (F-008).
- `explain.find_top_contributor` only considers history items with positive contribution and computes a share; `format_reason` suppresses reasons below the configured threshold.
- Cross-type consistency and SAR consistency tests are present and passed in the full suite.

## Adjacent findings (reported elsewhere)
- **F-010 (CORE):** `resolve_serving_config` does not re-apply tuned `similarity_type`/`timedecay_formula`, so a tuned SAR artifact may be served with the wrong configuration.
- **F-008 (EVAL):** the articles evaluation bypasses `RandomModel` and uses built-in `hash()` for its Random baseline.
- **F-009 (EVAL):** the articles cold-start curve does not pass the full-history exclusions used by the shared harness.

## Positives verified
- R3 invariants are checked in the shared `checks.py` suite and exercised across types.
- The SAR cold-start consistency test compares `recommend_user` with `recommend_history` on training history for sampled users.
- Explanation property tests assert the reason item is a member of history and is the maximum contributor.
- No TensorFlow/PyTorch dependency is introduced by any model.

## Uncovered / notes
- I did not independently re-derive SAR scores against the vendored implementation; I relied on the existing consistency tests and the full-suite pass.
- Model performance quality is outside this audit’s scope; only correctness/reproducibility contracts were checked.
