# Discovery Engine — Backend

The backend recommendation engine for **Discovery Engine**, an adaptive content recommendation system designed for multi-domain discovery (Movies, Products, Articles).

## Architecture

The backend consists of three distinct packages:

1. **`engine/` (Original Core Code)**
   - `adapters/`: Content-type adapters mapping raw datasets to canonical data schemas (`MovieLensAdapter`, `AmazonProductsAdapter`, `MindArticlesAdapter`).
   - `configs/`: Declarative YAML configurations defining dataset parameters, signal thresholds, split strategies, model hyperparameters, and serving budgets.
   - `models/`: Unified recommender model implementations (`SarModel`, `PopularityModel`, `RandomModel`, `TfidfModel`).
   - `evaluation/`: Evaluation harness, chronological splitters, ranking and diversity metrics (NDCG, MAP, Novelty, Diversity, Personalisation), and invariant checkers (R1–R6).
   - `coldstart.py` & `explain.py`: Model-agnostic history normalization and faithful attribution helpers.
   - `artifacts.py`: Checksum-verified artifact serialization (`manifest.json`, `items.parquet`, `interactions.parquet`, `model/`, `topn.parquet`, `metrics.json`).
   - `train.py`: Unified training CLI for offline artifact generation.

2. **`discovery/` (Derived Recommenders Algorithms)**
   - Vendored, trimmed, and renamed package derived from [Recommenders](https://github.com/recommenders-team/recommenders) under the MIT License.
   - Contains algorithmic building blocks (`SARSingleNode`, TF-IDF utilities, python splitters, python evaluation metrics).
   - Free of heavy runtime dependencies (`tensorflow`, `pyspark`, `torch`).

3. **`api/` (Serving Layer)**
   - FastAPI REST API exposing `/v1` endpoints for recommendation serving, cold-start onboarding, model comparison, item search, and evaluation metrics.
   - Serves precomputed artifacts and fast sparse matrix multiplications only.

## Getting Started

### 1. Environment Setup

Python 3.11+ is required.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies in editable mode
pip install -e "backend/.[core,dev]"
```

### 2. Fetch Datasets

```bash
# Fetch MovieLens data
python backend/scripts/fetch_data.py --type movies
```

### 3. Training & Evaluation

```bash
# Run training pipeline for movies (with --fast developer overrides)
python -m engine.train --type movies --fast

# Run full training pipeline
python -m engine.train --type movies
```

### 4. Running Tests and Checks

```bash
# Run full test suite
pytest backend/tests/

# Lint and formatting
ruff check backend/ tools/
ruff format --check backend/ tools/

# Strict type checking
mypy --config-file backend/pyproject.toml backend/engine/ backend/api/
```

### 5. Running the API

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

Each content type is configured declaratively in `engine/configs/<type>.yaml`. Key configuration sections include:

- `dataset`: Raw source adapter, variant, and interaction filtering thresholds.
- `signal`: Positive interaction threshold and rating weighting.
- `split`: Splitting strategy (chronological per-user, impression time).
- `model`: Model selection (`sar`, `tfidf_profile`) and hyperparameters.
- `serving`:
  - `top_neighbors_per_item`: Number of sparse neighbors retained for item similarity.
  - `max_items_in_similarity`: Item catalogue budget cap for similarity matrix.
  - `min_positive_items_for_personalization`: Minimum positive interactions before activating personalized mode (default: 3).
  - `explanation_min_threshold`: Minimum contribution share required to show an explanation reason (default: 0.2).
- `fast`: Developer overrides for quick test and development cycles.
