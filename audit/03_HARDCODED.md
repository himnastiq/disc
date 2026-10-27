# Hardcoded-Value Sweep

**Command:** `python audit/scratch/hardcode_scan.py` (raw output: `audit/hardcoded_scan_raw.txt`).
**Raw size:** 1,190 matching lines, 14 categories.
**Method:** regex scan of tracked source/config/tool files, then manual triage of every category and hot-spot review of production code. Test fixtures and documentation were read in context rather than judged by pattern alone.

## Category counts and triage

| Category | Hits | Triage |
|---|---:|---|
| `ABSOLUTE_PATH` | 78 | Mostly documentation URLs, dataset URLs, citation links, and Windows path normalization. No hardcoded developer home directory. Benign. |
| `URL_OR_HOST` | 136 | Expected dataset/citation/attribution endpoints and test image URLs. Benign. |
| `PORT` | 2 | `localhost:3000` CORS/demo defaults. Acceptable; CORS is env-overridable. |
| `SECRET_LIKE` | 1 | `backend/tests/unit/test_api_security.py:102` test token only. No production secret. |
| `TYPE_SPECIFIC` | 142 | Mostly registry names, API descriptions, docstrings, and tool CLI defaults. Real branches exist in `artifacts.py:149-159` (display names) and `train.py:247` (evaluation caps). Acceptable but worth centralizing display metadata. |
| `MAGIC_NUMBER` | 658 | Mostly thresholds, metric constants, test values, and CLI defaults. Hot spots below. |
| `SEED_LITERAL` | 16 | Configs use `seed: 42`; tests use explicit seeds. Expected. |
| `BROAD_EXCEPT` | 24 | Mostly API handlers, optional-tool fallbacks, and logging. Two problematic swallows: `config.py:175-176` (F-010) and `articles_eval.py:505-506` (F-009). |
| `PRINT_CALL` | 15 | Training CLI summary only (`train.py:293-331`). Acceptable. |
| `TODO_MARKER` | 1 | `backend/tests/unit/test_progress.py:25` fixture text. Not a real TODO. |
| `SUPPRESSION` | 47 | Mostly `type: ignore`/`noqa` with reasons. No blanket production suppression. |
| `ASSERT_RUNTIME` | 16 | `checks.py` asserts are intentional invariant checks; adapter/model asserts are F-020. |
| `UNSAFE_CALL` | 12 | The real one is `amazon.py:51` `eval` (F-001); the rest are Makefile `find`/shell text and docstrings. |
| `NAIVE_TIME` | 14 | Timing/logging in tuning, benchmarks, and tools; no business logic depends on wall-clock time. |

## Hot spots reviewed

1. **`backend/engine/adapters/amazon.py:51` — `eval(line)`**
   - Real unsafe call on downloaded data. Reported as F-001 (HIGH). This is the only code-execution primitive found.

2. **`backend/engine/evaluation/articles_eval.py:121` — `int(abs(hash(ctx))) % 10000000`**
   - Built-in string hash is process-randomized; the Random baseline is not reproducible. Reported as F-008 (MEDIUM).

3. **`backend/engine/train.py:247` — `max_test = 2000 if ... else (50 if fast else 200)`**
   - Hardcoded evaluation sample caps. Not a correctness bug, but the caps should be config/evaluation metadata so metrics can state exactly how many users/impressions were evaluated. Currently `metrics.json` records `evaluated_test_users`, which mitigates the opacity.

4. **`backend/api/search.py:55` — `default_rank = len(pop_ranks) + 1000`**
   - Magic tie-break offset. It works because it is larger than any real popularity rank; a named constant would be clearer.

5. **`backend/api/security.py:17` — `MAX_REQUEST_BODY_BYTES = 1_048_576`**
   - Correct 1 MB constant; should remain a named constant.

6. **`backend/engine/config.py:175-176` — `except Exception: pass`**
   - Hides malformed tuning data and contributes to F-010. Replace with a logged warning/error.

7. **`backend/engine/evaluation/articles_eval.py:505-506` — `except Exception: continue`**
   - Silently drops cold-start users, biasing the curve. Reported as F-009.

8. **`backend/engine/adapters/{amazon,mind}.py` runtime asserts**
   - F-020. Low impact but should be explicit exceptions.

## Conclusions
- **No hardcoded production secrets, API keys, or credentials were found.**
- **One genuine unsafe call:** `eval()` on untrusted Amazon data (F-001).
- **Two exception-swallowing hot spots** materially affect reproducibility/evaluation (F-009, F-010).
- Most magic numbers are legitimate config/test/threshold values; the main quality improvement is to move evaluation sample caps and display/type metadata into config or named constants.
- The scan did not find evidence of environment-specific absolute paths in production code; path normalization in tests/tools is intentional.
