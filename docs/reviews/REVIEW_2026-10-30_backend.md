# Backend Review - 2026-10-30

## 1. Summary Table

| # | Command / Step | Verdict | Summary / Notes |
|---|---|---|---|
| 1 | `git status --short ; git rev-parse HEAD ; git log --all --oneline -- "artifacts_backup*"` | **PASS** | Working tree inspected; HEAD at `29ca849119956170b94ff1ee31725524ecf9e734`; git hygiene commits present. |
| 2 | `.\.venv\Scripts\python.exe tools\check.py` | **PASS** | Full QA check passed: Ruff lint/format, mypy, conformance, git hygiene, pytest (`not real_data`), frontend lint, tsc, vitest, and secret checks all passed. |
| 3 | `cd backend; ..\.venv\Scripts\python.exe -m pytest tests -m real_data -q -rs` | **FAIL** | 46 passed, 2 failed out of 48 selected tests. Failures related to missing `product_specific_checks` in `artifacts/products/metrics.json`. |
| 4 | `cd backend; ..\.venv\Scripts\python.exe ..\docs\reviews\probe_real.py` | **NOT BUILT YET** | File `docs\reviews\probe_real.py` does not exist on disk. |
| 5 | `cd backend; ..\.venv\Scripts\python.exe -m pytest tests\unit\test_tfidf_scoring_equivalence.py tests\unit\test_conformance.py -q` | **PASS** | 13 passed in 6.82s. |
| 6 | Clean clone simulation (own venv, git clone, pip install, pytest not real_data, check_conformance) | **PASS** | Fresh clone in temp directory passed 447 tests (1 skipped), conformance check passed. |
| 7 | `Select-String` patterns for FIX-46 in `sar.py` and `test_sar_consistency.py` | **PASS** | Line numbers located: `sar.py` lines 286, 290; `test_sar_consistency.py` lines 61, 124, 183, 251. |

---

## 2. Command Executions & Exact Outputs

### Command 1
```powershell
git status --short ; git rev-parse HEAD ; git log --all --oneline -- "artifacts_backup*"
```
**Verdict:** PASS  
**Exact Output:**
```
 M backend/engine/models/sar.py
 M backend/tests/fixtures/golden_movies_100k.json
 M docs/RESULTS.md
 M docs/figures/cold_start_curves.png
 M frontend/AGENTS.md
 M frontend/app/globals.css
 M frontend/app/layout.tsx
 M frontend/app/providers.tsx
 M frontend/components/shell/AppFooter.tsx
 M frontend/components/shell/AppHeader.tsx
 M frontend/components/shell/TabNavigation.tsx
 M frontend/lib/hooks/useUrlState.ts
?? design.md
?? frontend/components/shell/TypeSwitcher.tsx
?? frontend/components/shell/UserSelect.tsx
?? frontend/tests/unit/typeSwitcher.test.tsx
?? frontend/tests/unit/userSelect.test.tsx
?? tools/openapi.json
29ca849119956170b94ff1ee31725524ecf9e734
72d6d52 FIX-53: add tools/check_tracked_files.py, enforce git hygiene, and remove tracked backup artifacts
b20fb7e chore: remove audit workspace, artifact backups, and temporary reviews; update .gitignore
deff867 Audit and Review
```

---

### Command 2
```powershell
.\.venv\Scripts\python.exe tools\check.py
```
**Verdict:** PASS  
**Exact Output (Last 25 lines):**
```
========================================================
RUNNING: Frontend Type Checker (tsc)
COMMAND: npm.cmd run type-check
CWD:     E:\discover\frontend
========================================================
[PASSED]  Frontend Type Checker (tsc)

========================================================
RUNNING: Frontend Vitest Suite
COMMAND: npm.cmd run test
CWD:     E:\discover\frontend
========================================================
[PASSED]  Frontend Vitest Suite

========================================================
RUNNING: Frontend Secret Leakage Check
COMMAND: npm.cmd run check-secrets
CWD:     E:\discover\frontend
========================================================
[PASSED]  Frontend Secret Leakage Check

========================================================
[SUCCESS] All checks passed successfully.
========================================================
```

---

### Command 3
```powershell
cd backend; ..\.venv\Scripts\python.exe -m pytest tests -m real_data -q -rs
```
**Verdict:** FAIL  
**Summary Line:**
```
2 failed, 46 passed, 448 deselected, 1 warning in 1119.30s (0:18:39)
```
**Failed Test Names:**
1. `tests/integration/test_products_gate.py::test_gate_real_products_artifacts_integrity`
2. `tests/unit/test_product_checks.py::test_real_products_artifacts_contain_valid_checks`

**Failure Details (Exact Output):**
```
================================== FAILURES ===================================
_________________ test_gate_real_products_artifacts_integrity _________________

    @pytest.mark.integration
    @pytest.mark.real_data
    def test_gate_real_products_artifacts_integrity() -> None:
        """RITUAL 6: Verify real products artifacts pass cryptographic verification and gate checks."""
        artifacts_dir = REPO_ROOT / "artifacts" / "products"
        if not artifacts_dir.exists():
            pytest.skip("artifacts/products directory not found")
    
        # 1. Cryptographic manifest verification
        manifest = verify_artifacts(artifacts_dir)
        assert manifest["content_type"] == "products"
        assert manifest["model_name"] == "sar"
    
        # 2. Load artifacts
        loaded = load_artifacts(artifacts_dir)
        assert not loaded.items.empty
        assert not loaded.interactions.empty
        assert not loaded.users.empty
    
        # 3. R1 report verification on real interactions and items
        check_r1_data_validity(loaded.interactions, loaded.items)
    
        # 4. R4 metrics verification
        metrics = loaded.metrics
        check_r4_evaluation_validity(metrics)
        assert metrics["content_type"] == "products"
        assert metrics["sanity_checks"]["model_beats_popularity"] is True
    
        # 5. Product-specific checks verification (P4.6)
>       assert "product_specific_checks" in metrics
E       AssertionError: assert 'product_specific_checks' in {'protocol': {'split_strategy': 'chronological', 'split_ratio': 0.8, 'allow_repeat': False, 'positive_threshold': 4.0,...bbedbc7edb96f8ecb431e03c8565ebe40e816ed29fbf2eed8cfb3971c', 'git_sha': '5ee8745472c6ff2980308baff6822f40bc9d1fdf', ...}

tests\integration\test_products_gate.py:275: AssertionError
______________ test_real_products_artifacts_contain_valid_checks ______________

    @pytest.mark.real_data
    def test_real_products_artifacts_contain_valid_checks() -> None:
        """Verify saved products metrics.json contains product_specific_checks meeting all gates."""
        import json
    
        metrics_p = REPO_ROOT / "artifacts" / "products" / "metrics.json"
        if not metrics_p.exists():
            pytest.skip("artifacts/products/metrics.json not generated yet")
    
        metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
>       assert "product_specific_checks" in metrics, (
            "Missing product_specific_checks key in metrics.json"
        )
E       AssertionError: Missing product_specific_checks key in metrics.json
E       assert 'product_specific_checks' in {'protocol': {'split_strategy': 'chronological', 'split_ratio': 0.8, 'allow_repeat': False, 'positive_threshold': 4.0,...bbedbc7edb96f8ecb431e03c8565ebe40e816ed29fbf2eed8cfb3971c', 'git_sha': '5ee8745472c6ff2980308baff6822f40bc9d1fdf', ...}

tests\unit\test_product_checks.py:179: AssertionError
```

---

### Command 4
```powershell
cd backend; ..\.venv\Scripts\python.exe ..\docs\reviews\probe_real.py
```
**Verdict:** NOT BUILT YET  
**Exact Output:**
```
C:\Users\Aero\AppData\Local\Programs\Python\Python311\python.exe: can't open file 'E:\\discover\\docs\\reviews\\probe_real.py': [Errno 2] No such file or directory
```

---

### Command 5
```powershell
cd backend; ..\.venv\Scripts\python.exe -m pytest tests\unit\test_tfidf_scoring_equivalence.py tests\unit\test_conformance.py -q
```
**Verdict:** PASS  
**Exact Output:**
```
.............                                                            [100%]
13 passed in 6.82s
```

---

### Command 6
```powershell
$d="$env:TEMP\ci_sim_b"; Remove-Item $d -Recurse -Force -ErrorAction SilentlyContinue
git clone file:///E:/discover $d; python -m venv "$d\venv"
& "$d\venv\Scripts\python.exe" -m pip install -q -e "$d\backend[core,dev]"
cd $d\backend; & "$d\venv\Scripts\python.exe" -m pytest tests -q -rs -m "not real_data" --maxfail=20
& "$d\venv\Scripts\python.exe" ..\tools\check_conformance.py --check
```
**Verdict:** PASS  
**Exact Output:**
```
Cloning into 'C:\Users\Aero\AppData\Local\Temp\ci_sim_b'...

[notice] A new release of pip is available: 23.2.1 -> 26.2.2
[notice] To update, run: C:\Users\Aero\AppData\Local\Temp\ci_sim_b\venv\Scripts\python.exe -m pip install --upgrade pip
........................................................................ [ 16%]
.............................s.......................................... [ 32%]
........................................................................ [ 48%]
........................................................................ [ 64%]
........................................................................ [ 80%]
........................................................................ [ 96%]
................                                                         [100%]
============================== warnings summary ===============================
..\venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\Aero\AppData\Local\Temp\ci_sim_b\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
SKIPPED [1] tests\integration\test_clean_room.py:29: Clean-room rebuild takes ~7.5m; run with RUN_CLEAN_ROOM=1 or tools/clean_room_rebuild.py
447 passed, 1 skipped, 48 deselected, 1 warning in 77.24s (0:01:17)
Conformance check passed: docs/CONFORMANCE.md is up to date.
```

---

### Command 7
```powershell
Select-String -Path backend\engine\models\sar.py -Pattern "FIX-46"
Select-String -Path backend\tests\integration\test_sar_consistency.py -Pattern "positive_threshold = 0.0"
```
**Verdict:** PASS  
**Exact Output:**
```
backend\engine\models\sar.py:286:        # Still exclude all history items from results (FIX-46)
backend\engine\models\sar.py:290:        # Build affinity sparse row vector using only evidence with signal >= positive_threshold (FIX-46)
backend\tests\integration\test_sar_consistency.py:61:    spec.signal.positive_threshold = 0.0
backend\tests\integration\test_sar_consistency.py:124:    spec.signal.positive_threshold = 0.0
backend\tests\integration\test_sar_consistency.py:183:    spec.signal.positive_threshold = 0.0
backend\tests\integration\test_sar_consistency.py:251:    spec.signal.positive_threshold = 0.0
```

---

## 3. Problems (Exact Output)

### Problem 1: Real Data Product Gate Failures (Command 3)
In `artifacts/products/metrics.json`, the expected key `product_specific_checks` is absent:
```
tests\integration\test_products_gate.py:275: AssertionError: assert 'product_specific_checks' in metrics
tests\unit\test_product_checks.py:179: AssertionError: Missing product_specific_checks key in metrics.json
```

### Problem 2: Missing probe script (Command 4)
```
C:\Users\Aero\AppData\Local\Programs\Python\Python311\python.exe: can't open file 'E:\\discover\\docs\\reviews\\probe_real.py': [Errno 2] No such file or directory
```
The file `probe_real.py` was removed in commit `b20fb7e` (`chore: remove audit workspace, artifact backups, and temporary reviews; update .gitignore`).

---

## 4. Unsure Items

None. All checks executed deterministically, with distinct verdicts matching system specifications.

