# Discovery Engine

An adaptive content recommendation engine that personalises recommendations across multiple content types (Movies, Products, Articles) through a single, unified engine.

> **Attribution:** This project uses code derived from [Recommenders](https://github.com/recommenders-team/recommenders) (MIT License) by Microsoft/Recommenders contributors. The derived code lives in `backend/discovery/` and is trimmed and renamed from the original package. See [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md) and [`backend/discovery/NOTICE.md`](backend/discovery/NOTICE.md) for full details.

> **Non-commercial:** This project is for educational and research use only. It is not intended for commercial deployment.

## Quick Start

```bash
# 1. Set up the environment
make setup

# 2. Download datasets
make data

# 3. Train models (use train-fast for quick iteration)
make train-fast

# 4. Evaluate models and generate results report
make eval

# 5. Launch the demo (API + frontend)
make demo
```

## Repository Structure

```
discovery-engine/
  backend/
    discovery/   # DERIVED from Recommenders (MIT) — trimmed and renamed
    engine/      # ORIGINAL — adapters, models, evaluation, training
    api/         # ORIGINAL — FastAPI backend
    tests/       # ORIGINAL — unit, property, integration, contract tests
  frontend/      # ORIGINAL — Next.js dashboard
  tools/         # ORIGINAL — build and analysis scripts
  docs/          # Documentation, attribution, results
```

## Content Types

| Type | Dataset | Model | Signal |
|------|---------|-------|--------|
| Movies | MovieLens | SAR | Ratings (≥4 positive) |
| Products | Amazon Reviews | SAR | Ratings/reviews |
| Articles | MIND-small | TF-IDF content model | Clicks |

> [!NOTE]
> **Articles Pipeline (MIND-small):** Articles is trained on the real Microsoft News Dataset (`MIND-small`) under a dual-protocol evaluation (impression ranking and 24h recency window retrieval). When raw MIND data is absent during fast offline tests or CI, the pipeline gracefully falls back to the offline fixture (`backend/tests/fixtures/mind/`) with explicit provenance tracking in `manifest.json`.

## Extensible Post-Train Evaluation Hooks

The training pipeline supports generic, domain-agnostic post-training evaluation hooks configured per content type:

- **Configuration:** Configured in the content type YAML under `evaluation.post_train` (e.g. `post_train: [product_checks]` in `backend/engine/configs/products.yaml`).
- **Generic Execution:** During training (`python -m engine.train`), registered hooks are retrieved dynamically via `engine.registry.get_post_train_hook()` and executed without hardcoded content-type names in engine core. Hook results are automatically merged into `metrics.json`.
- **Integrity Enforcement:** Report generation (`python tools/make_results.py`) strictly enforces that any content type declaring post-train hooks in its configuration contains the corresponding check keys in `metrics.json`, exiting with an error if missing.

## Dataset Citations

- **MovieLens:** Harper, F.M. and Konstan, J.A. (2015). The MovieLens Datasets: History and Context. ACM TiiS.
- **MIND:** Wu, F. et al. (2020). MIND: A Large-scale Dataset for News Recommendation. ACL.
- **Amazon Reviews:** See `docs/DATASETS.md` for full citation.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

The vendored `backend/discovery/` package retains the original MIT License from Recommenders. See [`backend/discovery/LICENSE`](backend/discovery/LICENSE).
