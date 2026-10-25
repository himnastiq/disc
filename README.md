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
| Articles | MIND | TF-IDF content model | Clicks |

## Dataset Citations

- **MovieLens:** Harper, F.M. and Konstan, J.A. (2015). The MovieLens Datasets: History and Context. ACM TiiS.
- **MIND:** Wu, F. et al. (2020). MIND: A Large-scale Dataset for News Recommendation. ACL.
- **Amazon Reviews:** See `docs/DATASETS.md` for full citation.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

The vendored `backend/discovery/` package retains the original MIT License from Recommenders. See [`backend/discovery/LICENSE`](backend/discovery/LICENSE).
