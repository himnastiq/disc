# AREA API — FastAPI backend

**Verdict:** PASS WITH FINDINGS — 1 MEDIUM, 1 LOW.

## Files read
- `backend/api/main.py`
- `backend/api/security.py`
- `backend/api/errors.py`
- `backend/api/schemas.py`
- `backend/api/deps.py`
- `backend/api/search.py`
- `backend/api/lookups.py`
- `backend/api/routes/metadata.py`
- `backend/api/routes/recommend.py`
- `backend/api/routes/users.py`
- `backend/api/openapi.json`
- `backend/scripts/export_openapi.py`

## Findings
### F-014 — `total_matches` is capped by `limit` (MEDIUM)
`backend/api/routes/metadata.py:247` calls `index.search(query=q, limit=limit)`, then `metadata.py:252` sets `total_matches=len(results)`.

`backend/api/schemas.py:129` describes `total_matches` as “Total number of matches”. Dynamic test on the mini artifact: query `q=a` has 59 matching items, but with `limit=1` the response reports `total_matches: 1`. With `limit=5` it reports 5, etc.

The contract test only asserts `total_matches >= len(results)` at `backend/tests/contract/test_api_metadata.py:216`, so it cannot catch the bug.

**Impact:** Clients cannot know how many matches exist, cannot implement pagination or “show more”, and the field is semantically wrong.

**Recommendation:** Have the index return `(results, total_count)` or compute the full match count before truncating; assert `total_matches >= len(results)` **and** independence from `limit` in tests.

### F-019 — Item detail reaches into `ItemSearchIndex._entries` (LOW)
`backend/api/routes/metadata.py:286-294` iterates `search_indexes[type]._entries` to find `popularity_rank`.

**Impact:** The API is coupled to a private implementation detail; any refactor of the index breaks item detail. It also does a linear scan per request.

**Recommendation:** Add a public `get_entry(item_id)`/`popularity_rank(item_id)` method or a dictionary lookup.

## Positives verified (dynamic)
Against `backend/tests/fixtures/artifacts_mini`:
- `/v1/health`, `/v1/types`, `/v1/about` → 200.
- `k=0` and `k=51` → 422; `type=../movies` → 404; unknown user/item → 404.
- Empty and 101-character search query → 422.
- Cold-start empty history → 200; 201 entries → 422; duplicate IDs → 422; unknown-only history → 200.
- `exclude` removes the returned item; k=5 results are a stable prefix of k=10.
- `/v1/metrics` payload equals `artifacts/.../metrics.json` exactly.
- Missing/wrong API key → 401; valid non-ASCII key → 200.
- OpenAPI export check passes; committed schema is current.
- Errors use the standard `{"error": {"code", "message", "details"}}` shape; no stack traces leak.
- Artifact corruption is handled at startup by marking the type unavailable rather than crashing.

## Uncovered / notes
- I did not rerun the full benchmark or a >1 MB body-limit probe; the unit test `test_payload_too_large_via_content_length` covers the header path.
- Concurrent-request identity is covered by `tests/integration/test_phase7_gate.py`, not independently rerun here.
