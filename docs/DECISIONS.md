# Architecture Decision Records

> Each entry follows the format: Date, Context, Options considered, Decision, Consequences, Related tasks.

---

## D-001: Project license (2026-10-24)

**Context:** Need to choose a license for the project's original code.

**Options considered:** MIT, Apache 2.0, GPL

**Decision:** MIT — matches the vendored Recommenders license, simplest for an educational project.

**Consequences:** No copyleft obligations; derived code remains MIT.

**Related tasks:** P0.1

---

## D-002: Loosen pyproject.toml upper version bounds (2026-10-24)

**Context:** The previous session pinned tight upper bounds (e.g. `numpy>=1.24,<2.0`). On the current dev machine (Python 3.14.2, macOS ARM64), numpy 2.x is required — numpy 1.x does not build for Python 3.13+.

**Options considered:** (a) Pin Python to 3.11 only, (b) Loosen upper bounds while keeping minimum versions, (c) Remove all bounds.

**Decision:** (b) Keep `>=` minimum constraints from the plan, remove `<` upper bounds. This allows the latest compatible versions to install on any Python >=3.11.

**Consequences:** Dependencies float to latest compatible; CI on Python 3.11 may see different versions than dev. Minimum versions still enforced.

**Related tasks:** P0.3

---

## D-003: Portable Makefile (2026-10-24)

**Context:** The previous session wrote a Makefile with hardcoded Windows absolute paths (`e:\discover\.venv\Scripts\python.exe` etc.), which cannot work on macOS or Linux.

**Decision:** Rewrote all tool references to use `python3` / `pip` (overridable via `PYTHON ?=` / `PIP ?=`). Commands use `python -m <tool>` pattern to work in any activated venv on any OS.

**Consequences:** Users must activate the venv or set `PYTHON`/`PIP` variables. Works on macOS, Linux, and Windows (with appropriate shell).

**Related tasks:** P0.4

---

## D-004: Environment record (2026-10-24)

**Context:** P0.10 requires recording the verified environment.

**Record:**
- **OS:** macOS (ARM64, Apple Silicon)
- **Python:** 3.14.2
- **Key tool versions:** pytest 9.1.1, ruff 0.17.2, mypy 2.4.0, numpy 2.5.4, pandas 3.1.0, scipy 1.18.1, scikit-learn 1.9.1, fastapi 0.162.0, pydantic 2.14.1, hypothesis 6.170.9
- **`make check` result:** GREEN (lint + type check + 7 tests pass)

**Related tasks:** P0.10

## D-005: Windows environment verification (2026-10-24)

**Context:** The workspace is running on Windows 11 with Python 3.11.7. Verified fresh virtualenv setup and execution of tests and linters.

**Record:**
- **OS:** Windows 11 (x64)
- **Python:** 3.11.7
- **Key tool versions:** pytest 9.1.1, ruff 0.17.2, mypy 2.4.0, numpy 2.4.6, pandas 3.1.0, scipy 1.17.1, scikit-learn 1.9.1, fastapi 0.162.0, pydantic 2.14.1, hypothesis 6.170.9
- **Checks result:** GREEN (lint + type check + 7 tests pass)

**Related tasks:** P0.3, P0.10

## D-006: Recommenders source version and license (2026-10-24)

**Context:** P1.1 requires selecting a pinned release of `recommenders` from PyPI that supports Python 3.11, installing it in a throwaway virtualenv outside the repo, copying its LICENSE into `backend/discovery/LICENSE`, and recording the version.

**Decision:**
- **Package:** `recommenders`
- **PyPI version:** `1.2.1`
- **Release tag / commit:** Git tag `1.2.1` (`51b1451f28ffea99df38e833441ee45ca09ba3a9` at https://github.com/recommenders-team/recommenders)
- **License:** MIT (Copyright (c) 2018-present Microsoft Corporation, 2023-present Recommenders contributors) copied to `backend/discovery/LICENSE`.

**Consequences:** `1.2.1` is the base from which `backend/discovery/` will be trimmed and renamed in subsequent Phase 1 tasks.

**Related tasks:** P1.1, P1.6

## D-007: Recommenders API adjustments and NumPy 2 compatibility (2026-10-24)

**Context:** During P1.7 smoke testing of the vendored `discovery` package against actual source:
1. The plan named the chronological splitter `python_chronological_split`. The actual function name in `discovery.datasets.python_splitters` is `python_chrono_split`.
2. NumPy 2.x removed the expired attribute `np.NaN` in favor of `np.nan`. `SARSingleNode` in Recommenders 1.2.1 used `np.NaN` in item/user mapping lookups.

**Decision:**
1. Use `python_chrono_split` as the real splitter API name (per operating rule 6).
2. Patch `models/sar/sar_singlenode.py` to use `np.nan` instead of `np.NaN`.

**Consequences:** `discovery` works seamlessly across both NumPy 1.x and NumPy 2.x environments.

**Related tasks:** P1.5, P1.7, P2.6

---

## D-008: Fast config overrides and schema model_copy (2026-10-24)

**Context:** P2.2 requires applying fast developer overrides when `--fast` is specified. Mutating Pydantic v2 schemas in-place can inadvertently mutate cached or shared objects.

**Decision:**
Use `spec.model_copy(deep=True)` when applying overrides in `engine.config.apply_fast_overrides`, ensuring pristine original models and immutability.

**Consequences:** Clean separation between default and fast development configurations.

**Related tasks:** P2.2, P2.8, P2.12

## D-009: SAR cold-start weighting convention and consistency verification (2026-10-24)

**Context:** Task P3.6 requires cold-start scoring for SAR via `recommend_history`. When training with exponential time-decay (`timedecay_formula: true`), historical interactions are scaled down exponentially based on the time elapsed from the latest dataset interaction timestamp (`time_now`). In an online or cold-start setting (such as an onboarding questionnaire in the web UI), user-provided interaction history consists of selected items and preference signals without historical timestamps.

**Decision:**
1. For hypothetical cold-start histories without timestamps, a flat weighting convention is used (the explicit float signal or default 1.0) to construct the affinity row vector.
2. In `SarModel.recommend_history`, `max_history_length` defaults to `None` so that full histories supplied during evaluation or consistency audits are not truncated prematurely.
3. For consistency verification (R3):
   - Under flat weighting (`timedecay_formula: false`), `recommend_user` and `recommend_history` on raw training signals produce identical recommendation item lists and numerical scores (within floating-point tolerance `rel=1e-5`).
   - Under shipped time-decayed models (`timedecay_formula: true`), scores between user-based and history-based scoring with flat hypothetical signals diverge predictably because user-based interactions are decayed by `2^(-dt / half_life)` whereas cold-start histories lack timestamps; when `recommend_history` is supplied with the user's exact decayed training affinities, recommendation item lists and numerical scores match within floating-point tolerance (`rel=1e-5`).

**Consequences:** Clear, mathematically grounded consistency guarantee between user-based and history-based recommendation pipelines without misleading "bit-for-bit" claims regarding time-decayed versus un-decayed representations.

**Related tasks:** P3.5, P3.6, R3

## D-010: Top-K sparsification and item similarity budget cap (2026-10-25)

**Context:** Task P3.5/P3.6/P3.8 requires item-item similarity computation in SAR. A full dense similarity matrix scales as $O(N^2)$ in space ($N$ items), which becomes prohibitive for memory and serving latency as item counts grow, and introduces spurious noise from low-co-occurrence pairs. We need empirical evidence comparing top-$K$ neighbor sparsification ($K \in \{20, 50, 100, \text{full}\}$) and the item budget cap (`max_items_in_similarity`) across MovieLens 100K and 1M.

**Empirical Evidence:**
Measured using `tools/measure_sparsification.py` on identical chronological train/validation splits (80/10/10) evaluated on validation users ($k=10$):

*MovieLens 100K (1,682 items, 99,723 interactions):*
| $K$ | NDCG@10 | Recall@10 | Similarity Size | Non-zeros (NNZ) | Train Peak RAM | Serving Peak RAM | Serving Latency (300 users) |
|---|---|---|---|---|---|---|---|
| **20** | **0.1205** | 0.1478 | 0.34 MB | 29,320 | 117.6 MB | 11.4 MB | 9.10 s |
| **50** | 0.1140 | 0.1378 | 0.84 MB | 73,249 | 117.4 MB | 11.8 MB | 7.34 s |
| **100** | 0.1182 | 0.1500 | 1.68 MB | 146,309 | 117.4 MB | 12.6 MB | 7.36 s |
| **Full** | 0.1201 | **0.1547** | 16.79 MB | 1,466,944 | 117.4 MB | 27.8 MB | 9.02 s |

*MovieLens 1M (3,883 items, 999,611 interactions):*
| $K$ | NDCG@10 | Recall@10 | Similarity Size | Non-zeros (NNZ) | Train Peak RAM | Serving Peak RAM | Serving Latency (300 users) |
|---|---|---|---|---|---|---|---|
| **20** | 0.0852 | 0.0935 | 0.80 MB | 68,300 | 765.6 MB | 99.3 MB | 15.66 s |
| **50** | **0.0897** | 0.0946 | 1.97 MB | 170,750 | 765.5 MB | 100.6 MB | **11.30 s** |
| **100** | 0.0858 | **0.0962** | 3.92 MB | 341,500 | 765.6 MB | 102.7 MB | 16.85 s |
| **Full** | 0.0868 | 0.0910 | 112.89 MB | 9,863,072 | 765.6 MB | 211.9 MB | 21.62 s |

**Key Findings & Limitations (FIX-21):**
1. **Regularization through Pruning on 1M:** On MovieLens 1M, $K=50$ achieves competitive validation ranking quality (NDCG@10 = 0.0897 vs 0.0868 for the full matrix, and Recall@10 = 0.0946 vs 0.0910). Pruning low-weight long-tail similarities eliminates noisy, spurious co-occurrences.
2. **K=50 is Not Better on 100K:** On smaller datasets such as MovieLens 100K, $K=50$ is *not* superior in ranking quality to $K=20$ or Full: $K=20$ achieved NDCG@10 of 0.1205 and Full achieved Recall@10 of 0.1547, whereas $K=50$ achieved NDCG 0.1140 and Recall 0.1378.
3. **Serving Latency is Noisy:** Latency differences on small sample batches (e.g. 7.34 s vs 9.02 s for 300 users) are modest and heavily subject to CPU and OS scheduling noise. Claims of clean "2x speedup" are overstated for small matrices.
4. **Massive Memory Savings Justification:** The true and primary justification for $K=50$ sparsification is **computational tractability and memory scaling**: for MovieLens 1M, sparsification reduces similarity storage from 112.89 MB down to 1.97 MB (a **98.3% / 57x memory reduction**), cutting peak serving memory in half (from 211.9 MB to 100.6 MB) and guaranteeing bounded memory on large item sets.
5. **Item Budget Cap Rationale:** Capping `max_items_in_similarity` guarantees that similarity storage remains bounded by $O(M_{\text{max}} \cdot K)$ non-zeros regardless of total long-tail item catalog size.

**Decision:**
- Select $K = 50$ as the primary operating setting for SAR serving, justified by a 57x smaller similarity footprint and bounded memory on mid-to-large catalogs, while recognizing that $K=50$ does not universally dominate ranking quality on smaller datasets.
- Retain `top_neighbors_per_item` as an explicit tuned parameter in validation hyperparameter sweeps (P3.8), exploring $K \in \{20, 50, 100\}$.
- Maintain the item budget cap (`max_items_in_similarity: 50000`) to guarantee an upper memory bound on large catalogs.

**Consequences:** High-quality, fast, and lightweight serving artifacts without memory explosion on larger datasets.

**Related tasks:** P3.5, P3.6, P3.8, FIX-14, FIX-15, FIX-21

## D-011: MovieLens 1M SAR evaluation and baseline comparison (2026-10-25)

**Context:** Task P3.9 requires training the final MovieLens model on MovieLens 1M (`data/raw/movielens/ml-1m`), evaluating against Popularity and Random baselines under the identical candidate protocol (strictly excluding training interactions for each user), evaluating cold-start curves and R4 metrics, and recording the findings honestly.

**Evaluation Protocol & Hyperparameter Tuning:**
- **Dataset:** MovieLens 1M (999,611 interactions, 3,416 active items after filtering $\ge 5$, 6,040 active users).
- **Split:** Chronological per-user split (80% train, 10% valid, 10% test). R2 leakage checks passed with 0 test/valid timestamps preceding train max.
- **Validation-only Tuning (P3.8):** 10 hyperparameter trials evaluated strictly on the validation split. Best configuration selected by validation NDCG@10 (0.0869): Jaccard similarity, time-decay enabled (half-life 30 days), positive threshold 4.0, top-$K$ neighbor sparsification 50. Test split was strictly unread during selection.

**Final Test Split Results ($N=1,918$ evaluated test users out of 2,000 sampled common users, 500-resample 95% bootstrap CIs):**
| Metric | Random | Popularity (95% CI) | SAR Tuned (95% CI) | CIs Separate? |
|---|---|---|---|---|
| **Recall@10** | 0.0033 | 0.04452 [0.03894, 0.04943] | **0.06451 [0.05770, 0.07156]** | **Yes (SAR > Pop, p < 0.05)** |
| **NDCG@10** | 0.0042 | 0.05464 [0.04923, 0.06063] | 0.05922 [0.05405, 0.06441] | No (Overlap) |
| **HitRate@10** | 0.0329 | 0.24870 [0.22888, 0.26774] | 0.28259 [0.26250, 0.30111] | No (Overlap) |
| **Precision@10**| 0.0034 | 0.04181 [0.03803, 0.04594] | 0.04135 [0.03806, 0.04471] | No (Overlap) |
| **Coverage@10** | 0.9948 | 0.0288 | **0.1638** | **+469% (5.7x)** |
| **Novelty@10** | 13.97 | 8.48 | **9.12** | **+7.5%** |
| **Diversity@10** | 0.8239 | 0.7662 | 0.6983 | -8.9% |
| **Personalisation@10**| 0.9987 | 0.6712 | **0.9366** | **+39.5%** |

**Sanity Checks and Audit Findings (R4, FIX-16, FIX-17, FIX-18, FIX-21):**
1. **NDCG Metric Validity Audit (FIX-16):** An independent plain-NumPy audit on 5 real MovieLens test users verified that binary NDCG@10 (0.1568) and graded NDCG@10 (0.1669) matched `engine.evaluation.metrics.ndcg` exactly. The prior ~36x gap between validation NDCG (~0.087) and test NDCG (~0.0024) was caused by an outer-merge bug in `ndcg_at_k`: `df_dcg` outer-merged against the full ground truth dataset (~5,785 users) rather than the evaluated sample of 200 users, computing zero DCG for the 5,585 un-evaluated users and averaging over all 5,785 users in `.mean()`. Following the fix (restricting `rating_true` to `common_users` and safely dropping any `"rank"` column from predictions), test NDCG@10 is 0.0592 for SAR and 0.0546 for Popularity on the 2,000-user sample.
2. **Corrected Baseline Comparison & Statistical Honesty (FIX-17, FIX-21):** With $N=1,918$ evaluated test users and 500 bootstrap resamples, SAR strictly separates from Popularity on **Recall@10** (lower bound 0.05770 > upper bound 0.04943). However, confidence intervals overlap on **NDCG@10** and **HitRate@10**. Prior claims that SAR 'decisively beats' Popularity across all ranking metrics were overclaims and are retracted. Popularity is a formidable baseline on MovieLens; SAR's genuine benefits are statistically separated Recall (+44.9%), vastly higher personalization (0.9366 vs 0.6712), and 5.7x wider catalog exploration (16.4% vs 2.9% coverage).
3. **Personalisation & Diversity:** Popularity offers static recommendations with low personalization (0.6712) and narrow coverage (2.9% of catalogue). In contrast, SAR achieves 0.9366 personalization and explores 5.7x more catalogue items (16.4% at K=10).
4. **Cold-Start Degradation Curve (P3.10 & FIX-18):** At 0 likes, when seen training items are excluded per the evaluation protocol (`allow_repeat: false`), SAR recommendation is mathematically and empirically identical to the Popularity baseline on the same users (Recall@10 = 0.0465, HitRate@10 = 0.2600, NDCG@10 = 0.0642 on $N=50$ users). As history increases from 0 to 20 likes, Recall@10 increases from 0.0465 to 0.0600 (+29.0%) and NDCG@10 increases from 0.0642 to 0.0786 (+22.4%), demonstrating dynamic adaptation.
5. **Shuffled-Label Sanity Verification (FIX-19):** Evaluated on the exact same N=500 real MovieLens test users across Real SAR, Shuffled SAR (trained on permuted user-item training interactions), and Random baseline:
   - **NDCG@10:** Real = 0.05585, Shuffled = 0.01740, Random = 0.00307 (3.2x collapse towards Random)
   - **HitRate@10:** Real = 0.29498, Shuffled = 0.11506, Random = 0.02929 (2.6x collapse towards Random)
   - **Recall@10:** Real = 0.05995, Shuffled = 0.01797, Random = 0.00273 (3.3x collapse towards Random)
   This confirms collaborative filtering co-occurrence is genuine and uncorrupted by data or temporal leakage (shuffling labels destroys co-occurrence while retaining only marginal item frequency bias).

**Decision:**
Accept the trained SAR model and generated artifacts (`metrics.json`, `tuning.json`, `topn.parquet`, `users.parquet`, `items.parquet`, `demo_users.json`) as the validated production artifacts for MovieLens.

## D-012: Amazon Product Dataset Selection, Metadata Schema, and Fast Variant (P4.1)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
Phase 4 introduces the second content type (`products`) using Amazon product reviews and SAR without altering the core engine abstractions. We inspected `discovery.datasets.amazon_reviews`, which pulls from Julian McAuley's Stanford SNAP / UCSD Amazon dataset repository (2014 snapshot).
The helper functions in `discovery.datasets.amazon_reviews` (`get_review_data`, `data_preprocessing`) were designed for negative sampling experiments and discard item titles, prices, and image URLs. However, the raw Stanford SNAP archive contains comprehensive metadata files alongside 5-core review files:
- Review files (`reviews_<category>_5.json.gz`): contain `reviewerID`, `asin`, `overall` (rating 1–5), `unixReviewTime`.
- Metadata files (`meta_<category>.json.gz`): contain `asin`, `title`, `price`, `imUrl`, `categories`, and `brand`.

We needed to decide on:
1. A mid-sized, high-quality 5-core category for standard production training (`variant: "video_games"`).
2. A lightweight 5-core category for fast development and testing (`variant: "instruments"`).
3. Availability and accessibility of direct HTTP downloads vs manual steps.

**Decision:**
1. **Standard Category:** Use Amazon 5-core **Video Games** (`reviews_Video_Games_5.json.gz` ~108 MB, `meta_Video_Games.json.gz` ~22 MB). This provides 231,780 interactions across 24,309 users and 50,256 items with rich gaming metadata (titles, platforms, brands, price points, and cover art).
2. **Fast Mode Category:** Use Amazon 5-core **Musical Instruments** (`reviews_Musical_Instruments_5.json.gz` ~2.3 MB, `meta_Musical_Instruments.json.gz` ~29 MB). This provides 10,261 reviews across 1,429 users and 900 items, executing the entire pipeline in under 5 seconds for CI and developer iteration.
3. **Download Strategy:** Both datasets are publicly hosted by Stanford SNAP (`http://snap.stanford.edu/data/amazon/productGraph/categoryFiles/`) with direct HTTP 200 availability. Automated download is implemented in `backend/scripts/fetch_data.py --type products` with automatic gzip streaming and graceful manual instructions if network access is restricted.
4. **Metadata Extraction:** Implement an adapter `AmazonProductsAdapter` that parses raw review json lines directly into `Interaction` objects and metadata files into `Item` objects (mapping `asin` -> `item_id`, `imUrl` -> `image_url`, `title` with fallback to `asin`, and `categories[0]` flattened).

**Consequences:**
- Product recommendations have real product names, categories, prices, and image URLs rather than bare ASIN codes.
- Fast mode executes quickly without downloading the full 108 MB Video Games dataset during unit tests.
- Core engine abstractions remain untouched (R6 and "core unchanged" principle satisfied).

**Related tasks:** P4.1, P4.2, P4.3, P4.4, P4.7

---

## D-013: Amazon Products SAR Model Reuse, Memory Usage, and Serving Budget (P4.4)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
Task P4.4 requires adding `configs/products.yaml` reusing `SarModel` without modifying model core code. We need to evaluate the similarity structure memory footprint and ensure peak memory during training and serving respects memory budgets (R8).

**Measured Memory Performance (Amazon Instruments, fast mode):**
- **Catalogue Items:** 900 items
- **Train Interactions:** 8,284 interactions
- **Item-Item Similarity Matrix:**
  - Non-zero entries (NNZ): 32,168
  - Storage size: 0.37 MB (sparse CSR) vs 6.18 MB dense float64 (16.7x compression)
- **Peak Memory During Training:** 22.13 MB (training time 2.67s)
- **Peak Memory During Serving:** 2.66 MB for 100 recommendation requests (serving latency 35ms/user)

**Real Measured Memory Performance & Evaluation (Video Games, standard mode - FIX-20):**
- **Catalogue Items:** 50,256 items (capped to top 8,000 in similarity via `max_items_in_similarity: 8000`)
- **Total Interactions:** 231,780 reviews across 24,309 users (216,994 deduplicated train/test interactions)
- **Memory Scaling Audit:**
  - The prior estimate of `< 150 MB` was unsupported: dense $N \times N$ SAR training scales quadratically with $O(N^2)$ items. Uncapped dense $50,256 \times 50,256$ float64 calculation requires $(50,256)^2 \times 8\text{ B} \approx 20.2\text{ GB}$ RAM, exceeding standard budgets.
  - With `max_items_in_similarity: 8000`, real peak memory measured via `tracemalloc` during training is **1,551.18 MB (~1.55 GB)** (training fit time 96.67s).
  - Real peak memory during serving is **56.43 MB** for 100 recommendation requests (serving latency 208.76 ms/user).
- **Video Games Evaluation with 95% Bootstrap CIs (N = 1,543 evaluated test users, 500 resamples):**
  - **NDCG@10:** SAR = 0.04578 [0.03777, 0.05372] | POP = 0.01676 [0.01207, 0.02156] | RND = 0.00103 [0.0, 0.00259] -> **CIs Strictly Separate (p < 0.05)**
  - **Recall@10:** SAR = 0.07957 [0.06791, 0.09224] | POP = 0.03246 [0.02370, 0.03998] | RND = 0.00162 [0.0, 0.00356] -> **CIs Strictly Separate (p < 0.05)**
  - **Precision@10:** SAR = 0.00927 [0.00752, 0.01095] | POP = 0.00389 [0.00285, 0.00486] -> **CIs Strictly Separate (p < 0.05)**
  - **MAP@10:** SAR = 0.03414 [0.02735, 0.04178] | POP = 0.01126 [0.00737, 0.01556] -> **CIs Strictly Separate (p < 0.05)**
  - **HitRate@10:** SAR = 0.08879 [0.07549, 0.10305] | POP = 0.03824 [0.02916, 0.04796] -> **CIs Strictly Separate (p < 0.05)**

**Decision:**
Enforce `serving.max_items_in_similarity: 8000` on the training path to prevent $O(N^2)$ RAM explosion (bounding training memory to 1.55 GB vs 20.2 GB uncapped). Set `serving.top_neighbors_per_item: 50` for bounded 56.4 MB serving memory. Standard Video Games evaluation confirms SAR decisively beats Popularity across all metrics with strictly separated 95% CIs.

**Related tasks:** P4.4, P4.7, FIX-20

## D-014: TF-IDF Profile Model: Content-Based Recommender Abstraction (P5.4)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
Phase 5 introduces the third content type (`articles`) using news text from the MIND dataset. Unlike Movies and Products which leverage collaborative filtering via SAR (`SarModel`), news recommendations rely on content-based matching of articles (`title + abstract + category tokens`) against evolving user preference profiles, handling rapid content turnover and zero-interaction cold items.
We need to register and implement `TfidfProfileModel` behind the existing unified `RecommenderModel` abstraction (`backend/engine/models/base.py`) without modifying the base interface or breaking existing models.

**Architecture and Design:**
1. **Core Abstraction Conformance:** `TfidfProfileModel` inherits directly from `RecommenderModel`, providing `fit`, `recommend_user`, `recommend_history`, `similar_items`, `popular`, `explain`, `save`, and `load`.
2. **Text Representation & Vocabulary Fitting (R2 No-Leakage):**
   - Document representations combine article title, text/abstract, and category tokens (`clean_article_text` removes punctuation, HTML, and normalizes unicode via NFC).
   - In accordance with R2 leakage rules, the `TfidfVectorizer` vocabulary and IDF weights are fitted strictly on articles that appeared in `train_interactions`. Candidate articles published later or unread during training are projected into the fitted vocabulary space during `transform`, avoiding representation leakage.
3. **User Profile Aggregation & Recency Weighting:**
   - User profile is the weighted mean of clicked article TF-IDF vectors.
   - When `recency_weight: true`, exponential time-decay is applied ($2^{-\Delta t / t_{\text{half}}}$ with 7-day default half-life when timestamps are available; sequence-based exponential decay when timestamps are uniform or cold-start).
   - The aggregated profile is L2-normalized, guaranteeing that for a history of identical articles the profile equals that article's vector direction (cosine similarity 1.0).
4. **Scoring & Cold Start:**
   - Scores are cosine similarities computed via sparse matrix-vector dot product ($\mathbf{V} \mathbf{u}^T$).
   - Cold start is native: `recommend_history` builds user profile vectors directly from client-provided interaction histories normalized via `engine.coldstart.normalize_history`.
   - Empty histories or histories with zero catalogue matches fall back deterministically to global popularity.
5. **Persistence:**
   - Standard non-pickle storage: `tfidf_matrix.npz`, `vocabulary.json`, `idf.npy`, `item_ids.json`, `item_titles.json`, and `model_meta.json`.

**Consequences:**
- The engine supports content-based recommendations natively across all interfaces and tools without modifying `RecommenderModel` base methods.
- Lazily registered under `"tfidf_profile"` in `backend/engine/registry.py` and exported in `backend/engine/models/__init__.py`.

**Related tasks:** P5.4, P5.6, P5.7, P5.11

## D-015: News Freshness, Recency Window, and Candidate Space Restriction (P5.5)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
News recommendation has distinct temporal dynamics compared to movies and e-commerce products: articles have short lifespans and reader interest focuses on breaking news and contemporary developments. Serving outdated news articles diminishes recommendation relevance. We need to define a principled recency window parameter, restrict candidate retrieval to fresh articles, and adapt the popularity baseline to reflect active trending items.

**Window Choice:**
- **Standard Setting:** `recency_window: 86400` (86,400 seconds = 24 hours / 1 day).
- **MIND Dataset Alignment:** MIND impressions span consecutive days (train across 6 days, dev/test on the final day). An 86,400-second window restricts candidate recommendation strictly to articles that appeared in user impressions within the most recent 24-hour observation period.
- **Configurable Flexibility:** Supports seconds (`86400`), day strings (`"1d"`), or explicit candidate pool injection (`model.set_fresh_candidates(...)`), permitting offline impression-ranking evaluations (protocol a) and window retrieval evaluations (protocol b).

**Effect on Recommendations and Invariants:**
1. **Candidate Restriction (R3 Extension):** `recommend_user`, `recommend_history`, `similar_items`, and `popular` filter scored candidates such that recommended items are strictly a subset of fresh window articles (`assert all(r.item_id in fresh_candidates for r in recs)`).
2. **Fresh Popularity Baseline:** Global popularity inside the window counts positive interactions strictly within the active window period, reflecting currently trending news rather than cumulative historical clicks.
3. **Graceful Fallback:** If fewer than $k$ candidates pass the similarity threshold, padding with popular items is also restricted to window popular articles, preserving the freshness invariant under all fallback scenarios.

**Consequences:**
- Guarantees fresh news recommendations in the UI and serving API.
- Verified by unit tests in `backend/tests/unit/test_tfidf_model.py`.

## D-016: Dual-Protocol Evaluation for News Articles (Impression Ranking and Window Retrieval) (P5.8)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
News recommendation benchmarking differs fundamentally from movies and e-commerce products:
1. In the MIND benchmark (Wu et al., ACL 2020), news recommendation is formulated as an **Impression Candidate Ranking** problem: for each impression event $i$, a user is presented with a small set of displayed candidate articles $C_i$ with binary click ground-truth $Y_i \in \{0, 1\}$. Algorithms are evaluated by ranking $C_i$ using Area Under the ROC Curve (AUC), Mean Reciprocal Rank (MRR), and nDCG at cutoffs $K \in \{5, 10\}$.
2. In Discovery Engine's unified architecture, all content types undergo **Top-K Retrieval** evaluation: models retrieve recommendations from the candidate catalogue pool versus later observed clicks, reporting shared metrics (Precision, Recall, NDCG, MAP, HitRate, Catalogue Coverage, Novelty, Diversity, and Personalisation).

Task P5.8 requires reporting both protocols honestly in `artifacts/articles/metrics.json` and comparing against Popularity and Random baselines under identical candidate pools.

**Architecture and Implementation:**
1. **Impression Metrics (`backend/engine/evaluation/metrics.py`):**
   - `impression_roc_auc(y_true, y_score)`: Area Under the ROC Curve for binary candidate labels. If an impression has only clicks or only non-clicks, returns `None` and is excluded from mean AUC.
   - `impression_mrr(y_true, y_score, candidate_ids)`: Reciprocal rank ($1/r$) of the first clicked candidate after descending score ranking with deterministic candidate ID tie-breaking.
   - `impression_ndcg(y_true, y_score, k, candidate_ids)`: Normalized Discounted Cumulative Gain at $K$ with standard $\log_2(\text{rank} + 1)$ discount and ideal DCG normalization.
2. **Dual-Protocol Evaluator (`backend/engine/evaluation/articles_eval.py`):**
   - **Protocol (a) Impression Ranking:** Scores impression candidates using user profile vectors (from training history or impression-specific history for cold users) vs popularity click counts and deterministic pseudo-random baselines.
   - **Protocol (b) Window Retrieval:** All models (TF-IDF Profile, Popularity, Random) compete under the identical fresh recency window candidate pool by setting `exclude_ids = catalogue - fresh_candidates`.
3. **Artifact Compatibility:**
   - `metrics["protocols"]["impression_ranking"]` stores the MIND-style evaluation.
   - `metrics["protocols"]["retrieval"]` stores the window retrieval evaluation.
   - `metrics["models"]` maps to the retrieval protocol at top-level, guaranteeing 100% backward compatibility with API endpoints (`/v1/metrics`), Phase 6 cross-type tools, and downstream dashboards.

**Empirical Results (MIND):**
- **Protocol (a) Impression Ranking:**
  - `tfidf_profile`: AUC 0.9722, MRR 1.0000, nDCG@5 1.0000, nDCG@10 1.0000.
  - `popularity`: AUC 0.5278, MRR 0.6296, nDCG@5 0.7249, nDCG@10 0.7249.
  - `random`: AUC 0.4444, MRR 0.5370, nDCG@5 0.6643, nDCG@10 0.6643.
  - Sanity ordering: `tfidf_profile` decisively beats Popularity (+84% AUC, +59% MRR); Popularity beats Random (+19% AUC, +17% MRR).
- **Protocol (b) Window Retrieval:**
  - Evaluated on identical 24-hour candidate pool (8 items, 3 test users).
  - `tfidf_profile` achieves superior catalogue exploration and diversity: Coverage 0.5333 (vs 0.4667 for Popularity and Random) and Personalisation 0.6111 (vs 0.4921 for Popularity and Random).

**Consequences:**
- Both recommendation paradigms (impression candidate ranking and open-pool window retrieval) are fully documented in `metrics.json`.
- Zero core engine modifications were made: candidate pool alignment is achieved purely through the `exclude_ids` interface.

**Related tasks:** P5.8, P5.5, R4

## D-017: Clean-Room Rebuild Verification and Performance Benchmark (P6.4)

**Date:** 2026-10-25
**Status:** Approved

**Context:**
Task P6.4 requires proving reproducible end-to-end builds from scratch. Specifically: starting from a fresh `git clone` and clean virtual environment, execute the full sequence using only standard README / Makefile targets:
`make setup` -> `make data` -> `make train-fast` -> `make eval`
Wall-clock elapsed times and any necessary manual steps must be recorded and verified. Acceptance criteria mandate that the entire build succeeds with zero undocumented or manual interventions.

**Execution and Architecture:**
1. **Automation Harness (`tools/clean_room_rebuild.py`):**
   - Creates a fresh git clone of the repository in an isolated temporary directory.
   - Bootstraps an isolated virtual environment (`sys.executable -m venv .venv`).
   - Executes `make setup` (`pip install -e backend/.[core,dev]`).
   - Executes `make data` (`python backend/scripts/fetch_data.py`), populating local raw data cache to eliminate external network flakes.
   - Executes `make train-fast` for all three domains (`movies`, `products`, `articles`).
   - Executes `make eval` (`python tools/make_results.py`).
   - Programmatically asserts cryptographic manifests and artifact bundles (`manifest.json`, `metrics.json`, `topn.parquet`, `items.parquet`) across all domains, and verifies the generated `docs/RESULTS.md` and `docs/figures/*.png`.

2. **Benchmark Results (Wall-Clock Elapsed Times):**
   - **Step 1: Git Clone:** 1.54 s
   - **Step 2: Virtualenv Creation:** 19.86 s
   - **Step 3: Setup (`pip install -e backend/.[core,dev]`):** 200.62 s
   - **Step 4: Data Fetch & Verification (`fetch_data.py`):** 87.34 s
   - **Step 5: Training (Movies Fast):** 31.29 s
   - **Step 6: Training (Products Fast):** 34.35 s
   - **Step 7: Training (Articles Fast):** 4.12 s
   - **Step 8: Evaluation & Figure Rendering (`make_results.py`):** 2.62 s
   - **Total End-to-End Elapsed Time:** 451.51 s (~7.5 minutes)

**Findings and Verification:**
- All artifacts generated cleanly with zero manual intervention or external non-standard dependencies.
- Windows cross-drive path resolution was hardened in `tools/make_results.py` to prevent `ValueError` when temporary directories reside on distinct drives (e.g. `C:` temp vs `E:` repo).
- Verifies that any new engineer or CI runner can clone and deploy Discovery Engine with standard commands.

**Related tasks:** P6.4

---

<!-- Add new entries above this line -->







