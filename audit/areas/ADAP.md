# AREA ADAP — Dataset adapters

**Verdict:** FAIL WITH FINDINGS — 3 HIGH, 1 MEDIUM.

## Files read
- `backend/engine/adapters/base.py`
- `backend/engine/adapters/movielens.py`
- `backend/engine/adapters/amazon.py`
- `backend/engine/adapters/mind.py`
- `backend/engine/adapters/toy.py`
- `backend/scripts/fetch_data.py`
- `backend/engine/configs/{movies,products,articles}.yaml`
- `artifacts/{movies,products,articles}/interactions.parquet` (column/schema inspection)
- `artifacts/{movies,products,articles}/data_report.json`

## Findings
### F-001 — Untrusted Amazon data is executed with `eval()` (HIGH)
`backend/engine/adapters/amazon.py:39-47` first tries `json.loads` and `ast.literal_eval`. If both fail, `amazon.py:51` calls `res = eval(line)` on a line read directly from the downloaded Amazon review/metadata files (`amazon.py:119-129`).

`backend/scripts/fetch_data.py:98-110` downloads the files and checks only the byte count; there is no SHA-256 or signature verification. An attacker who can influence the download source, DNS, or a proxy can supply a line that passes `literal_eval`’s failure path and executes arbitrary Python in the training process.

**Impact:** Remote code execution / full host compromise during `make data` or training. The data is explicitly third-party and untrusted.

**Disproof attempt:** `ast.literal_eval` rejects calls and imports, so the fallback is reachable for any non-literal expression. No sandbox, subprocess, or restricted globals are used. The risk is real.

**Recommendation:** Delete the `eval` fallback. If a legacy format must be parsed, use a dedicated parser or `ast.parse` with an allow-list of node types, and add checksums for downloads.

### F-002 — Amazon item cap is computed before the train/test split, using test interactions (HIGH)
`backend/engine/adapters/amazon.py:243-247` computes `df_inter["item_id"].value_counts()` over the adapter’s full interactions and keeps the top `max_items_in_similarity` items. The split happens later in `backend/engine/train.py:169-175`.

**Impact:** Test-period interactions influence which items survive the cap, so the catalogue and popularity signal are selected with knowledge of the test set. This violates R2’s “no test interactions in popularity/similarity” and P4.2’s selection integrity. It can inflate product metrics and makes the published product results non-causal.

**Disproof attempt:** I traced the call order: `adapter.interactions()` runs `_prepare_data` (including the cap) before `split_interactions`. No train-only filter is applied before the cap. The defect is confirmed.

**Recommendation:** Split first, then apply the popularity cap using train interactions only (or fit the cap inside the training pipeline), and assert that test item IDs never influence the retained set.

### F-003 — MIND time protocol backdates later history and globally dedupes, leaking future clicks (HIGH)
`backend/engine/adapters/mind.py:288-312` sorts all behavior rows by impression time, but assigns every history item a timestamp before the user’s **first** impression (`min_ts - 86400 - ...` at line 312). History from later sessions therefore receives a timestamp in the train period even though those clicks happened later.

`backend/engine/adapters/mind.py:355-359` then globally deduplicates `(user_id, item_id)` with `keep="last"`. A clicked test item that also appears in a later history is kept at the backdated train timestamp; a test click that duplicates an earlier history item is dropped entirely.

**Impact:** Future preferences can enter the training positive set, and test clicks can disappear. The R2 leakage test in `backend/tests/integration/test_articles_split_leakage.py` only checks train/test pair intersection after this dedupe, so it cannot detect the backdating. P5.3 remains unchecked in `IMPLEMENTATION_PLAN.md:420`; the only leakage test is marked `real_data` and excluded from CI (see F-013).

**Disproof attempt:** The plan’s intent is “history items … occur before the user’s first impression”, but the implementation applies that rule to history from **every** session, including sessions after the first. That is stronger than the plan and is exactly the leak. The global `seen_user_items` set also makes the result order-dependent.

**Recommendation:** Build the train/test boundary from impression timestamps and only include history clicks whose true session time is before the boundary. Do not backdate post-boundary history. Add a real-data R2 test that checks the actual clicked item/time, not just pair intersection.

### F-005 — Product interactions omit the required `positive` field (MEDIUM)
`backend/engine/schema.py:29` defines `Interaction.positive: bool` as required. MovieLens sets it at `backend/engine/adapters/movielens.py:222`; MIND sets it at `backend/engine/adapters/mind.py:319/338`; the Amazon adapter builds rows with only `user_id`, `item_id`, `signal`, and `timestamp` at `backend/engine/adapters/amazon.py:138-144`.

**Impact:** The products artifact is schema-inconsistent with the other types. `check_r1_data_validity` silently falls back to `signal >= threshold` (`backend/engine/evaluation/checks.py:101-104`), and `tuning.py:206-209` also takes the fallback path. Consumers that assume the unified schema will fail or silently treat products differently.

**Recommendation:** Add `positive = signal >= spec.signal.positive_threshold` in the Amazon adapter, and add a cross-type artifact-schema assertion.

## Positives verified
- MovieLens title cleaning, year parsing, genre mapping, minimum-interaction filtering, and `positive` derivation are implemented and tested.
- Amazon metadata join has missing-title fallbacks and counts missing metadata; product-specific checks exist.
- MIND parsing handles missing abstracts, unicode, empty histories, unknown catalogue items, and duplicate news IDs; data reports include date ranges.
- Adapters are registered by decorator and keep dataset-specific logic out of the engine core.
- Artifact counts inspected: movies 999,611 interactions / 3,883 items; products 216,994 / 8,000; articles 28 / 15 (synthetic).

## Uncovered / notes
- Real MIND files were not available, so the adapter was exercised only on the synthetic fixture and committed artifacts. This is the main reason P5.3 cannot be closed.
- I did not re-download Amazon data; the `eval` finding is static and does not require network access.
