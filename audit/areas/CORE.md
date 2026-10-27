# AREA CORE — Engine core (schema, config, registry, errors, artifacts, logging)

**Verdict:** PASS WITH FINDINGS — 2 MEDIUM, 1 LOW.

## Files read
- `backend/engine/schema.py`
- `backend/engine/config.py`
- `backend/engine/registry.py`
- `backend/engine/errors.py`
- `backend/engine/artifacts.py`
- `backend/engine/logging_utils.py`
- `backend/engine/coldstart.py`
- `backend/engine/explain.py`
- `backend/engine/configs/{movies,products,articles,toy}.yaml`

## Findings
### F-010 — Serving config reconstruction ignores two tuned parameters (MEDIUM)
`backend/engine/train.py:190-196` writes the tuned `similarity_type`, `timedecay_formula`, `time_decay_coefficient`, `positive_threshold`, and `top_neighbors_per_item` into the spec before saving artifacts.

`backend/engine/config.py:164-174` only re-applies:
- `top_neighbors_per_item` (line 165),
- `time_decay_coefficient` (lines 166-172),
- `positive_threshold` (lines 173-174).

It never re-applies `similarity_type` or `timedecay_formula`. The broad `except Exception: pass` at `config.py:175-176` also hides malformed `tuning.json`.

**Impact:** If tuning ever selects a non-default similarity type or time-decay flag, `resolve_serving_config` either (a) reconstructs the wrong config and fails the manifest hash check, marking the content type unavailable at startup, or (b) silently returns a config that differs from the model artifact. The current committed tuning files happen to select the same values as the YAML defaults, so the bug is latent rather than active.

**Disproof attempt:** I copied a mini artifact, added `best_params.similarity_type = "lift"`, and called `resolve_serving_config`. It returned `jaccard` rather than `lift`; with a manifest hash generated from a lift-trained model it would instead raise `ConfigError`. This confirms the parameter is ignored.

**Recommendation:** Apply both fields and fail loudly on malformed tuning data instead of swallowing the exception.

### F-011 — Artifact save is not atomic (MEDIUM)
`backend/engine/artifacts.py:113-118` writes Parquet files in place; `artifacts.py:121-122` writes JSON files in place; `artifacts.py:184` writes the manifest last.

**Impact:** A crash or full disk between writes leaves a mixture of old and new files. If the process dies before the new manifest is written, the old manifest remains and points at files whose checksums no longer match, so the API marks the type unavailable. There is no staging directory, rename, or rollback.

**Recommendation:** Write to a temporary sibling directory and atomically swap it into place, or write the manifest first with a generation ID and clean up incomplete generations on load.

### F-018 — Manifest verification joins unvalidated relative paths (LOW)
`backend/engine/artifacts.py:201-203` does `file_path = artifact_dir / rel_path` for every key in `manifest["files"]` without rejecting absolute paths or `..` segments.

**Impact:** A tampered manifest can make verification hash files outside the artifact directory. It is read-only and requires manifest tampering, so impact is limited, but the containment invariant is missing.

**Recommendation:** Reject absolute paths and resolve each path, then assert it is relative to `artifact_dir`.

## Positives verified
- `schema.py` uses strict Pydantic models (`extra="forbid"`), string-ID coercion, timestamp bounds, and a unified `Interaction`/`Item`/`ScoredItem` shape.
- `config.py` produces readable validation errors and a deterministic config hash; fast-mode overrides are explicit.
- `registry.py` uses decorator registration and keeps dataset/model wiring out of the API.
- `errors.py` has a clear hierarchy and actionable messages.
- `verify_artifacts` correctly detected artifact deletion, a one-byte flip, and a schema-version tamper in dynamic testing (`ArtifactCorruptError` in all three cases).
- `logging_utils.py` is small, structured, and avoids duplicate handlers.
- `coldstart.normalize_history` handles empty input, duplicates, unknown IDs, non-finite signals, and length capping.
- `explain.find_top_contributor` enforces that the reason item is in history and computes a positive contribution share.

## Uncovered / notes
- No concurrency test of `save_artifacts`; non-atomicity is a static finding.
- The artifact path-traversal issue was not exploited against a live API instance.
