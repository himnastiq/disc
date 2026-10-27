# AREA SEC — Security and dependencies

**Verdict:** FAIL WITH FINDINGS — 1 HIGH, 2 MEDIUM.

## Files read
- `backend/api/security.py`
- `backend/api/errors.py`
- `backend/api/main.py`
- `backend/scripts/fetch_data.py`
- `backend/engine/adapters/amazon.py`
- `backend/pyproject.toml`
- `.github/workflows/ci.yml`
- secret-pattern scan over the repository

## Findings
### F-001 — `eval()` on downloaded Amazon data (HIGH)
`backend/engine/adapters/amazon.py:51` executes a downloaded line when JSON and `ast.literal_eval` fail. `fetch_data.py:98-110` verifies only byte count, not content integrity. See AREA ADAP for the full analysis. This is the highest-risk issue in the repository.

### F-012 — No dependency lock file (MEDIUM)
`backend/pyproject.toml:19-46` uses lower bounds only; no lock file exists. See AREA REPO. For security, this also means a compromised or breaking transitive release can enter CI without review.

### F-013 — CI excludes the security-adjacent real-data leakage/determinism tests (MEDIUM)
`.github/workflows/ci.yml:54` deselects 42 tests. See AREA TEST.

## Positives verified
- `api/security.py:17-47` compares API keys with `hmac.compare_digest` on encoded bytes, handles `None`, and returns `False` on any exception. Dynamic probes: missing key → 401, wrong key → 401, valid non-ASCII key → 200.
- `SecurityMiddleware` enforces a 1 MB body limit for both `Content-Length` and streamed/chunked bodies (`security.py:132-181`), and exempts only `/docs`, `/redoc`, `/openapi.json`, and CORS preflight.
- CORS origins come from `CORS_ORIGINS` (`main.py:46`); no wildcard default.
- Search query is capped at 100 characters; path/type traversal is blocked by registry membership (`deps.py:20-25`); unknown types return 404.
- Secret-pattern grep found no credentials/keys. The only `SECRET_LIKE` hit is a test literal in `backend/tests/unit/test_api_security.py:102`.
- `pip show recommenders` fails; `find_spec("recommenders")` is `None`.
- No debug stack traces are returned; the catch-all handler logs and returns a generic 500.

## Uncovered / notes
- `pip-audit --local` could not complete: PyPI connection timed out. **Dependency vulnerability status is unknown.** This must be rerun with network access before a production claim.
- I did not attempt to exploit the `eval()` path with a crafted file, to avoid executing code; the reachability is established statically.
- No TLS/network security review of the download URLs beyond noting the absence of checksums and the `--insecure` opt-out.
