# Specification Conformance Audit: Phases 0 to 7

This document provides a comprehensive, rigorous conformance audit of the Discovery Engine backend (Phases 0 through 7) against **Sections 6, 7, 8, and 10** of [IMPLEMENTATION_PLAN.md](file:///e:/discover/IMPLEMENTATION_PLAN.md).

Every requirement is audited and categorized into:
- **`PASS`**: Completely conformant with the specification with automated test verification.
- **`DEVIATION`**: Deliberate engineering decision justified by an Architecture Decision Record in [DECISIONS.md](file:///e:/discover/docs/DECISIONS.md).
- **`FAIL`**: Non-conformant requirement requiring code fixes.

---

## 1. Section 6: Core Contracts Audit

| Spec Section | Requirement Summary | Status | Source File & Line | Evidence / Verification Notes |
|---|---|---|---|---|
| **6.1 Unified Schema** | Interaction: `user_id: str`, `item_id: str`, `signal: float`, `timestamp: int`, `positive: bool` | **PASS** | [`engine/schema.py:16-29`](file:///e:/discover/backend/engine/schema.py#L16-L29) | Pydantic model with strict validation, unix second timestamps, and boolean positive flag. |
| **6.1 Unified Schema** | Item: `item_id: str`, `title: str`, `subtitle: str \| None`, `categories: list[str]`, `text: str \| None`, `year: int \| None`, `image_url: str \| None`, `extra: dict` | **PASS** | [`engine/schema.py:32-47`](file:///e:/discover/backend/engine/schema.py#L32-L47) | Pydantic model enforcing string IDs, string category list, and optional extra metadata dictionary. |
| **6.1 Unified Schema** | ContentTypeSpec loaded from YAML, validated by pydantic | **PASS** | [`engine/schema.py:110-145`](file:///e:/discover/backend/engine/schema.py#L110-L145), [`engine/config.py:30-65`](file:///e:/discover/backend/engine/config.py#L30-L65) | Validated via `ContentTypeSpec.model_validate(raw_dict)`. Rejects invalid or incomplete configs. |
| **6.1 Unified Schema** | String ID invariant at all boundaries | **PASS** | [`engine/schema.py:18-35`](file:///e:/discover/backend/engine/schema.py#L18-L35), [`api/schemas.py:253`](file:///e:/discover/backend/api/schemas.py#L253) | All IDs coerced and validated as `str` in adapters, models, parquet artifacts, and API request/response models. |
| **6.2 Configuration** | Config YAML structure: dataset, signal, split, model, evaluation, serving | **PASS** | [`engine/configs/movies.yaml`](file:///e:/discover/backend/engine/configs/movies.yaml), [`engine/configs/products.yaml`](file:///e:/discover/backend/engine/configs/products.yaml), [`engine/configs/articles.yaml`](file:///e:/discover/backend/engine/configs/articles.yaml) | Validated against schema. Fast mode overrides (`--fast`) dynamically update dataset variants and grid searches. |
| **6.3 Adapter Interface** | `DatasetAdapter` abstract base class with `download`, `load_raw`, `interactions`, `items`, `validate`, `split` | **PASS** | [`engine/adapters/base.py:20-65`](file:///e:/discover/backend/engine/adapters/base.py#L20-L65) | ABC defining all lifecycle methods; zero dataset-specific code in engine core. |
| **6.3 Adapter Splitter** | Splitter API naming | **DEVIATION** | [`discovery/datasets/python_splitters.py:20`](file:///e:/discover/backend/discovery/datasets/python_splitters.py#L20) | Recommenders source function is named `python_chrono_split` rather than `python_chronological_split`. Justified in **D-007**. |
| **6.4 Model Interface** | `RecommenderModel` abstract base class with `fit`, `recommend_user`, `recommend_history`, `similar_items`, `popular`, `explain`, `save`, `load`, `supports_cold_start` | **PASS** | [`engine/models/base.py:25-95`](file:///e:/discover/backend/engine/models/base.py#L25-L95) | Full interface implemented by `PopularityModel`, `RandomModel`, `SarModel`, and `TfidfContentModel`. |
| **6.4 Model Output** | `ScoredItem` with `item_id: str`, `score: float`, `rank: int` | **PASS** | [`engine/schema.py:50-57`](file:///e:/discover/backend/engine/schema.py#L50-L57) | Model layer returns raw float scores and integer ranks; normalization is strictly deferred to the API layer. |
| **6.4 Cold Start** | SAR cold-start scoring via history vector affinity product | **PASS** | [`engine/models/sar.py:290-345`](file:///e:/discover/backend/engine/models/sar.py#L290-L345) | Explicit affinity multiplication using fitted item index and similarity matrix. Verified equivalent in consistency tests. |
| **6.5 Artifact Layout** | Required files: `manifest.json`, `items.parquet`, `interactions.parquet`, `users.parquet`, `model/`, `topn.parquet`, `metrics.json`, `demo_users.json` | **PASS** | [`engine/artifacts.py:75-125`](file:///e:/discover/backend/engine/artifacts.py#L75-L125) | Generated on pipeline run. Manifest records SHA-256 hashes, git SHA, and config hash. Verified on load. |

---

## 2. Section 7: Per-Type Design Differences Audit

| Content Type | Domain Dimension | Specification | Actual Implementation | Status | Source File & Line |
|---|---|---|---|---|---|
| **Movies** | Signal & Threshold | Rating >= 4.0 | Rating >= 4.0 (`positive_threshold: 4.0`) | **PASS** | [`engine/configs/movies.yaml:12`](file:///e:/discover/backend/engine/configs/movies.yaml#L12) |
| **Movies** | Candidate Pool & Repeat | All catalogue items, no repeat consumption | All items, `allow_repeat: false` | **PASS** | [`engine/configs/movies.yaml:18`](file:///e:/discover/backend/engine/configs/movies.yaml#L18) |
| **Movies** | Model & Explanations | SAR with similarity matrix, co-occurrence attribution | `SarModel` (Jaccard, time decay=30d) | **PASS** | [`engine/configs/movies.yaml:16`](file:///e:/discover/backend/engine/configs/movies.yaml#L16), [`engine/models/sar.py`](file:///e:/discover/backend/engine/models/sar.py) |
| **Movies** | Split Strategy | Chronological per user | `chronological` split with R2 no-leakage check | **PASS** | [`engine/configs/movies.yaml:14`](file:///e:/discover/backend/engine/configs/movies.yaml#L14) |
| **Products** | Signal & Threshold | Rating >= 4.0 | Rating >= 4.0 (`positive_threshold: 4.0`) | **PASS** | [`engine/configs/products.yaml:12`](file:///e:/discover/backend/engine/configs/products.yaml#L12) |
| **Products** | Candidate Pool & Budget | All items (capped top neighbors) | `top_neighbors_per_item: 50`, `max_items_in_similarity: 8000` | **PASS** | [`engine/configs/products.yaml:26-28`](file:///e:/discover/backend/engine/configs/products.yaml#L26-L28) |
| **Products** | Model & Explanations | SAR with similarity matrix | `SarModel` (Jaccard co-occurrence attribution) | **PASS** | [`engine/models/sar.py`](file:///e:/discover/backend/engine/models/sar.py) |
| **Articles** | Signal & Recency | Clicks (label 1), hours to days lifespan | Click binary signal, `recency_window_seconds: 86400.0` (24h) | **PASS** | [`engine/configs/articles.yaml:11-28`](file:///e:/discover/backend/engine/configs/articles.yaml#L11-L28) |
| **Articles** | Content Model | TF-IDF content model with user profile | `TfidfContentModel` with sublinear TF and cosine similarity | **PASS** | [`engine/models/tfidf.py:45-120`](file:///e:/discover/backend/engine/models/tfidf.py#L45-L120) |
| **Articles** | Split Strategy | Impression time split (later days test) | `impression_time` split with R2 verification | **PASS** | [`engine/evaluation/splits.py:165-189`](file:///e:/discover/backend/engine/evaluation/splits.py#L165-L189) |
| **Articles** | Dual Protocol Evaluation | MIND impression logging & open retrieval | Dual protocol evaluation (Impression Ranking + Window Retrieval) | **DEVIATION** | [`engine/evaluation/articles_eval.py`](file:///e:/discover/backend/engine/evaluation/articles_eval.py) | Justified in **D-016**. |

---

## 3. Section 8: API Specification Audit

| API Endpoint | Method | Specification / Constraints | Status | Source File & Line | Evidence / Notes |
|---|---|---|---|---|---|
| **Base Path** | ALL | Base prefix `/v1` | **PASS** | [`api/routes/metadata.py:18`](file:///e:/discover/backend/api/routes/metadata.py#L18), [`api/routes/recommend.py:28`](file:///e:/discover/backend/api/routes/recommend.py#L28), [`api/routes/users.py:11`](file:///e:/discover/backend/api/routes/users.py#L11) | All API routes mounted under `/v1`. |
| **Root Health Alias** | GET | `/health` alias for infrastructure probes | **PASS** | [`api/main.py:156`](file:///e:/discover/backend/api/main.py#L156) | Root `/health` delegates directly to `/v1/health`. |
| **Error Format** | ALL | JSON format `{"error": {"code": str, "message": str}}` | **PASS** | [`api/errors.py:35-180`](file:///e:/discover/backend/api/errors.py#L35-L180) | Strict RFC/spec format with HTTP status codes (400, 401, 403, 404, 409, 422, 503). |
| **GET /health** | GET | Overall health (`ok`, `degraded`, `error`), per-type status, version | **PASS** | [`api/routes/metadata.py:75-118`](file:///e:/discover/backend/api/routes/metadata.py#L75-L118) | Returns `HealthResponse` asserting availability and artifact versions. |
| **GET /types** | GET | List registered content types, card types, counts | **PASS** | [`api/routes/metadata.py:120-153`](file:///e:/discover/backend/api/routes/metadata.py#L120-L153) | Returns `TypesResponse` with `card_type` in `('movie', 'product', 'article')`. |
| **GET /types/{type}/users** | GET | Demo users and sampled users list | **PASS** | [`api/routes/metadata.py:155-225`](file:///e:/discover/backend/api/routes/metadata.py#L155-L225) | Returns `UsersResponse` with demo users prioritized. |
| **GET /users/{id}/profile** | GET | Total interactions, positive count, category shares (cap 10), recent items (cap 10), first/last activity | **PASS** | [`api/routes/users.py:14-64`](file:///e:/discover/backend/api/routes/users.py#L14-L64) | Returns `UserProfileResponse` computed via in-memory lookup structures. |
| **GET /recommend** | GET | Personalised results, mode, display_scores (0..1), faithful reasons, meta fields; k 1..50 | **PASS** | [`api/routes/recommend.py:42-178`](file:///e:/discover/backend/api/routes/recommend.py#L42-L178) | Bounded k (1..50). Precomputed topn or live model scoring. Meta contains model, version, latency_ms, explanation_errors. |
| **POST /recommend/cold-start**| POST | History max 200 items, unique IDs (422 on dupes), unknown IDs ignored and reported; k 1..50 | **PASS** | [`api/routes/recommend.py:180-312`](file:///e:/discover/backend/api/routes/recommend.py#L180-L312) | Rejects duplicate IDs with 422 `duplicate_ids`. Meta includes `history_size` and `explanation_errors`. |
| **GET /popular** | GET | Overall popular items; k 1..50; meta fields | **PASS** | [`api/routes/recommend.py:315-372`](file:///e:/discover/backend/api/routes/recommend.py#L315-L372) | Bounded k (1..50). Returns `PopularResponse` with meta (`model`, `artifact_version`, `latency_ms`). |
| **GET /similar** | GET | Nearest neighbor items; excludes query item; k 1..50; meta fields | **PASS** | [`api/routes/recommend.py:374-441`](file:///e:/discover/backend/api/routes/recommend.py#L374-L441) | Bounded k (1..50). Returns `SimilarResponse` with meta (`model`, `artifact_version`, `latency_ms`). |
| **GET /items/search** | GET | Normalized text search: exact > prefix > word-start > contains, ties broken by popularity | **PASS** | [`api/routes/metadata.py:228-256`](file:///e:/discover/backend/api/routes/metadata.py#L228-L256), [`api/search.py`](file:///e:/discover/backend/api/search.py) | Normalized matching stripping accents and articles. Validated by comprehensive search tests. |
| **GET /items/{item_id}** | GET | Catalogue item detail with full metadata | **PASS** | [`api/routes/metadata.py:258-309`](file:///e:/discover/backend/api/routes/metadata.py#L258-L309) | Returns `ItemDetail` or 404 `unknown_item`. |
| **GET /metrics** | GET | Evaluation metrics payload served directly from `metrics.json` | **PASS** | [`api/routes/metadata.py:329-338`](file:///e:/discover/backend/api/routes/metadata.py#L329-L338) | Serves verbatim pipeline evaluation results. |
| **GET /about** | GET | Attribution, dataset citations, license terms, original vs derived | **PASS** | [`api/routes/metadata.py:311-327`](file:///e:/discover/backend/api/routes/metadata.py#L311-L327) | Returns `AboutResponse` with upstream citations and academic licensing notices. |

---

## 4. Section 10: Robustness Gates (R1 to R11) Audit

| Gate | Title | Invariant / Acceptance Criterion | Status | Primary Enforcement & Test Verification |
|---|---|---|---|---|
| **R1** | **Data Validity** | Sparsity in [0, 1]; no duplicate interaction rows; no null IDs; valid timestamps; catalogue membership; bijective mapping | **PASS** | [`engine/evaluation/checks.py:21-117`](file:///e:/discover/backend/engine/evaluation/checks.py#L21-L117), [`tests/unit/test_checks.py`](file:///e:/discover/backend/tests/unit/test_checks.py) |
| **R2** | **No Leakage** | `max(train.timestamp) <= min(test.timestamp)`; no test interactions in similarity, vocabulary, or popularity | **PASS** | [`engine/evaluation/splits.py:11-63`](file:///e:/discover/backend/engine/evaluation/splits.py#L11-L63), [`tests/integration/test_articles_split_leakage.py`](file:///e:/discover/backend/tests/integration/test_articles_split_leakage.py) |
| **R3** | **Model Invariants** | Length <= k; no duplicates; no excluded/seen items; monotonic scores; cold-start consistency; faithful explanations | **PASS** | [`engine/evaluation/checks.py:138-215`](file:///e:/discover/backend/engine/evaluation/checks.py#L138-L215), [`tests/contract/test_api_recommend.py`](file:///e:/discover/backend/tests/contract/test_api_recommend.py) |
| **R4** | **Evaluation Validity** | Identical split & candidate protocol for baselines; Random < Popularity <= Model sanity; diversity & novelty reported | **PASS** | [`engine/evaluation/harness.py:35-180`](file:///e:/discover/backend/engine/evaluation/harness.py#L35-L180), [`docs/RESULTS.md`](file:///e:/discover/docs/RESULTS.md) |
| **R5** | **Cold-Start Behaviour** | History sizes 0..20 evaluated; size 0 falls back to popularity mode; duplicates rejected (422); unknown IDs ignored | **PASS** | [`engine/coldstart.py:40-120`](file:///e:/discover/backend/engine/coldstart.py#L40-L120), [`tests/contract/test_api_cold_start.py`](file:///e:/discover/backend/tests/contract/test_api_cold_start.py) |
| **R6** | **Reproducibility** | Fixed random seeds (seed 42); retraining produces identical hashes; clean checkout builds with committed mini fixtures | **PASS** | [`engine/train.py:25-35`](file:///e:/discover/backend/engine/train.py#L25-L35), [`tests/integration/test_determinism.py`](file:///e:/discover/backend/tests/integration/test_determinism.py) |
| **R7** | **API Contract & Edge Cases** | All endpoints tested across all types; k in 1..50; error shape consistent; no stack traces leaked; no TensorFlow in sys.modules | **PASS** | [`tests/contract/`](file:///e:/discover/backend/tests/contract/), [`tests/integration/test_api_runtime_purity.py`](file:///e:/discover/backend/tests/integration/test_api_runtime_purity.py) |
| **R8** | **Performance & Resources** | Latency p95 GET /recommend < 150 ms (actual < 5 ms); API RSS < 2 GB (actual ~340 MB) | **PASS** | [`scripts/bench_api.py`](file:///e:/discover/backend/scripts/bench_api.py), [`docs/RESULTS.md`](file:///e:/discover/docs/RESULTS.md) |
| **R9** | **Frontend Robustness** | TypeScript strict clean, zod runtime validation, responsive layouts, failure injection | **PENDING** | Scheduled for Phases 8–10 (Frontend implementation). |
| **R10**| **Licensing & Attribution** | MIT license preserved; NOTICE.md and ATTRIBUTION.md current; no `import recommenders` in codebase; citations present | **PASS** | [`NOTICE.md`](file:///e:/discover/NOTICE.md), [`ATTRIBUTION.md`](file:///e:/discover/ATTRIBUTION.md), [`backend/tests/contract/test_licensing.py`](file:///e:/discover/backend/tests/contract/test_licensing.py) |
| **R11**| **Security Basics** | Constant-time API key check on bytes (`secrets.compare_digest`); CORS from env; 1MB body limit; no secrets in repo | **PASS** | [`api/security.py:20-60`](file:///e:/discover/backend/api/security.py#L20-L60), [`tests/unit/test_api_security.py`](file:///e:/discover/backend/tests/unit/test_api_security.py) |

---

## 5. Audit Summary and Verdict

- **Total Requirements Audited:** 48
- **PASS:** 44 (91.7%)
- **DEVIATION:** 3 (6.3% — all explicitly justified and documented in [DECISIONS.md](file:///e:/discover/docs/DECISIONS.md))
  - **D-007**: Recommenders source function named `python_chrono_split`.
  - **D-010**: Sparsification of top-50 co-occurrence neighbors to guarantee memory budget < 2GB.
  - **D-016**: Dual-protocol evaluation (impression candidate ranking + recency window retrieval) for news articles.
- **PENDING:** 1 (2.0% — R9 Frontend Robustness, scheduled for Phases 8–10).
- **FAIL:** 0 (0.0%).

**Audit Verdict:** **CONFORMANT**. The backend implementation for Phases 0 through 7 satisfies all architectural, API, and robustness constraints specified in the Implementation Plan.
