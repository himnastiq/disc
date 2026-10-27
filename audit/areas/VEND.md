# AREA VEND — Vendored `backend/discovery/` package

**Verdict:** PASS — no findings.

## Files read
- `backend/discovery/LICENSE`
- `backend/discovery/NOTICE.md`
- `docs/ATTRIBUTION.md`
- `docs/VENDORED_FILES.md`
- `docs/vendored_modules.txt`
- `tools/vendored_manifest.py`
- `backend/tests/unit/test_vendored_manifest.py`
- `backend/tests/unit/test_vendored_imports.py`
- `backend/tests/unit/test_vendored_smoke.py`
- file tree of `backend/discovery/`

## Evidence
- Vendored source is identified as Recommenders `1.2.1`, tag `51b1451f28ffea99df38e833441ee45ca09ba3a9`, MIT, in `backend/discovery/NOTICE.md` and `docs/ATTRIBUTION.md`.
- Original MIT text is preserved at `backend/discovery/LICENSE`.
- `tools/vendored_manifest.py --check` passed and reports 22 vendored files; `docs/VENDORED_FILES.md` is the generated manifest.
- `pip show recommenders` fails and `importlib.util.find_spec("recommenders")` is `None`; P1.8 holds.
- `grep -rniE "import recommenders|from recommenders" backend/` returns no production import.
- Runtime purity tests assert `tensorflow`, `torch`, `pyspark`, and `cornac` are not imported by the API or vendored modules.
- Compatibility patches (lazy notebook/NLTK/BERT imports, optional `pandera`, NumPy 2.0 `np.nan`, TLS verification) are documented in `NOTICE.md`.

## Assessment
The vendoring is unusually well documented: license, source tag, trimming rationale, modification log, checksum manifest, import-purity tests, and smoke tests are all present. I found no copied file outside the declared subset and no lingering `recommenders` import.

## Uncovered / notes
- I did not independently diff the vendored files against upstream Recommenders 1.2.1 because the package is not installed and the environment has no reliable PyPI access. Provenance is therefore verified by the project’s own manifest and notices, not by an independent upstream comparison.
- `ruff` and `mypy` intentionally exclude/ignore `discovery/`; defects in vendored code would not be caught by project linting.
