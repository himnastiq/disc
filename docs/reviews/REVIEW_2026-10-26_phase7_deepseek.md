# Review report — Phase 7 deep probe (tester)

- Date: 2026-10-26
- Reviewer: deepseek-v4.1-flash-free (tester role, read-only)
- Project root: `E:\discover`
- Python: `E:\discover\.venv\Scripts\python.exe`
- HEAD: `785e9acc2aab294c763ae28bb195b3b61273946c`
- Shell note: the agent shell is Git Bash, so every PowerShell command below was
  invoked as `powershell.exe -NoProfile -Command "<command>"` from `E:\discover`.
  Command text is otherwise unchanged.

## 1. Summary table

| Step | Check (short name) | Verdict |
|---|---|---|
| 0 | No dev session running (no uvicorn/vite/next dev; no listener on 3000/4173/5173/8000/8080/8888) | PASS |
| 1.1 | `git status --short` (must print nothing) | PASS |
| 1.2 | `git rev-parse HEAD` | PASS |
| 2 | `make check` | ENV PROBLEM |
| 2b | Substitute for 2 (ruff check, ruff format --check, mypy, local pytest), run separately | PASS |
| 3.1 | `$src` / `$dst` set, target removed | PASS |
| 3.2 | robocopy to `%TEMP%\disc_clean` | PASS |
| 3.3 | `empty_artifacts` created | PASS |
| 3.4 | Import path resolves inside TEMP copy | PASS |
| 3.5 | Clean-checkout pytest | FAIL |
| 3.6 | `ARTIFACT_DIR` removed | PASS |
| 4.1 | `docs\reviews\probe_api.py` created exactly as supplied | PASS |
| 4.2 P1 | Cold start, 5 items, no signal → mode `personalized` | FAIL |
| 4.2 P2 | Cold start, 5 items, signal 5.0 → mode `personalized` | PASS |
| 4.2 P3 | `k=50/51/100/101` → `200/422/422/422` | FAIL |
| 4.2 P4 | `meta` contains `model`, `artifact_version`, `latency_ms` | FAIL |
| 4.2 P5 | Popularity-mode user results equal `/v1/popular` | FAIL |
| 4.2 P6 | `/v1/recommend` p95 < 150 ms over 100 users | PASS |
| 4.2 P7 | `/v1/types` card types = movie, product, article | PASS |
| 4.2 P8 | Profile `top_categories` length ≤ 10 | PASS |
| 4.2 P9 | starlette / fastapi versions copied | PASS (copied) |
| 5.1 | `export_openapi.py --check` | PASS |
| 5.2 | No `"toy"` in `backend\api\*.py`, `backend\api\routes\*.py` | FAIL |
| 5.3 | `except Exception` in `backend\api\routes\*.py` (inspection only) | UNSURE |
| 5.4 | `data\raw\mind` train/dev `news.tsv`, `behaviors.tsv` | NOT BUILT YET |
| 5.5 | `docs\RESULTS.md` contains `<1.0 ms` / `50x` / `100x` / `< 250 MB` | FAIL |

## 2. Problems found

### Problem 1 — HIGH — Clean checkout cannot run the test suite; CI will be red

Step 3.5 on the TEMP copy (no `artifacts/`, no `data/`, `ARTIFACT_DIR` pointed at an
empty directory):

```
PYTEST_EXIT=1
...
113 failed, 290 passed, 7 skipped, 2 warnings in 118.89s (0:01:58)
```

Failure nature (from the same single run, first failure block):

```
______________________________________ test_cold_start_personalized_flow[movies] ______________________________________
tests\contract\test_api_cold_start.py:31: in test_cold_start_personalized_flow
    loaded = load_artifacts(ARTIFACTS_DIR / content_type, verify=False)
...
E   FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\Aero\\AppData\\Local\\Temp\\disc_clean\\artifacts\\movies\\manifest.json'
------------------------------------------------ Captured stdout setup ------------------------------------------------
[2026-10-26 07:27:58] [INFO] [engine.api.main] Initializing Discovery Engine API from artifacts: C:\Users\Aero\AppData\Local\Temp\disc_clean\empty_artifacts
[2026-10-26 07:27:58] [WARNING] [engine.api.main] Content type 'articles' unavailable: Artifact directory not found at C:\Users\Aero\AppData\Local\Temp\disc_clean\empty_artifacts\articles
[2026-10-26 07:27:58] [WARNING] [engine.api.main] Content type 'movies' unavailable: Artifact directory not found at C:\Users\Aero\AppData\Local\Temp\disc_clean\empty_artifacts\movies
[2026-10-26 07:27:58] [WARNING] [engine.api.main] Content type 'products' unavailable: Artifact directory not found at C:\Users\Aero\AppData\Local\Temp\disc_clean\empty_artifacts\products
```

Error tally in that log (top entries): `assert 503 == 200` (27), `503 Service Unavailable`
where-clauses (35), `FileNotFoundError` (30), `ArtifactError` (16), `assert 503 == 404` (7),
`assert 503 == 422` (1).

`.github\workflows\ci.yml` runs `pytest tests/ -v --tb=short -x` after install and
**no** training or artifact build step, so on a fresh checkout this is the first
blocking failure. The local suite (with real artifacts) passes 409 tests
(see 2b), so the gap is CI self-sufficiency, not a broken local tree.

### Problem 2 — MEDIUM — `docs\RESULTS.md` prose contradicts its own table (5.5)

Matches found:

```
docs\RESULTS.md:225:- **In-Memory Artifact Serving:** Precomputed `topn.parquet` lookups execute in sub-millisecond
time (<1.0 ms median), bypassing database overhead entirely.
docs\RESULTS.md:226:- **Sparse Live Scoring:** Personalized fallback and cold-start matrix multiplications in
`SarModel` (via sparse COO non-zero iteration) and `TfidfProfileModel` (via sparse CSR dot-product) comfortably beat
the 150 ms tail budget by over 50x to 100x.
docs\RESULTS.md:227:- **Memory Footprint:** Baseline process RSS remains lean (< 250 MB) with zero deep-learning
runtime overhead (no TensorFlow, PyTorch, or JVM memory footprint).
```

Same file, Section 8 table (excerpt):

```
| `GET /v1/recommend (movies)` | 500 | `124.70 ms` | **`143.47 ms`** | `210.84 ms` | `127.34 ms` | `455.0 MB` | **PASSED** |
| `GET /v1/popular (movies)` | 500 | `20.54 ms` | **`25.14 ms`** | `34.97 ms` | `20.83 ms` | `442.7 MB` | **PASSED** |
```

The table shows p50 124.70 ms / p95 143.47 ms for `/v1/recommend (movies)` (≈1.05x
margin against 150 ms, not 50x–100x), 20.54 ms for `/v1/popular` (not sub-millisecond),
and 442.7–455.0 MB RSS (not < 250 MB).

### Problem 3 — MEDIUM — `k` upper bound is 100 in the API, not 50 (P3)

```
P3 k= 50 200
P3 k= 51 200
P3 k= 100 200
P3 k= 101 422
```

`backend\api\routes\recommend.py:99` and `backend\api\schemas.py:301-302` both declare
`ge=1, le=100` ("Number of recommendations requested [1, 100]"). No `1..50` statement
was found in `IMPLEMENTATION_PLAN.md` (searched `1\.\.50`, `1-50`, `max_k`, `k_max`,
`k must`, `between 1 and`), so the stated expectation (1..50) is not what the code or
plan document.

### Problem 4 — MEDIUM — `/v1/recommend` `meta` lacks `model`, `artifact_version`, `latency_ms` (P4)

```
P4 meta keys ['positive_interactions', 'source']
```

`backend\api\schemas.py:277-279` types `meta` as a free-form `dict[str, Any]`
("Diagnostic and serving metadata"); only two keys are populated at runtime.

### Problem 5 — MEDIUM — Popularity-mode response is not the `/v1/popular` list (P5)

```
P5 low-positive user 4349 mode popularity equals_popular False
```

Code path: `backend\api\routes\recommend.py:262-271` builds `exclusions` from
`body.exclude` and the asked user's history, then calls `model.popular(k, exclude_ids=exclusions)`;
`/v1/popular` (`recommend.py:342-351`) applies no user-specific exclusions. So a
`mode=popularity` answer and `/v1/popular` diverge for any user with seen items.

### Problem 6 — LOW — Cold start with 5 no-signal items returns `popularity`, expected `personalized` (P1)

```
P1 no-signal 200 popularity
P2 signal5 200 personalized
```

Mechanism: `recommend.py:254` defaults a missing `signal` to `1.0`; `movies.yaml` sets
`positive_threshold: 4.0`; `recommend.py:258-267` switches to `personalized` only when
`pos_items_count >= min_positive_items_for_personalization` (default 3, per
`backend\README.md`). With no signals, positives = 0, so the response is popularity.
This is consistent with P7.6's rule (`mode = popularity when fewer positive items than
the type's minimum`), but not with the stated expectation for P1.

### Problem 7 — LOW — `"toy"` literals present in API modules (5.2)

```
backend\api\deps.py:21:    available_types = [t for t in registry.types() if t != "toy"]
backend\api\deps.py:22:    if ctype not in available_types or ctype == "toy":
backend\api\main.py:76:    available_types = [t for t in registry.types() if t != "toy"]
backend\api\main.py:78:        if content_type == "toy":
backend\api\routes\metadata.py:83:    registered_types = [t for t in registry.types() if t != "toy"]
backend\api\routes\metadata.py:124:    registered_types = [t for t in registry.types() if t != "toy"]
```

Context: `IMPLEMENTATION_PLAN.md:1023` describes a contract test that asserts `/v1/types`
returns exactly the three content types and that the lifespan loader *ignores*
`artifacts/toy`. The matches are exclusion guards, so the check's premise ("no matches")
conflicts with the behaviour the plan requires.

### Problem 8 — LOW — Broad `except Exception` inside request handlers (5.3)

```
> backend\api\routes\recommend.py:190:        except Exception:
  backend\api\routes\recommend.py:191:            reason_obj = None
  backend\api\routes\recommend.py:192:
> backend\api\routes\recommend.py:307:            except Exception:
  backend\api\routes\recommend.py:308:                reason_obj = None
  backend\api\routes\recommend.py:309:
```

Both sites silently discard any explanation failure and continue with `reason_obj = None`.

### Problem 9 — LOW — Profile returns zero `top_categories` for user `1` (P8)

```
P8 top_categories 0
```

The literal criterion (≤ 10) is met. Recorded because 0 categories for the first
catalogue user is indistinguishable from an unpopulated profile for that user.

### Problem 10 — LOW (environment) — `make` is not installed

```
make : The term 'make' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

Not present in PowerShell PATH or Git Bash PATH; no `make.exe` under Git, Chocolatey,
GnuWin32 or MSYS64 locations.

## 3. Not checked / unsure

- **Step 2 criteria not executed as written.** `make` is absent, so `make check` could not
  run. Its four constituents were run instead (2b): `ruff check .`, `ruff format --check .`,
  `mypy engine/ api/` and `pytest tests -q -rs` — all PASS (409 passed, 1 skipped). This is
  evidence, not a substitute verdict for Step 2, which stays ENV PROBLEM.
- **CI was not reproduced on Linux.** Step 3 ran on Windows/Python 3.11 from
  `C:\Users\Aero\AppData\Local\Temp\disc_clean`. GitHub Actions uses `ubuntu-latest` with a
  fresh `pip install`. The missing-artifact causes (FileNotFoundError on
  `artifacts\*\manifest.json`, `ArtifactError`, 503s) are platform-independent, but the exact
  failure count on Ubuntu was not measured.
- **`ARTIFACT_DIR` scope.** In Step 3.5 the env var redirected the app
  (`Initializing Discovery Engine API from artifacts: ...\empty_artifacts`), while the
  contract tests read `ARTIFACTS_DIR` repo-relative (`...\disc_clean\artifacts`). Both
  locations are empty in the copy, so this does not change the Step 3.5 verdict.
- **5.3 has no stated pass criterion** (inspection only) → UNSURE. Two `except Exception`
  sites are listed above as informational.
- **P9 has no criterion** (explicitly "just copy"): `starlette 1.9.0 fastapi 0.162.0`.
- **P8's 0 categories** may be legitimate for user `1`; not investigated further (that would
  need a second probe run, and each command was run once).
- **`docs\reviews\probe_api.py` is untracked (`??`).** It did not exist before this session
  (Step 1 `git status --short` was empty); it was created here as permitted by the brief and
  is the only file added besides this report.
- **Not attempted:** no git add/commit/checkout/reset, no installs, no `make train`,
  no `make data`, no edits to existing project files.

## 4. Raw output

### Step 0 — dev session check

```
(no output)
```

```
ProcessId   : 3028
Name        : bash.exe
CommandLine : "C:\Program Files\Git\bin\bash.exe" -c "powershell.exe -NoProfile -Command \"Get-CimInstance
              Win32_Process | Where-Object { \$_.CommandLine -match 'uvicorn|vite|next dev|npm run
              dev|pnpm dev|webpack|flask run' } | Select-Object ProcessId, Name, CommandLine | Format-List\""

ProcessId   : 8604
Name        : bash.exe
CommandLine : "C:\Program Files\Git\bin\..\usr\bin\bash.exe" -c "powershell.exe -NoProfile -Command \"Get-CimInstance
              Win32_Process | Where-Object { \$_.CommandLine -match 'uvicorn|vite|next dev|npm run
              dev|pnpm dev|webpack|flask run' } | Select-Object ProcessId, Name, CommandLine | Format-List\""

ProcessId   : 5772
Name        : powershell.exe
CommandLine : C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -Command "Get-CimInstance
              Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn|vite|next dev|npm run
              dev|pnpm dev|webpack|flask run' } | Select-Object ProcessId, Name, CommandLine | Format-List"
```

Only the checking process matched its own pattern; no server process. Listening-port
probe returned `(no output)`.

### Step 1 — git status / HEAD

```
---HEAD---
785e9acc2aab294c763ae28bb195b3b61273946c
```

(`git status --short` printed nothing.)

### Step 2 — `make check`

```
make : The term 'make' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ make check 2>&1 | Tee-Object -FilePath $env:TEMP\make_check.log | Out ...
+ ~~~~
    + CategoryInfo          : ObjectNotFound: (make:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

EXIT=
=== LAST 15 LINES ===
Get-Content : Cannot find path 'C:\Users\Aero\AppData\Local\Temp\make_check.log' because it does not exist.
At line:1 char:155
+ ... === LAST 15 LINES ==='; Get-Content $env:TEMP\make_check.log -Tail 15
+                             ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\Aero\AppData\Local\Temp\make_check.log:String) [Get-Content
   ], ItemNotFoundException
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
```

### Step 2b — constituents of `make check`, run separately

```
=== ruff check ===
All checks passed!
RUFF_CHECK_EXIT=0
=== ruff format --check ===
114 files already formatted
RUFF_FMT_EXIT=0
=== mypy ===
pyproject.toml: note: unused section(s): module = ['sklearn', 'tests.*']
Success: no issues found in 44 source files
MYPY_EXIT=0
```

```
PYTEST_EXIT=0
............................................................................s................................... [ 27%]
................................................................................................................ [ 54%]
................................................................................................................ [ 81%]
..........................................................................                                       [100%]
================================================== warnings summary ===================================================
..\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================================== short test summary info ===============================================
SKIPPED [1] tests\integration\test_clean_room.py:29: Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py

409 passed, 1 skipped, 1 warning in 286.36s (0:04:46)
```

Counts: passed 409, failed 0, skipped 1.

### Step 3.1–3.4 — build the TEMP copy

```
SRC=E:\discover
DST=C:\Users\Aero\AppData\Local\Temp\disc_clean

ROBOCOPY_EXIT=1
DIRS OK
```

### Step 3.6 — import origin

```
C:\Users\Aero\AppData\Local\Temp\disc_clean\backend\api\main.py
```

Starts with the TEMP copy → Step 3 proceeded.

### Step 3.7 — clean-checkout pytest

```
PYTEST_EXIT=1
=== LAST 40 LINES ===
_________________________ test_make_results_section_headings_and_dataset_names_from_manifest __________________________
tests\unit\test_make_results.py:239: in test_make_results_section_headings_and_dataset_names_from_manifest
    m_dict = json.loads((ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8"))
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
..\..\..\Programs\Python\Python311\Lib\pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
..\..\..\Programs\Python\Python311\Lib\pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\Aero\\AppData\\Local\\Temp\\disc_clean\\artifacts\\movies\\metrics.json'
___________________________________ test_make_results_minimum_sample_rule_n3_and_n9 ___________________________________
tests\unit\test_make_results.py:306: in test_make_results_minimum_sample_rule_n3_and_n9
    (ARTIFACTS_DIR / "movies" / "metrics.json").read_text(encoding="utf-8")
..\..\..\Programs\Python\Python311\Lib\pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
..\..\..\Programs\Python\Python311\Lib\pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\Aero\\AppData\\Local\\Temp\\disc_clean\\artifacts\\movies\\metrics.json'
================================================== warnings summary ===================================================
E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1
  E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/integration/test_determinism.py::test_pipeline_determinism_movies
  E:\discover\.venv\Lib\site-packages\urllib3\connectionpool.py:1129: InsecureRequestWarning: Unverified HTTPS request is being made to host 'files.grouplens.org'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================================== short test summary info ===============================================
SKIPPED [1] tests\integration\test_clean_room.py:29: Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py
SKIPPED [1] tests\integration\test_movies_gate.py:248: artifacts/movies/manifest.json does not exist yet; run make train TYPE=movies first
SKIPPED [1] tests\integration\test_movies_split_leakage.py:57: MovieLens 1M dataset not found in data/raw/movielens
SKIPPED [1] tests\integration\test_products_gate.py:251: artifacts/products directory not found
SKIPPED [1] tests\integration\test_products_split_leakage.py:25: Amazon instruments dataset not found in data/raw/amazon
SKIPPED [1] tests\integration\test_products_split_leakage.py:69: Amazon dataset not found on disk
SKIPPED [1] tests\unit\test_product_checks.py:175: artifacts/products/metrics.json not generated yet
113 failed, 290 passed, 7 skipped, 2 warnings in 118.89s (0:01:58)
=== FIRST 10 FAILED ===
```

Note: `-q` mode emits no `FAILED ...` summary lines, so the `=== FIRST 10 FAILED ===`
section was empty. The first 10 failures were derived from the per-failure traceback
headers of the same log:

```
tests\contract\test_api_cold_start.py:31: in test_cold_start_personalized_flow      [movies]
tests\contract\test_api_cold_start.py:31: in test_cold_start_personalized_flow      [products]
tests\contract\test_api_cold_start.py:31: in test_cold_start_personalized_flow      [articles]
tests\contract\test_api_cold_start.py:74: in test_cold_start_empty_history          [movies]
tests\contract\test_api_cold_start.py:74: in test_cold_start_empty_history          [products]
tests\contract\test_api_cold_start.py:74: in test_cold_start_empty_history          [articles]
tests\contract\test_api_cold_start.py:95: in test_cold_start_only_unknown_ids       [movies]
tests\contract\test_api_cold_start.py:95: in test_cold_start_only_unknown_ids       [products]
tests\contract\test_api_cold_start.py:95: in test_cold_start_only_unknown_ids       [articles]
tests\contract\test_api_cold_start.py:116: in test_cold_start_duplicate_ids_rejected
```

(next, for reference: `test_cold_start_200_and_201_entries_boundary`,
`tests\contract\test_api_metadata.py::test_health_endpoint_contract`)

Counts: passed 290, failed 113, skipped 7.

### Step 3.8 — cleanup

```
ARTIFACT_DIR removed (process-local)
ENV=
```

### Step 4.2 — probe output (first 30 lines)

```
E:\discover\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
[2026-10-26 07:30:36] [INFO] [engine.api.main] Initializing Discovery Engine API from artifacts: E:\discover\artifacts
[2026-10-26 07:30:36] [INFO] [engine.api.main] Content type 'articles' loaded successfully.
[2026-10-26 07:30:37] [INFO] [engine.api.main] Content type 'movies' loaded successfully.
[2026-10-26 07:30:38] [INFO] [engine.api.main] Content type 'products' loaded successfully.
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: GET http://testserver/v1/health "HTTP/1.1 200 OK"
HEALTH ok
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: GET http://testserver/v1/types "HTTP/1.1 200 OK"
P7 card types [('articles', 'article'), ('movies', 'movie'), ('products', 'product')]
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: POST http://testserver/v1/recommend/cold-start "HTTP/1.1 200 OK"
P1 no-signal 200 popularity
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: POST http://testserver/v1/recommend/cold-start "HTTP/1.1 200 OK"
P2 signal5 200 personalized
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1&k=50 "HTTP/1.1 200 OK"
P3 k= 50 200
[2026-10-26 07:30:38] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1&k=51 "HTTP/1.1 200 OK"
P3 k= 51 200
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1&k=100 "HTTP/1.1 200 OK"
P3 k= 100 200
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1&k=101 "HTTP/1.1 422 Unprocessable Entity"
P3 k= 101 422
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1&k=5 "HTTP/1.1 200 OK"
P4 meta keys ['positive_interactions', 'source']
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4349&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/popular?type=movies&k=10 "HTTP/1.1 200 OK"
P5 low-positive user 4349 mode popularity equals_popular False
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=3156&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=3446&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:39] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=332&k=10 "HTTP/1.1 200 OK"
```

### Step 4.2 — probe output (last 30 lines)

```
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=2385&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=5789&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1023&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4485&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=2726&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4427&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1665&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4942&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4483&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4814&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=2357&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=3646&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=751&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4885&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=3154&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=2598&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=4716&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1984&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=2379&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1507&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:45] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1552&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:46] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=1530&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:46] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=271&k=10 "HTTP/1.1 200 OK"
[2026-10-26 07:30:46] [INFO] [httpx] HTTP Request: GET http://testserver/v1/recommend?type=movies&user_id=5020&k=10 "HTTP/1.1 200 OK"
P6 ms p50 56.9 p95 129.3 max 213.9
[2026-10-26 07:30:46] [INFO] [httpx] HTTP Request: GET http://testserver/v1/users/1/profile?type=movies "HTTP/1.1 200 OK"
P8 top_categories 0
[2026-10-26 07:30:46] [INFO] [engine.api.main] Discovery Engine API shutting down.
P9 starlette 1.9.0 fastapi 0.162.0
EXIT=0
```

### Step 4.2 — probe result lines (exact, extracted from the run above)

```
HEALTH ok
P7 card types [('articles', 'article'), ('movies', 'movie'), ('products', 'product')]
P1 no-signal 200 popularity
P2 signal5 200 personalized
P3 k= 50 200
P3 k= 51 200
P3 k= 100 200
P3 k= 101 422
P4 meta keys ['positive_interactions', 'source']
P5 low-positive user 4349 mode popularity equals_popular False
P6 ms p50 56.9 p95 129.3 max 213.9
P8 top_categories 0
P9 starlette 1.9.0 fastapi 0.162.0
```

Per-line judgement:

| Line | Expected | Observed | Verdict |
|---|---|---|---|
| P1 | `personalized` | `popularity` | FAIL |
| P2 | `personalized` | `personalized` | PASS |
| P3 | `200 / 422 / 422 / 422` | `200 / 200 / 200 / 422` | FAIL |
| P4 | `model`, `artifact_version`, `latency_ms` present | `['positive_interactions', 'source']` | FAIL |
| P5 | results equal `/popular` when mode is popularity | `equals_popular False` | FAIL |
| P6 | p95 < 150 ms | p95 129.3 ms | PASS |
| P7 | `movie`, `product`, `article` | `article`, `movie`, `product` | PASS |
| P8 | ≤ 10 | 0 | PASS |
| P9 | copy | `starlette 1.9.0 fastapi 0.162.0` | PASS (copied) |

### Step 5.1 — OpenAPI check

```
[SUCCESS] OpenAPI schema at E:\discover\backend\api\openapi.json is strictly up to date.
EXIT=0
```

### Step 5.2 — `"toy"` literal search

```
backend\api\deps.py:21:    available_types = [t for t in registry.types() if t != "toy"]
backend\api\deps.py:22:    if ctype not in available_types or ctype == "toy":
backend\api\main.py:76:    available_types = [t for t in registry.types() if t != "toy"]
backend\api\main.py:78:        if content_type == "toy":
backend\api\routes\metadata.py:83:    registered_types = [t for t in registry.types() if t != "toy"]
backend\api\routes\metadata.py:124:    registered_types = [t for t in registry.types() if t != "toy"]
EXIT=
```

### Step 5.3 — `except Exception` in route modules

```
> backend\api\routes\recommend.py:190:        except Exception:
  backend\api\routes\recommend.py:191:            reason_obj = None
  backend\api\routes\recommend.py:192:

> backend\api\routes\recommend.py:307:            except Exception:
  backend\api\routes\recommend.py:308:                reason_obj = None
  backend\api\routes\recommend.py:309:
```

### Step 5.4 — MIND raw data

```
=== RESULTS.md ===
```

(no `FullName`/`Length` rows; the `Get-ChildItem` produced no output.)

Directory context:

```
Name
----
amazon
mind_deferred
movielens
```

### Step 5.5 — `docs\RESULTS.md` claim scan

```
docs\RESULTS.md:225:- **In-Memory Artifact Serving:** Precomputed `topn.parquet` lookups execute in sub-millisecond
time (<1.0 ms median), bypassing database overhead entirely.
docs\RESULTS.md:226:- **Sparse Live Scoring:** Personalized fallback and cold-start matrix multiplications in
`SarModel` (via sparse COO non-zero iteration) and `TfidfProfileModel` (via sparse CSR dot-product) comfortably beat
the 150 ms tail budget by over 50x to 100x.
docs\RESULTS.md:227:- **Memory Footprint:** Baseline process RSS remains lean (< 250 MB) with zero deep-learning
runtime overhead (no TensorFlow, PyTorch, or JVM memory footprint).
EXIT=
```
