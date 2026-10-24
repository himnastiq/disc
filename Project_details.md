# Discovery Engine: Adaptive Content Recommendation Engine
## Implementation Plan (single source of truth for the coding agent)

> **Read this whole file section by section before writing any code.** Sections 0 to 3 are mandatory reading at the start of every session. You may be one of several agent sessions running on different accounts, so this file and the git history are the only shared memory.

---

## 0. Agent operating rules (READ FIRST, EVERY SESSION)

1. **This file is the source of truth.** At the start of every session: read sections 0 to 3, the Progress Dashboard, and the last 3 entries of the Session Log (end of file). Then continue from the first unfinished task of the lowest-numbered unfinished phase.
2. **Status markers** (use exactly these):
   - `[ ]` not started
   - `[~]` in progress (add a one-line note under it saying what is done and what remains)
   - `[x]` done (acceptance criteria met AND tests pass)
   - `[!]` blocked (add a note saying why and what the human must do; then move on to a task that does not depend on it)
3. **After every task:** update its marker, run `python tools/progress.py` (created in task P0.6; until then, update the dashboard by hand), and make a git commit whose message starts with the task ID, e.g. `P3.5: SAR wrapper with cold-start scoring`.
4. **Never tick a task whose tests fail.** Never delete, skip, or weaken a test to make something pass. If a test is wrong, fix it and explain why in the Session Log.
5. **No fabricated results.** Every number shown anywhere (README, UI, RESULTS.md) must come from a file produced by the pipeline (`artifacts/<type>/metrics.json`). No placeholder or invented metrics, ever. If something cannot be computed, mark it `[!]` and say why.
6. **Verify library APIs against the real source.** This plan names Recommenders classes and functions from memory (for example `SAR`, `TfidfRecommender`, `python_chronological_split`). Names or signatures may differ in the version you vendor. Read the source before using it and adjust. Record any difference in `docs/DECISIONS.md`.
7. **Stay in scope.** Do not add features that are not in this plan without writing a decision entry in `docs/DECISIONS.md`. Optional work lives only in Phase 12 and starts only after Phases 0 to 11 are complete.
8. **Robustness is the main goal of this project.** After every phase you must run the Phase Gate (section 10) and record the results in the Session Log. Recommendation quality and correctness matter more than UI polish. See section 10 for the "break your own work" ritual.
9. **Ask the human only for:** manual dataset downloads, API keys, and tasks marked `HUMAN`. For everything else make a reasonable decision, document it, and continue.
10. **End of session / low quota protocol:** stop starting new tasks when you suspect quota is running low. Finish or cleanly revert the current task, make sure the working tree builds and tests pass, commit, mark unfinished tasks `[~]` with notes, and append a Session Log entry using the template at the end of this file.
11. **Order of work is fixed:** backend recommendation engine first (Phases 0 to 7), frontend second (Phases 8 to 10), documentation and showcase prep (Phase 11), optional extras last (Phase 12).
12. **Every phase must end with something that runs.** If the project is stopped after any phase, there must be a working, documented state to demonstrate.

---

## Progress Dashboard

> Auto-updated by `python tools/progress.py`. Counts only `[x]` tasks inside the `PHASE` sections. Phase 12 is optional, so the project is complete at 100% of Phases 0 to 11 even if the overall bar is lower. Do not edit between the markers by hand once the script exists.

<!-- PROGRESS:START -->
| Phase | Name | Done | In progress | Blocked | Total | % |
|---|---|---|---|---|---|---|
| 0 | Scaffolding and tooling | 0 | 0 | 0 | 11 | 0% |
| 1 | Vendor, trim, and rename Recommenders into `discovery` | 0 | 0 | 0 | 9 | 0% |
| 2 | Core engine abstractions | 0 | 0 | 0 | 13 | 0% |
| 3 | Movies pipeline (MovieLens + SAR) | 0 | 0 | 0 | 13 | 0% |
| 4 | Products pipeline (Amazon + SAR) | 0 | 0 | 0 | 8 | 0% |
| 5 | Articles pipeline (MIND + TF-IDF content model) | 0 | 0 | 0 | 12 | 0% |
| 6 | Cross-type hardening and evidence | 0 | 0 | 0 | 8 | 0% |
| 7 | FastAPI backend | 0 | 0 | 0 | 13 | 0% |
| 8 | Frontend scaffolding | 0 | 0 | 0 | 9 | 0% |
| 9 | Frontend features | 0 | 0 | 0 | 12 | 0% |
| 10 | Integration and robustness audit | 0 | 0 | 0 | 8 | 0% |
| 11 | Documentation and showcase preparation | 0 | 0 | 0 | 8 | 0% |
| 12 | Optional stretch (only after Phases 0 to 11 are complete) | 0 | 0 | 0 | 5 | 0% |
| | **Overall** | **0** | | | **129** | **0%** |

`[--------------------] 0%  (0/129 tasks)`
<!-- PROGRESS:END -->

---

## 1. Project overview

**Name:** Discovery Engine. Use this exact name (title case) in the README, the UI header and browser tab title, the About tab, the API title (`FastAPI(title="Discovery Engine")`), the report assets, and the demo script. Repository and folder name: `discovery-engine`. Note that `discovery/` (the vendored, renamed Recommenders package) and `engine/` (original code) are internal package names and are different from the project name; never present `discovery/` as the project itself.

**Goal:** an engine that adapts to the content type and produces personalised recommendations. A user selects a content type (Movies, Products, Articles) and a user, and sees that user's profile and personalised recommendations, with explanations, comparisons against non-personalised baselines, a cold-start demo, and an honest evaluation of every model.

**Context:** a college showcase project (non-commercial). Evaluators will look at (a) whether it works, (b) whether it genuinely adapts across content types through one engine, and (c) whether the recommendation quality is measured honestly and the design decisions are justified.

**Core idea:** one *engine* with one interface. Each content type plugs in through a *dataset adapter* (data to unified schema) plus a *config file* (signal rules, model choice, hyperparameters, split strategy, card type). Adding a content type must not require changing engine core code. Phase 6 proves this with a test.

**Non-goals:** user accounts/login, real-time learning from live traffic, production deployment, commercial use, image/audio analysis, LLM-based recommendation.

---

## 2. Locked decisions

| Topic | Decision |
|---|---|
| Content types | **Movies**, **Products**, **Articles** |
| Recommendation code | Recommenders (https://github.com/recommenders-team/recommenders, MIT license, formerly Microsoft Recommenders) is the source of the models, dataset loaders, splitters, and metrics. It is **vendored, trimmed, and renamed** to the package `discovery` (not installed via pip). See sections 3 and 5. |
| Original work | `engine/` (adapters, registry, configs, harness, explanations, cold-start, artifacts), `api/`, `frontend/`, `tools/`, tests, docs. |
| Models, primary (CPU-only) | Movies: **SAR**. Products: **SAR**. Articles: **TF-IDF content model with user profile**. Baselines for all: **Popularity** and **Random**. |
| Models, stretch (Phase 12) | LightGCN (movies), SASRec (products), NRMS/NAML (articles), and optionally the owner's own hybrid ALS fold-in engine. Training offline only. |
| Backend | Python 3.11, FastAPI, pydantic v2, numpy/pandas/scipy/scikit-learn. **The API process must never import TensorFlow, Spark, or any deep-learning framework.** It serves precomputed artifacts and cheap numpy/scipy computations only. |
| Training | Offline CLI: `python -m engine.train --type <type>`. Produces artifacts consumed by the API. |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind CSS, Recharts, React Query (or SWR). Calls FastAPI only through Next.js route handlers (server side). |
| Hardware assumption | CPU-only laptop, no GPU, no cloud. Datasets are downloaded to `data/raw/` (gitignored). |
| Demo model | Run both servers locally. No deployment required. |
| Time | Not a constraint on design. Phases are ordered so each ends in a working state. |

---

## 3. Attribution and licensing rules (NON-NEGOTIABLE)

The vendored package is derived from Recommenders under the MIT license. The project must be transparent about this.

1. Keep the original `LICENSE` text (with copyright notice) at `backend/discovery/LICENSE` and keep original copyright headers in every vendored file.
2. Create and maintain `docs/ATTRIBUTION.md` and `backend/discovery/NOTICE.md` stating: source repository URL, source version and commit (or PyPI version), what was trimmed, what was modified (including the package rename), and the list of vendored files (generated by `tools/vendored_manifest.py`).
3. State the derivation in: the README (top section), the About tab in the UI, the report assets, and the demo script.
4. Keep a clear separation: **`backend/discovery/` is derived code; everything else is original.** Never put original code inside `discovery/` except minimal, documented compatibility patches (each listed in `NOTICE.md`).
5. Dataset terms (verify current terms when downloading; record them in `docs/DATASETS.md`): MovieLens (research and education, non-commercial, must cite Harper and Konstan 2015, "The MovieLens Datasets: History and Context", ACM TiiS), MIND (Microsoft Research License, research use, cite Wu et al., ACL 2020), Amazon reviews (academic use, cite the dataset authors). Do not redistribute raw datasets in the repository. If TMDB or any other API is added later, include its required attribution.
6. The README and About tab must say the project is non-commercial and for educational use.

---

## 4. Architecture

```
 raw datasets (MovieLens / Amazon / MIND)
        |
        v
 Adapter (per type)  --->  unified schema: interactions + items
        |
        v
 Registry: type -> {adapter, model, config}           <-- engine/ (original)
        |
        v
 Model wrapper (SAR / TF-IDF-profile / baselines)     <-- uses discovery/ (derived)
        |
 Evaluation harness (splits + metrics + cold-start curves + robustness checks)
        |
        v
 artifacts/<type>/  (model data, items, interactions, users, metrics.json, manifest)
        |
        v
 FastAPI (api/): loads artifacts at startup, serves /v1/*   (no deep-learning imports)
        |
        v
 Next.js (frontend/): route handlers proxy to FastAPI; dashboard UI
```

---

## 5. Repository layout (create in Phase 0)

```
discovery-engine/
  README.md
  IMPLEMENTATION_PLAN.md          # this file (keep at repo root)
  LICENSE                         # the project's own license (default MIT unless the owner says otherwise)
  Makefile
  .gitignore  .pre-commit-config.yaml  .github/workflows/ci.yml
  docs/
    ATTRIBUTION.md  DATASETS.md  DECISIONS.md  ARCHITECTURE.md
    RESULTS.md  DEMO_SCRIPT.md  figures/  screenshots/
  tools/
    progress.py  vendored_manifest.py  make_results.py  select_demo_users.py
  data/            # gitignored: raw/ and processed/
  artifacts/       # gitignored except small demo artifacts if the owner decides
  backend/
    pyproject.toml  (extras: core, dev, deep)   uv.lock or requirements lock
    discovery/     # DERIVED from Recommenders: trimmed + renamed. Has LICENSE and NOTICE.md
      datasets/  evaluation/  models/  utils/
    engine/        # ORIGINAL
      schema.py  config.py  registry.py  artifacts.py  errors.py  logging_utils.py
      adapters/    base.py  movielens.py  amazon_products.py  mind_articles.py  toy.py (test-only)
      models/      base.py  baselines.py  sar_model.py  tfidf_profile_model.py
      evaluation/  splits.py  metrics.py  harness.py  checks.py
      explain.py   coldstart.py   train.py
      configs/     movies.yaml  products.yaml  articles.yaml
    api/
      main.py  deps.py  schemas.py  routes/  security.py  errors.py
    tests/
      unit/  property/  integration/  contract/  fixtures/
    scripts/       fetch_data.py  bench_api.py  export_openapi.py
  frontend/
    package.json  next.config.js  tailwind.config.ts  tsconfig.json
    src/app/  src/components/  src/lib/ (api client, zod schemas, generated types)
    tests/ (vitest)   e2e/ (playwright)   mocks/ (msw fixtures)
```

---

## 6. Core contracts

### 6.1 Unified schema (`engine/schema.py`, pydantic)

- **Interaction:** `user_id: str`, `item_id: str`, `signal: float` (strength, e.g. rating or 1.0 for a click), `timestamp: int` (unix seconds; required, drives chronological splits and time decay), `positive: bool` (derived from the config's signal rule).
- **Item:** `item_id: str`, `title: str`, `subtitle: str | None` (e.g. brand or category line), `categories: list[str]`, `text: str | None` (abstract or description, used by content models), `year: int | None`, `image_url: str | None`, `extra: dict`.
- **ContentTypeSpec:** loaded from YAML (below).

IDs are always **strings** at the engine and API boundary, even if a dataset uses integers.

### 6.2 Config example (`engine/configs/movies.yaml`, validated by pydantic at load)

```yaml
type: movies
display_name: Movies
card_type: movie             # movie | product | article  (frontend card variant)
dataset:
  adapter: movielens
  variant: "1m"              # "100k" for --fast runs and tests
  min_user_interactions: 5
  min_item_interactions: 5
signal:
  positive_threshold: 4.0    # rating >= 4 counts as positive
  use_rating_as_weight: true
split:
  strategy: chronological    # chronological | leave_last_n | impression_time
  ratio: 0.8
  seed: 42
model:
  name: sar
  params: { similarity_type: jaccard, time_decay_coefficient: 30, timedecay_formula: true }
  allow_repeat: false        # whether already-seen items may be recommended
  supports_cold_start: true
evaluation:
  k: [5, 10, 20]
  cold_start_history_sizes: [0, 1, 2, 3, 5, 10, 20]
  baselines: [popularity, random]
serving:
  top_neighbors_per_item: 50
  max_items_in_similarity: 8000   # caps memory (dense NxN similarity is the risk)
```

### 6.3 Adapter interface (`engine/adapters/base.py`)

`DatasetAdapter` (abstract) with: `download(raw_dir)`, `load_raw()`, `interactions() -> DataFrame` (schema columns), `items() -> DataFrame`, `validate() -> ValidationReport`, `split(interactions) -> (train, valid, test)`. Adapters own all dataset-specific logic (parsing, title cleaning, id mapping, filtering). **Engine core must contain no dataset-specific code.**

### 6.4 Model interface (`engine/models/base.py`)

`RecommenderModel` (abstract):
- `fit(train_interactions, items)`
- `recommend_user(user_id, k, exclude_ids=()) -> list[ScoredItem]` (known user)
- `recommend_history(history: list[(item_id, signal)], k, exclude_ids=()) -> list[ScoredItem]` (cold-start, new user from a list of items; raise `ColdStartUnsupported` if not supported)
- `similar_items(item_id, k) -> list[ScoredItem]`
- `popular(k, exclude_ids=()) -> list[ScoredItem]`
- `explain(history_item_ids, recommended_item_id) -> Reason | None` (faithful: names the history item that contributed most to the score)
- `save(dir)` / `load(dir)` (no pickle of arbitrary objects for serving artifacts; use npz, parquet, json, scipy sparse)
- property `supports_cold_start`

`ScoredItem`: `item_id`, `score` (raw), `rank`. Normalised display scores are computed in the API layer only.

**Important about SAR and cold start:** as far as the plan author recalls, Recommenders' SAR `recommend_k_items` rejects users not seen in training. Cold-start for SAR must therefore be computed by the wrapper directly: build the user's affinity vector from the given history (using the fitted model's item index and time-decay settings) and multiply with the item similarity matrix. **Verify the attribute names and the exact scoring formula in the vendored SAR source**, and add a consistency test: for a known user, scoring from their own training history via the cold-start path must produce the same top-k as `recommend_user` (see R3 in section 10).

### 6.5 Artifact layout (`artifacts/<type>/`)

`manifest.json` (artifact schema version, type, model name, config hash, git SHA, dataset variant, created_at, file checksums), `items.parquet`, `interactions.parquet` (train + test, flagged), `users.parquet` (precomputed user stats and persona labels), `model/` (model-specific files: sparse top-K neighbours, TF-IDF matrix, vocabulary json, popularity counts), `topn.parquet` (precomputed top-50 per known user), `metrics.json`, `demo_users.json`. The loader must verify checksums and schema version and fail with a clear error otherwise.

---

## 7. Per-type design differences (this is what "adapts to content type" means)

| Aspect | Movies (MovieLens) | Products (Amazon) | Articles (MIND) |
|---|---|---|---|
| Signal | rating, positive if >= 4 | review/rating, positive if >= 4 (or any review, per config) | click (impression label 1) |
| Item lifespan | years | years | hours to days (recency matters) |
| Repeat consumption | no | no (config flag) | no |
| Content features | genres, year | category, brand, title, description | title, abstract, category, subcategory |
| Primary model | SAR | SAR | TF-IDF content model with user profile |
| Cold start | via similarity matrix | via similarity matrix | native (profile from history texts) |
| Candidate pool | all items | all items (capped) | recent-window articles only (config `recency_window`) |
| Split | chronological per user | chronological per user | by impression time (later days as test) |
| Card type | movie (genre chips, year) | product (brand, category, image slot) | article (headline, abstract snippet, category) |

---

## 8. API specification (summary; details in Phase 7)

Base path `/v1`. JSON errors always shaped `{"error": {"code": str, "message": str}}`. Item and user ids are strings. `k` bounded to 1..50. Endpoints: `GET /health`, `GET /types`, `GET /types/{type}/users`, `GET /users/{user_id}/profile?type=`, `GET /recommend?type=&user_id=&k=`, `POST /recommend/cold-start`, `GET /popular?type=&k=`, `GET /similar?type=&item_id=&k=`, `GET /items/search?type=&q=&limit=`, `GET /items/{item_id}?type=`, `GET /metrics?type=`, `GET /about`. Recommendation responses contain `mode` ("personalized" | "popularity"), `results[]` (item fields, `score`, `reason`), and `meta` (type, model, artifact_version, latency_ms, history_size).

---

## 9. Frontend specification (summary; details in Phases 8 to 9)

Single dashboard. Top bar: "Discovery Engine" wordmark, **TypeSwitcher** (Movies / Products / Articles), **UserSelect** (persona-labelled demo users plus search). URL query params hold `type`, `user`, `tab` so views are shareable. Tabs: **For You** (profile card + recommendation grid with reason badges), **Compare** (popular vs personalised, overlap highlighting, optional two-user comparison), **Cold Start** (search and add liked items, live recommendations), **Evaluation** (metrics table, model-vs-baseline chart, cold-start curve, protocol notes), **About** (attribution, datasets, architecture, original vs derived). Every data panel has loading skeleton, empty state, and error state with retry. Light/dark mode, responsive, keyboard accessible.

---

## 10. Robustness protocol (applies to every phase)

Robustness of the recommendations is the main focus. Each phase lists which gates apply. A phase is complete only when its gates pass and the results are recorded in the Session Log (gate name, date, pass/fail, evidence such as test counts or metric values).

### Gates

**R1 Data validity.** Row counts and sparsity reported; no duplicate (user,item,timestamp) rows unless justified; no null ids; timestamps parse and are within a plausible range; filtering thresholds applied and logged (how many users/items removed); every interacted item has a catalogue entry (or the gap is counted and handled); id mapping is bijective.

**R2 No leakage.** For chronological splits, per user: `max(train.timestamp) <= min(test.timestamp)`. No test interactions in any fitted structure (similarity matrix, TF-IDF vocabulary, popularity counts, hyperparameter selection). Hyperparameters are selected on a validation split, never on test. A dedicated automated test fails if any test row influences the fitted model (for example by fitting twice, once with test rows shuffled out, and comparing artifacts).

**R3 Model invariants.** For every endpoint-level and model-level recommendation call, assert: length <= k; no duplicate items; no excluded or already-seen items (unless `allow_repeat`); all item ids exist in the catalogue; scores finite and sorted descending; deterministic for fixed seed and artifacts; **cold-start consistency** (history-based scoring for a known user equals user-based scoring on their training history, for models that support both); `similar_items` never returns the query item; explanations are **faithful** (the named history item is the true maximum contributor, verified by a property test).

**R4 Evaluation validity.** The same split and the same candidate protocol for model and baselines; metrics checked against hand-computed values on a tiny fixture; sanity ordering reported: Random < Popularity <= Model on ranking metrics. If the model does not beat popularity, **do not hide it**: investigate (bug versus genuine), document the finding in `docs/DECISIONS.md` and RESULTS.md, and still present honest numbers. Also report coverage, novelty, intra-list diversity (by category), and a personalisation score (mean pairwise Jaccard distance between top-k lists of sampled users; a value near zero means the model collapsed to popularity).

**R5 Cold-start behaviour.** Evaluate with history sizes from `cold_start_history_sizes`. Verify: size 0 returns popularity with mode `popularity`; quality is non-decreasing on average as history grows (report non-monotonic cases honestly); behaviour with unknown item ids (ignored and reported), duplicates (rejected), huge histories (capped).

**R6 Reproducibility.** Fixed seeds everywhere; retraining twice produces identical top-N artifacts (compare hashes); a fresh clone can rebuild everything from the README commands; dependency versions locked.

**R7 API contract and edge cases.** Every endpoint tested for every registered type: success, unknown type, unknown user, unknown item, k below 1 and above 50, empty history, oversized history, malformed JSON, wrong types, duplicated ids, unicode and very long strings in search; error shape consistent; no stack traces leaked; OpenAPI schema exported and matches frontend types; the API process never imports TensorFlow (assert `"tensorflow" not in sys.modules`); startup survives a missing or corrupt artifact for one type by marking it `unavailable` instead of crashing.

**R8 Performance and resources.** Budgets on a normal laptop (record actual values): p95 `GET /recommend` < 150 ms, cold-start POST < 300 ms, API RSS memory < 2 GB with all types loaded, training for `--fast` mode < 10 minutes per type. Measure with `scripts/bench_api.py`.

**R9 Frontend robustness.** `tsc` strict clean; ESLint clean; runtime validation (zod) of every API response; tests for loading, empty, error, and slow states; failure injection (API down, 500, malformed JSON, very slow); no hydration warnings; keyboard navigation works; no layout break at 360, 768, 1280 px widths; displayed metrics equal `metrics.json` values exactly.

**R10 Licensing and attribution.** `LICENSE` and headers preserved; `NOTICE.md` and `ATTRIBUTION.md` current; the manifest lists every vendored file; no `import recommenders` anywhere; the original `recommenders` package is not installed in the project environment; About tab and README carry attribution and dataset citations.

**R11 Security basics.** Optional API key check uses constant-time comparison on **bytes** (a str with non-ASCII characters makes `secrets.compare_digest` raise); CORS origins from env (no wildcard in non-dev profile); request body size limits; no secrets in the repo or the frontend bundle; `pip-audit` and `npm audit` reviewed.

### The "break your own work" ritual (end of every phase)

Before ticking the Phase Gate, write down in the Session Log **five concrete ways the phase's output could be wrong or misleading** (for example "popularity baseline accidentally computed on test data", "reasons name an item the user never saw", "cold-start returns already-liked items"), then write or run a test or script for each one. Fix what you find. Record what you tried and the outcome.

### Automation

`make check` must run, at minimum: ruff, mypy (backend), pytest (unit, property, integration, contract), frontend `tsc`, ESLint, vitest. `make gates` runs the slower checks (reproducibility rebuild on `--fast`, bench script, Playwright e2e). CI runs `make check` on every push.

---

## 11. Datasets (summary; details go in `docs/DATASETS.md`)

| Type | Dataset | Notes |
|---|---|---|
| Movies | MovieLens (100K for `--fast` and tests, 1M for final results) | Via the vendored `discovery.datasets.movielens` loader. Research and education use. Cite Harper and Konstan 2015. |
| Products | Amazon reviews (use the loader in `discovery.datasets.amazon_reviews` if it provides product titles/categories; otherwise one mid-size category of the Amazon reviews 5-core set plus its metadata) | Check what the vendored loader actually ships before choosing. Cap item count so the similarity matrix fits in memory (see `max_items_in_similarity`). If a manual download is needed, mark `[!]` and tell the human. |
| Articles | MIND-small (`news.tsv`, `behaviors.tsv`) | Via the vendored `discovery.datasets.mind` helpers (verify names). Microsoft Research License. Cite Wu et al., ACL 2020. |


---

# PHASES

> Task format: `- [ ] **Pn.m** description. *Acceptance:* ...`. Gates are listed per phase. The `tools/progress.py` script counts `[x]` boxes in this PHASES section only.

---

## PHASE 0: Scaffolding and tooling

**Goal:** an empty but fully wired project where `make check` passes.
**Gates:** R6 (partial), R10 (partial).

- [ ] **P0.1** Initialise git, add `.gitignore` (Python, Node, `data/`, `artifacts/` big files, `.env*`, IDE files), add the project `LICENSE` (MIT unless the owner says otherwise). *Acceptance:* clean first commit.
- [ ] **P0.2** Create the directory layout from section 5 (empty packages with `__init__.py`, placeholder READMEs where useful). *Acceptance:* tree matches section 5.
- [ ] **P0.3** Backend environment: Python 3.11, `pyproject.toml` with extras `core` (numpy, pandas, scipy, scikit-learn, pyarrow, pydantic, pyyaml, tqdm, requests, fastapi, uvicorn, joblib), `dev` (pytest, pytest-cov, hypothesis, httpx, ruff, mypy, pip-audit), `deep` (placeholder for Phase 12). Lock versions (uv lock or pinned requirements). *Acceptance:* a fresh virtualenv installs `core,dev` with one command.
- [ ] **P0.4** `Makefile` targets: `setup`, `data`, `train` (all types), `train-fast`, `eval`, `api`, `web`, `test`, `lint`, `check`, `gates`, `progress`, `clean`. *Acceptance:* each target exists and fails gracefully with a clear message if its prerequisite is missing.
- [ ] **P0.5** Linting and typing config: ruff, mypy (strict for `engine/` and `api/`, lenient for `discovery/`), pre-commit hooks. *Acceptance:* `make lint` passes on the skeleton.
- [ ] **P0.6** Write `tools/progress.py` (a reference implementation is shipped next to this plan as `tools/progress.py`; copy it, read it, and add the unit test): parses this file, counts `[x]` / total tasks per `## PHASE n` section, rewrites the dashboard between the `PROGRESS:START/END` markers (table with phase name, done/total, percentage, and an overall bar). Must be idempotent. *Acceptance:* running it twice changes nothing the second time; unit test included in `backend/tests/unit/test_progress.py`.
- [ ] **P0.7** Create `docs/` skeleton files: `ATTRIBUTION.md`, `DATASETS.md`, `DECISIONS.md` (ADR-style log, each entry has date, context, decision, consequences), `ARCHITECTURE.md`, `RESULTS.md` (generated later), `DEMO_SCRIPT.md`. *Acceptance:* files exist with headings and TODO markers.
- [ ] **P0.8** `backend/scripts/fetch_data.py`: downloads datasets to `data/raw/<name>/` with checksums where possible, resumable, with clear messages; if a download fails because of network or terms, prints exact manual steps and the expected path. *Acceptance:* `--help` works; dry-run mode lists what it would fetch. (Real fetching is completed per type in Phases 3 to 5.)
- [ ] **P0.9** CI workflow `.github/workflows/ci.yml` running `make check` on push (backend and frontend jobs; frontend job skipped until Phase 8). *Acceptance:* workflow file validates (use `actionlint` if available).
- [ ] **P0.10** Verify the skeleton: `make setup && make check` is green from a fresh clone. Record Python version, OS, and tool versions in `docs/DECISIONS.md`. *Acceptance:* green run recorded in Session Log.
- [ ] **P0.11** Phase 0 Gate and "break your own work" ritual. *Acceptance:* Session Log entry written.

---

## PHASE 1: Vendor, trim, and rename Recommenders into `discovery`

**Goal:** a small, importable, attributed `backend/discovery/` package that provides what the engine needs, without TensorFlow, Spark, or Cornac installed.
**Gates:** R10 (full), R6.

- [ ] **P1.1** In a throwaway virtualenv **outside the repo**, install a pinned release of `recommenders` from PyPI (choose the latest stable that supports Python 3.11; record version and the corresponding git tag or commit). Copy its `LICENSE` into the repo as `backend/discovery/LICENSE`. *Acceptance:* version recorded in `docs/DECISIONS.md`.
- [ ] **P1.2** Compute the needed module set by tracing imports starting from the entry points the engine will use: dataset loaders (movielens, amazon_reviews, mind, download utilities), splitters (`python_chronological_split`, `python_stratified_split`, `python_random_split` and helper modules), `evaluation.python_evaluation`, `models.sar`, `models.tfidf`, plus transitive `utils` modules. Write the traced list to `docs/vendored_modules.txt`. Exclude Spark, TensorFlow, PyTorch, Cornac, Azure, notebooks, tests, contrib, tuning. *Acceptance:* list reviewed and committed.
- [ ] **P1.3** Copy only those modules into `backend/discovery/`, keeping the internal sub-structure (`datasets/`, `evaluation/`, `models/`, `utils/`). Preserve original copyright headers. *Acceptance:* no file outside the traced list is present.
- [ ] **P1.4** Rewrite imports and string references from `recommenders` to `discovery` (code, logger names, docstring paths, any `__name__`-based lookups). *Acceptance:* `grep -rniE "import recommenders|from recommenders" backend/` returns nothing; mentions of the old name remain only in `LICENSE`, `NOTICE.md`, `docs/`, and header comments.
- [ ] **P1.5** Make top-level imports light: remove or lazy-import optional heavy dependencies in `__init__.py` and utility modules so that `import discovery.models.sar`, `discovery.models.tfidf`, `discovery.evaluation.python_evaluation`, and the dataset and splitter modules succeed with only `core` extras installed. Each patch must be minimal and listed in `NOTICE.md`. *Acceptance:* a test imports each used module in a subprocess and asserts that `tensorflow`, `pyspark`, `torch`, and `cornac` are **not** in `sys.modules`.
- [ ] **P1.6** Write `backend/discovery/NOTICE.md` and `docs/ATTRIBUTION.md` (source URL, version, commit, trimming and modification summary, license statement). Write `tools/vendored_manifest.py` to generate `docs/VENDORED_FILES.md` (path, size, sha256, origin path). *Acceptance:* both documents complete; manifest regenerates deterministically.
- [ ] **P1.7** Smoke tests for the vendored code on tiny synthetic data: SAR fit and recommend; chronological split correctness; metrics (precision, recall, ndcg, map at k) against hand-computed values; TF-IDF recommender on 10 short documents; loaders' parsing functions on small fixture files (no network). *Acceptance:* all pass offline.
- [ ] **P1.8** Environment hygiene test: assert `pip show recommenders` fails in the project environment and `importlib.util.find_spec("recommenders")` is `None`. *Acceptance:* test passes in CI.
- [ ] **P1.9** Phase 1 Gate (R10 full) and "break your own work" ritual. *Acceptance:* Session Log entry.

---

## PHASE 2: Core engine abstractions

**Goal:** the adaptive layer, independent of any dataset: schema, config, adapter and model interfaces, registry, baselines, evaluation harness, artifacts, training CLI.
**Gates:** R2, R3 (baselines), R4 (harness correctness), R6.

- [ ] **P2.1** Implement `engine/schema.py` (Interaction, Item, ScoredItem, Reason, ValidationReport, ContentTypeSpec) with strict validation and string ids. *Acceptance:* unit tests incl. rejection of bad data.
- [ ] **P2.2** Implement `engine/config.py`: YAML loading, pydantic validation, config hash, `--fast` overrides (dataset variant, search grids). *Acceptance:* invalid configs fail with readable messages; tests cover missing fields and wrong types.
- [ ] **P2.3** Implement `adapters/base.py` and `models/base.py` exactly as in section 6, plus `errors.py` (`UnknownType`, `UnknownUser`, `UnknownItem`, `ColdStartUnsupported`, `ArtifactError`). *Acceptance:* abstract classes with docstrings and type hints; mypy strict passes.
- [ ] **P2.4** Implement baselines in `models/baselines.py`: `PopularityModel` (count of positive interactions; ties broken deterministically by item id) and `RandomModel` (seeded; deterministic per user). Both implement the full interface including cold start. *Acceptance:* R3 invariants hold (property tests with hypothesis).
- [ ] **P2.5** Implement `registry.py`: adapters and models registered by name; `get_adapter(type)`, `build_model(type)`; config-driven wiring; clear error for unknown names. *Acceptance:* registering a new adapter requires no edit to registry core (decorator or entry-point style).
- [ ] **P2.6** Implement `evaluation/splits.py` wrapping the vendored splitters: `chronological` (per user), `leave_last_n`, `impression_time`; each returns train/valid/test and runs the leakage check from R2. *Acceptance:* leakage tests pass and fail correctly on a deliberately broken split fixture.
- [ ] **P2.7** Implement `evaluation/metrics.py`: wrapper over vendored ranking metrics (precision, recall, ndcg, map at k) plus original metrics: hit rate, coverage, novelty (mean negative log2 popularity), intra-list diversity (category-based), personalisation score (R4). *Acceptance:* each metric verified against hand-computed values on a tiny fixture.
- [ ] **P2.8** Implement `evaluation/harness.py`: runs split, fits each model (baselines plus configured model), evaluates on the same protocol, simulates cold start by truncating user histories to each configured size, writes a `metrics.json` containing: protocol description, seeds, config hash, git SHA, timestamps, per-model per-k metrics, cold-start curves, sanity-check results. *Acceptance:* runs end to end on a synthetic dataset; schema of `metrics.json` documented in `docs/ARCHITECTURE.md`.
- [ ] **P2.9** Implement `evaluation/checks.py`: reusable invariant checkers for R1 to R5 that can be called from tests, from the harness, and from the API tests. *Acceptance:* used by at least the harness and the baseline tests.
- [ ] **P2.10** Implement `artifacts.py`: save and load per section 6.5, manifest, checksums, schema version, clear failure modes (missing file, bad checksum, version mismatch). *Acceptance:* corruption tests (flip a byte, delete a file) raise `ArtifactError` with an actionable message.
- [ ] **P2.11** Implement `explain.py` and `coldstart.py` helper utilities that are model-agnostic (history normalisation: dedupe, drop unknown ids and report them, cap length, validate signals). *Acceptance:* unit tests including empty, duplicate, and unknown ids.
- [ ] **P2.12** Implement `train.py` CLI: `python -m engine.train --type X [--fast] [--seed N]` (load config, adapter, validate, split, fit, evaluate, write artifacts, print a summary). Structured logging via `logging_utils.py`. *Acceptance:* works on a synthetic "toy" adapter used only in tests.
- [ ] **P2.13** Phase 2 Gate and "break your own work" ritual. *Acceptance:* Session Log entry.

---

## PHASE 3: Movies pipeline (MovieLens + SAR)

**Goal:** the first complete content type, trained, evaluated, and exported. It becomes the template for the others.
**Gates:** R1, R2, R3, R4, R5, R6.

- [ ] **P3.1** Fill the MovieLens section of `docs/DATASETS.md` (variants, license, citation text) and implement the download step in `fetch_data.py`; confirm 100K and 1M both load. *Acceptance:* `make data TYPE=movies` works or a `[!]` note explains the manual step.
- [ ] **P3.2** Implement `MovieLensAdapter`: columns to schema, string ids, clean display titles (strip trailing year and alternate-title parentheses, move trailing articles "Matrix, The" to "The Matrix"), parse year, genres to `categories`, minimum-interaction filtering from config. *Acceptance:* title-cleaning unit tests including edge cases (no year, multiple parentheses, "A", "An", non-ASCII).
- [ ] **P3.3** Implement `validate()` data report (R1) and write it to `artifacts/movies/data_report.json`. *Acceptance:* report includes counts, sparsity, filtered counts, timestamp range.
- [ ] **P3.4** Chronological per-user split (train/valid/test) via the harness; run the leakage test (R2) on the real data. *Acceptance:* test passes on the real split.
- [ ] **P3.5** Implement `SarModel` wrapper over the vendored SAR class: fit from config params; `recommend_user` (exclude seen unless `allow_repeat`); `popular`; `similar_items` from the item similarity matrix (top-K neighbours stored sparsely, never the query item itself). *Acceptance:* R3 invariants hold; unit and property tests.
- [ ] **P3.6** Cold-start scoring for SAR (see section 6.4): build the affinity vector from a history list (apply the same time-decay or weighting convention as training, or document why a flat weight is used for hypothetical histories without timestamps), multiply with the similarity structure, remove history items, return top-k. *Acceptance:* **consistency test**: for 50 sampled known users, top-10 from `recommend_user` equals top-10 from `recommend_history` on their training history (allowing documented tie-breaking differences); test lives in `tests/integration`.
- [ ] **P3.7** Faithful explanations: for recommended item `r` and history `H`, the reason item is `argmax_{h in H} affinity(h) * sim(h, r)`; show only when the contribution share exceeds a configurable threshold (default: top contributor accounts for at least a set fraction of the score; otherwise no reason). *Acceptance:* property test: the reason item is always a member of the history and is the true maximum contributor.
- [ ] **P3.8** Hyperparameter search on the **validation** split (small grid: similarity type, time decay on/off and coefficient, positive threshold). Log all trials to `artifacts/movies/tuning.json`; choose by ndcg@10 on validation; refit on train (+valid if configured); evaluate once on test. *Acceptance:* test split is not touched during selection (assert via the leakage checks and a log of which split each metric used).
- [ ] **P3.9** Train the final model (`make train TYPE=movies`), evaluate against Random and Popularity, write `metrics.json`. Apply R4: report sanity ordering and extra metrics (coverage, novelty, diversity, personalisation). If the model does not beat popularity, investigate and document honestly. *Acceptance:* metrics file valid; findings recorded in `docs/DECISIONS.md`.
- [ ] **P3.10** Cold-start curve for sizes in config (0 to 20 likes) using the harness. Report the curve and any non-monotonic points. *Acceptance:* curve stored in `metrics.json`.
- [ ] **P3.11** Precompute `topn.parquet` (top-50 per known user), `users.parquet` (interaction counts, top categories, first/last timestamps, persona label such as heavy/light/niche/mainstream computed from data), and `items.parquet`. Run `tools/select_demo_users.py` to choose about 8 demo users with diverse tastes (seeded), saved to `demo_users.json` with persona labels. *Acceptance:* demo users produce visibly different top-10 lists (pairwise Jaccard below the configured threshold).
- [ ] **P3.12** Golden-file regression test on the 100K `--fast` pipeline: top-5 for 3 fixed users and key metrics compared with stored values within tolerance. *Acceptance:* test in CI.
- [ ] **P3.13** Phase 3 Gate and "break your own work" ritual (include: popularity computed from train only; no test items in similarity; reasons only reference history items; seen items never recommended).

---

## PHASE 4: Products pipeline (Amazon + SAR)

**Goal:** the second type, added **without changing engine core code**.
**Gates:** R1 to R6, plus "core unchanged" check.

- [ ] **P4.1** Inspect what `discovery.datasets.amazon_reviews` actually provides (category, item metadata, titles, categories, images). Decide the dataset: use the loader's data if it has usable product metadata, else one mid-size Amazon 5-core category plus metadata. Record the decision and license notes in `docs/DATASETS.md` and `docs/DECISIONS.md`. If a manual download is required, mark `[!]`, tell the human exactly what to place where, and continue with Phase 5. *Acceptance:* decision recorded.
- [ ] **P4.2** Implement `AmazonProductsAdapter`: ids to strings, signal rule from config (positive if rating >= threshold), timestamps, metadata join (title, brand, categories, price, image URL when present), missing-metadata fallbacks (title = id, flagged and counted), item cap by popularity to respect `max_items_in_similarity`. *Acceptance:* adapter tests on a small fixture; cap behaviour tested.
- [ ] **P4.3** Validation report (R1) and chronological split with leakage test (R2). *Acceptance:* report and test pass.
- [ ] **P4.4** Add `configs/products.yaml` reusing `SarModel` (no new model code unless a documented need appears). Check memory usage of the similarity structure and keep the budget in R8. *Acceptance:* peak memory during training and serving recorded.
- [ ] **P4.5** Tune on validation, train, evaluate against baselines, cold-start curve, precompute artifacts, select demo users (same procedure as Phase 3). *Acceptance:* same artifact set as movies; R4 sanity results recorded honestly.
- [ ] **P4.6** Product-specific checks: sparse-data behaviour (many users with few interactions), long-tail items, category diversity of top-k, "similar alternatives" quality spot-check (top-5 similar items for 10 random products share category above a recorded rate). *Acceptance:* numbers in `metrics.json`.
- [ ] **P4.7** **Core unchanged check:** `git diff` between the Phase 3 end commit and now shows changes only in `adapters/`, `configs/`, tests, docs, and artifacts tooling; any core change requires a `docs/DECISIONS.md` entry explaining why the abstraction was insufficient (and a fix to the abstraction, not a special case). *Acceptance:* check script `tools/core_unchanged.py` added and passing.
- [ ] **P4.8** Phase 4 Gate and "break your own work" ritual.

---

## PHASE 5: Articles pipeline (MIND + TF-IDF content model)

**Goal:** the third type, which differs most (text content, freshness, impression-based evaluation), to show real adaptation.
**Gates:** R1 to R6, "core unchanged".

- [ ] **P5.1** Dataset step: fetch MIND-small via the vendored helpers (verify function names), record license and citation in `docs/DATASETS.md`. If download is blocked, mark `[!]` with manual steps (expected files: `news.tsv`, `behaviors.tsv` for train and dev). *Acceptance:* files load or blocked note written.
- [ ] **P5.2** Implement `MindArticlesAdapter`: parse `news.tsv` (id, category, subcategory, title, abstract, URL, entities) into Items (title, abstract as `text`, categories = [category, subcategory]); parse `behaviors.tsv` into interactions (history clicks and impression clicks with impression timestamps) and keep impression candidate lists for evaluation. Handle missing abstracts, unicode, and empty histories. *Acceptance:* parsing tests on fixture lines.
- [ ] **P5.3** Define the time protocol: history items in MIND have no individual timestamps, so treat them as occurring before the user's first impression; split by impression time (earlier days train, later days test); record the actual date ranges in the data report. Leakage test: no test impression's clicked item is used as a training positive for that user. *Acceptance:* R2 test on real data.
- [ ] **P5.4** Implement `TfidfProfileModel` using the vendored TF-IDF utilities (verify the class and its cleaning/tokenising helpers) over `title + abstract + category tokens`: fit vocabulary on train-period articles only; store sparse matrix and vocabulary as scipy npz and json. User profile = weighted mean of clicked article vectors (more recent clicks weigh more; weighting scheme from config); score = cosine similarity to candidates. *Acceptance:* unit tests (profile of identical history equals that article's vector direction; empty history gives popularity).
- [ ] **P5.5** Freshness: candidates restricted to the config `recency_window` (for demo: articles that appear in the most recent impressions period); popularity baseline = click count within the window. Document the window choice and its effect. *Acceptance:* recommendations never include articles outside the window (R3 extension).
- [ ] **P5.6** Cold start is native (`recommend_history` builds a profile from given article ids). Add a consistency test as in P3.6. *Acceptance:* test passes.
- [ ] **P5.7** Faithful explanations: the reason article is the history article with the highest cosine similarity to the recommended article; optionally add shared top TF-IDF terms (max 3) as extra explanation text. *Acceptance:* property test as in P3.7.
- [ ] **P5.8** Evaluation with two protocols, both reported: (a) **impression ranking** (MIND-style: rank each impression's candidates; report AUC, MRR, nDCG@5, nDCG@10) and (b) **retrieval** (top-k from the window pool versus later clicks, using the shared ranking metrics). Compare against Random and Popularity under identical candidates. *Acceptance:* both protocols documented in `metrics.json`; sanity ordering recorded honestly.
- [ ] **P5.9** Cold-start curve, precomputed top-N for sampled users, `users.parquet` stats (top categories from clicked articles), and demo users. *Acceptance:* artifact set identical in shape to the other types.
- [ ] **P5.10** Article-specific robustness: very short titles, missing abstracts, non-English characters, duplicated articles, users whose history contains articles missing from the catalogue (dropped and counted). *Acceptance:* tests for each.
- [ ] **P5.11** **Core unchanged check** (run `tools/core_unchanged.py`). Any needed abstraction change must be documented and applied for all types, with all previous tests still green.
- [ ] **P5.12** Phase 5 Gate and "break your own work" ritual.

---

## PHASE 6: Cross-type hardening and evidence

**Goal:** prove the engine is adaptive and trustworthy before any frontend work.
**Gates:** R1 to R6 across all types.

- [ ] **P6.1** `tools/make_results.py` generates `docs/RESULTS.md` and `docs/figures/*.png` from the three `metrics.json` files (tables: model vs baselines per type; cold-start curves; extra metrics; protocol notes; honest limitations). *Acceptance:* regenerates identically; contains no hand-typed numbers.
- [ ] **P6.2** Extensibility proof: add a synthetic fourth type `toy` (test-only adapter and config in `tests/`) and a test that registers it, trains it, and serves recommendations **without editing any file in `engine/` core or `api/`**. *Acceptance:* test passes in CI.
- [ ] **P6.3** Determinism: retrain each type twice in `--fast` mode and compare `topn.parquet` hashes. *Acceptance:* identical, or differences explained and eliminated.
- [ ] **P6.4** Clean-room rebuild: from a fresh clone and fresh virtualenv run `make setup data train-fast eval`; record wall-clock times and any manual steps. *Acceptance:* works using only README commands (update the README if not).
- [ ] **P6.5** Cross-type consistency checks: all three artifact sets load through the same loader; all models pass the same R3 invariant suite via one parametrised test over registered types. *Acceptance:* parametrised test over `registry.types()`.
- [ ] **P6.6** Statistical honesty: for each type and headline metric, compute a bootstrap confidence interval over users (at least 200 resamples) and report whether the model's advantage over popularity is outside the interval. *Acceptance:* intervals in `metrics.json` and shown in RESULTS.md.
- [ ] **P6.7** Failure-mode review: write `docs/DECISIONS.md` entries for known limitations (popularity bias, cold-start items not in training, domain shift, short histories, news freshness, offline-versus-online gap, dataset licences). *Acceptance:* each limitation has a measured or observed example where possible.
- [ ] **P6.8** Phase 6 Gate and "break your own work" ritual (include: shuffled-label test: training on shuffled user-item pairs must give metrics near Random; if not, the evaluation is leaking).

---

## PHASE 7: FastAPI backend

**Goal:** a robust, typed, tested API serving all three content types from artifacts, with no deep-learning imports.
**Gates:** R3, R7, R8, R11, R6.

- [ ] **P7.1** App skeleton in `backend/api/`: `main.py` with a lifespan handler that loads every type found in the registry via `engine.artifacts`; types that fail to load are marked `unavailable` with a logged reason (the app still starts). Config from environment: `ARTIFACT_DIR`, `RECOMMENDER_API_KEY` (optional), `CORS_ORIGINS`, `LOG_LEVEL`. Set `OPENBLAS_NUM_THREADS=1` before numpy import. *Acceptance:* startup test with one corrupt artifact dir passes.
- [ ] **P7.2** `schemas.py` (pydantic response and request models), `errors.py` (single error format, handlers for validation errors, `UnknownType` (404 `unknown_type`), `UnknownUser` (404 `unknown_user`), `UnknownItem`, `ColdStartUnsupported` (409 `cold_start_unsupported`), and a catch-all 500 that returns a generic message without a stack trace). *Acceptance:* every error path returns the standard shape.
- [ ] **P7.3** Read-only metadata endpoints: `GET /v1/health` (status, per-type availability, artifact versions), `GET /v1/types` (display name, card type, supports cold start, counts), `GET /v1/types/{type}/users?limit=&persona=` (demo users first, then sampled users), `GET /v1/items/{item_id}?type=`, `GET /v1/items/search?type=&q=&limit=` (normalised text search: lowercase, strip accents and punctuation, article handling, ranking exact > prefix > word-start > contains, ties by popularity), `GET /v1/about` (attribution, dataset citations, original-versus-derived summary read from docs or constants), `GET /v1/metrics?type=` (serves `metrics.json` unchanged). *Acceptance:* contract tests for each endpoint for each type.
- [ ] **P7.4** `GET /v1/users/{user_id}/profile?type=`: interaction count, positive count, top categories with shares, recent items (last 10 with titles and timestamps), first and last activity, persona label. *Acceptance:* values match a direct pandas computation in tests.
- [ ] **P7.5** `GET /v1/recommend?type=&user_id=&k=&exclude=`: personalised results from `topn.parquet` when the requested k and exclusions allow, otherwise computed live from the model (no TensorFlow); response includes `mode`, `results[]` with `item_id`, `title`, `subtitle`, `categories`, `year`, `image_url`, `score` (raw), `display_score` (0 to 1 min-max within the list), `reason` (`{kind, item_id, text}` or null), and `meta`. *Acceptance:* R3 invariants asserted on every response in tests.
- [ ] **P7.6** `POST /v1/recommend/cold-start` body `{type, history: [{item_id, signal?}], exclude?: [], k}`: history max 200 entries, ids unique (duplicates are a 422 `duplicate_ids`), unknown ids ignored and listed in `ignored_item_ids`, `mode` = `popularity` when fewer positive items than the type's minimum (config) else `personalized`. *Acceptance:* edge-case tests: empty history, only unknown ids, 200 and 201 entries, signals out of range.
- [ ] **P7.7** `GET /v1/popular?type=&k=` and `GET /v1/similar?type=&item_id=&k=`. *Acceptance:* `similar` never returns the query item; unknown item gives 404 `unknown_item`.
- [ ] **P7.8** Security: optional API key header `X-API-Key` compared in constant time **on encoded bytes**; CORS from env; request body size limit; input length limits (search query max 100 chars); no debug output. *Acceptance:* tests with a non-ASCII key header return 401, not 500.
- [ ] **P7.9** Export `openapi.json` (`scripts/export_openapi.py`) and commit it; add a CI check that the committed file equals the generated one. *Acceptance:* check script passes.
- [ ] **P7.10** Contract and property tests: parametrise every endpoint over `registry.types()`; invariants from R3; fuzz with hypothesis (random k, random strings, random id lists); run schemathesis against the OpenAPI schema if it can be installed. *Acceptance:* zero 500 responses across the fuzz run.
- [ ] **P7.11** Performance and memory: `scripts/bench_api.py` (warm-up, 500 requests per endpoint, report p50/p95/p99 and RSS). Meet R8 budgets or document why not. *Acceptance:* results appended to `docs/RESULTS.md` (generated section).
- [ ] **P7.12** Runtime purity test: start the app in a subprocess, hit all endpoints, then assert that `tensorflow`, `pyspark`, `torch`, and `cornac` were never imported (read `sys.modules` via a test-only debug hook or run with an import blocker). *Acceptance:* test passes.
- [ ] **P7.13** Phase 7 Gate and "break your own work" ritual (include: recommend for a user then add one of the results to `exclude`: it must disappear; changing `k` must not reorder the common prefix; concurrent requests give identical results).

---

## PHASE 8: Frontend scaffolding

**Goal:** a typed, tested, themed Next.js shell wired to the API through server-side route handlers.
**Gates:** R9 (partial), R11.

- [ ] **P8.1** Create the Next.js app in `frontend/` (App Router, TypeScript strict, Tailwind, ESLint, Prettier). Record exact versions in `docs/DECISIONS.md`. *Acceptance:* `npm run build` and `npm run lint` pass.
- [ ] **P8.2** Environment handling: `API_BASE_URL` and optional `API_KEY` are **server-only** env vars (never `NEXT_PUBLIC_`). `.env.example` committed. *Acceptance:* a build-output check script greps the client bundle for the key and fails if found.
- [ ] **P8.3** API access layer: Next.js route handlers under `src/app/api/*` proxy to FastAPI (adding the key, timeouts, and uniform error mapping). Generate TypeScript types from `openapi.json` (`openapi-typescript`), and add **zod schemas** that validate every response at runtime. A contract test compares zod schemas to the OpenAPI types. *Acceptance:* a malformed API response produces a typed error state, not a crash.
- [ ] **P8.4** Data fetching with React Query (or SWR): caching, retry with backoff for idempotent GETs, abort on navigation, stale-while-revalidate for metadata. *Acceptance:* unit tests with mocked responses.
- [ ] **P8.5** URL state: `type`, `user`, `tab` kept in the query string; invalid values fall back to defaults and the URL is corrected. *Acceptance:* tests for invalid params.
- [ ] **P8.6** Design system: tokens for colours, spacing, typography; light and dark themes (system default plus toggle); primitives `Card`, `Badge`, `Button`, `Tabs`, `Skeleton`, `ErrorState` (with retry), `EmptyState`, `Toast`, `Tooltip`. *Acceptance:* a `/dev/components` page (excluded in production builds) shows all primitives in both themes.
- [ ] **P8.7** App shell: top bar (title, TypeSwitcher placeholder, UserSelect placeholder, theme toggle), tab container, footer with attribution links (Recommenders, MovieLens, Amazon reviews, MIND; non-commercial notice). *Acceptance:* renders correctly at 360, 768, 1280 px.
- [ ] **P8.8** Test tooling: vitest and Testing Library; MSW with fixtures **recorded from the real API** (script `frontend/scripts/record_fixtures.ts`); Playwright config. Add frontend jobs to `make check` and CI. *Acceptance:* at least one passing test of each kind.
- [ ] **P8.9** Phase 8 Gate and "break your own work" ritual.

---

## PHASE 9: Frontend features

**Goal:** the complete dashboard.
**Gates:** R9, R4 (display fidelity).

- [ ] **P9.1** `TypeSwitcher` and `UserSelect`: types come from `/v1/types`; users from `/v1/types/{type}/users` with persona labels (for example "Heavy user, Sci-Fi fan"), keyboard-searchable. Switching type resets the user to that type's first demo user and keeps the current tab. *Acceptance:* component tests; no request waterfalls.
- [ ] **P9.2** `ProfileCard`: interaction count, top categories as a horizontal bar chart (Recharts), recent activity list, first/last activity. *Acceptance:* values match the API fixture exactly.
- [ ] **P9.3** `RecCard` with three variants selected by `card_type`: **movie** (title, year, genre chips), **product** (title, brand/subtitle, category chips, image slot with graceful placeholder), **article** (headline, abstract snippet clamped to 3 lines, category chip). `ReasonBadge` shows the reason text; a `ModeBadge` shows personalised versus popularity. *Acceptance:* visual tests via Playwright screenshots for each variant, both themes.
- [ ] **P9.4** **For You** tab: profile card plus recommendation grid, k selector (5, 10, 20), skeletons, empty and error states with retry. *Acceptance:* e2e flow for each type.
- [ ] **P9.5** **Compare** tab: two columns "Popular for everyone" and "Personalised for this user", with overlap highlighting and an overlap percentage computed on the client from the two lists; a second mode compares two selected users side by side. *Acceptance:* overlap percentage tested against known fixtures.
- [ ] **P9.6** **Cold Start** tab: debounced item search (`/v1/items/search`), add or remove liked items as chips (max 200, dedupe), optional rating slider for types where it applies, live recommendations via `POST /v1/recommend/cold-start`, a clear indicator of how many liked items are used and when the mode flips from popularity to personalised. For types where `supports_cold_start` is false, show an explanation instead of the form. *Acceptance:* requests are cancelled when inputs change quickly; e2e test covers add, remove, and clear.
- [ ] **P9.7** **Evaluation** tab: table of model versus baselines (including confidence intervals from P6.6), bar chart for the chosen metric and k, cold-start curve line chart, extra metrics (coverage, novelty, diversity, personalisation), protocol description and dataset notes, all read from `/v1/metrics`. *Acceptance:* **displayed numbers equal `metrics.json` values exactly** (test compares rendered text with fixtures; no rounding differences beyond the documented display precision).
- [ ] **P9.8** **About** tab: attribution (Recommenders derivation statement, license, links), dataset citations and licence notes, architecture diagram (static SVG or Mermaid rendered at build time), table "original versus derived code", limitations list from `docs/DECISIONS.md` highlights. *Acceptance:* content comes from `/v1/about` plus static assets; no copy that contradicts `docs/ATTRIBUTION.md`.
- [ ] **P9.9** Item drawer: clicking a card opens details (all item fields) with "More like this" from `/v1/similar`. *Acceptance:* focus is trapped and restored; closes with Escape.
- [ ] **P9.10** Responsiveness and accessibility: layouts at 360/768/1280 px; semantic landmarks; focus rings; aria labels on charts (text alternative with the data); colour contrast checks (axe); `prefers-reduced-motion` respected. *Acceptance:* axe reports no serious violations on all tabs.
- [ ] **P9.11** Component and integration tests for all components; Playwright e2e: per type, select user, view recommendations, compare, cold start, evaluation, about. *Acceptance:* e2e green against the real API using `--fast` artifacts.
- [ ] **P9.12** Phase 9 Gate and "break your own work" ritual (include: rapid type switching, rapid user switching, cold-start spam typing, offline mode, 500 from API, extremely long titles, items with missing fields).

---

## PHASE 10: Integration and robustness audit

**Goal:** assume nothing; re-verify everything end to end.
**Gates:** all (R1 to R11).

- [ ] **P10.1** `make demo` target: builds `--fast` or final artifacts if missing, starts the API and the frontend, waits for health, prints URLs. *Acceptance:* one command from a fresh clone after `make setup data train`.
- [ ] **P10.2** Failure-injection suite (Playwright with network interception): API down, 500, 404 for a user, malformed JSON, slow response (10 s), empty results, one type unavailable. *Acceptance:* the UI shows a correct state in each case, never a blank page or an unhandled exception in the console.
- [ ] **P10.3** Data-versus-UI consistency audit: script compares every number displayed in the UI (scraped via Playwright) with `metrics.json` and API values. *Acceptance:* zero mismatches.
- [ ] **P10.4** Re-run **all gates R1 to R11** for all types on final (non-fast) artifacts. Record a table (gate, type, result, evidence) in `docs/RESULTS.md` under "Robustness audit". *Acceptance:* all pass, or each failure has a fix task or a documented limitation.
- [ ] **P10.5** Security and dependency review: `pip-audit`, `npm audit`, secret scan (grep for keys, `.env` not committed), CORS configuration review, confirm the client bundle contains no API key. *Acceptance:* findings fixed or documented.
- [ ] **P10.6** Fresh-machine rehearsal: new clone in a new directory with a new virtualenv and a clean `node_modules`, following only the README. Record every deviation and fix the README. *Acceptance:* success without undocumented steps.
- [ ] **P10.7** Final regression: full `make check` and `make gates` green; golden tests green; coverage report (target at least 80% for `engine/` and `api/`; explain gaps).
- [ ] **P10.8** Phase 10 Gate and a last "break your own work" ritual: try to produce a nonsensical recommendation through the UI (weird users, strange cold-start combinations); fix or document each finding.

---

## PHASE 11: Documentation and showcase preparation

**Goal:** everything an evaluator or reader needs, honest and reproducible.
**Gates:** R10, R6.

- [ ] **P11.1** `README.md`: what it is, screenshots, the derivation statement (Recommenders, MIT, what is original), quick start (`make setup data train demo`), repository map, results summary pulled from `docs/RESULTS.md`, limitations, citations, non-commercial notice. *Acceptance:* a reader can run the project from the README alone.
- [ ] **P11.2** `docs/ARCHITECTURE.md` with Mermaid diagrams (system overview, training pipeline, request flow, adapter and registry design, artifact layout) and an explanation of how the engine adapts to content types (section 7 table, updated with real results).
- [ ] **P11.3** `docs/ATTRIBUTION.md`, `NOTICE.md`, `VENDORED_FILES.md` regenerated and reviewed; an "Original versus derived" table with file counts and line counts per area (generated by a script). *Acceptance:* numbers generated, not typed.
- [ ] **P11.4** Report assets in `docs/figures/` (metrics charts, cold-start curves, architecture diagram) and `docs/REPORT_OUTLINE.md` (suggested structure: problem, related work, design, implementation, evaluation, discussion, limitations, future work with the "replace derived components with from-scratch implementations" roadmap, references).
- [ ] **P11.5** `docs/DEMO_SCRIPT.md`: 5 to 7 minute walkthrough (one persona per type, compare tab, cold-start moment, evaluation tab, about/attribution), plus likely evaluator questions with answers grounded in the repository (why SAR, why TF-IDF for news, how cold start works, what is original, how leakage was prevented, what the limits are).
- [ ] **P11.6** Screenshots captured by Playwright into `docs/screenshots/` for each type and tab (backup for the demo). *Acceptance:* generated by a script.
- [ ] **P11.7** HUMAN: record a backup screen recording of the demo and verify the demo on the presentation machine. Mark `[!]` with a note for the human (do not tick this yourself).
- [ ] **P11.8** Final checklist: all earlier phases `[x]` (or documented `[!]`), dashboard updated, tag `v1.0`, Session Log final entry.

---

## PHASE 12: Optional stretch (only after Phases 0 to 11 are complete)

Each item must keep the API free of deep-learning imports (training offline, artifacts exported to numpy/parquet) and must be added through the same adapter/model interfaces.

- [ ] **P12.1** HUMAN-assisted: add the owner's own hybrid ALS fold-in movie engine as an additional movie model (`hybrid_als_foldin`) behind `RecommenderModel`, evaluated on the same split and protocol, credited as original work. Requires the human to provide the training code or artifacts (`model.npz`, `hybrid_config.json`, `recommender.py`) and a mapping from MovieLens ids to the engine's ids.
- [ ] **P12.2** Vendor extra Recommenders modules (LightGCN, SASRec, NRMS or NAML) with the `deep` extra; train offline; export embeddings or scores to artifacts; add evaluation rows and an "advanced model" toggle in the UI.
- [ ] **P12.3** Poster and image support via a licensed source (for example TMDB, requires an API key and its attribution text) behind a config flag.
- [ ] **P12.4** A fourth real content type (books or music) using only an adapter and a config, to demonstrate extensibility with real data.
- [ ] **P12.5** Side-by-side model switcher in the UI (same user, two models).

---

## 12. Known risks and mitigations

| Risk | Mitigation |
|---|---|
| Vendored code drags in heavy or conflicting dependencies | Trace imports (P1.2); lazy-import optional dependencies (P1.5); import-purity tests |
| Dataset downloads fail or terms require manual steps | `fetch_data.py` prints exact manual steps; mark `[!]`; continue with other types |
| SAR similarity matrix too large for products | Cap items (`max_items_in_similarity`), store only top-K neighbours for serving, document the cap |
| Offline metrics look good because of leakage | R2 tests, validation-only tuning, shuffled-label test (P6.8) |
| Model fails to beat popularity on a dataset | Report honestly; investigate; discuss in limitations. Do not tune on test |
| Explanations misleading | Faithful explanation property tests (P3.7, P5.7) |
| News freshness ignored | Recency window and test (P5.5) |
| Agent hallucinates library APIs | Rule 6: read the vendored source before use |
| Quota interruptions leave work half-done | Commit per task, `[~]` notes, Session Log handoff |
| Plan drift | Rule 7 and `docs/DECISIONS.md` for every deviation |

---

## 13. Templates

### Session Log entry template (append at the end of this file)

```
### Session N: YYYY-MM-DD, agent/account label
- Started at: task Pn.m   Ended at: task Pn.m
- Completed: Pn.a, Pn.b, ...
- In progress ([~]): Pn.c (what is done, what remains, where the code is)
- Blocked ([!]): Pn.d (what the human must do)
- Decisions made: (link to docs/DECISIONS.md entries)
- Gate results: (gate, type, pass/fail, evidence such as test counts or metric values)
- "Break your own work" findings: (5 hypotheses and outcomes)
- Test status: make check = PASS/FAIL (details)
- Next steps for the next session:
```

### Decision entry template (`docs/DECISIONS.md`)

```
## D-NNN: Title (date)
Context: ...  Options considered: ...  Decision: ...  Consequences: ...  Related tasks: ...
```

---

## 14. Session Log

> Append new entries below. Never delete earlier entries.

### Session 0: plan created
- Plan written; no code yet. Next: Phase 0, task P0.1.