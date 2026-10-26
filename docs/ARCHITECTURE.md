# Architecture

<!-- TODO: Full architecture documentation with Mermaid diagrams will be added in Phase 11 (P11.2). -->

## System Overview

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

## Artifact Layout

```
artifacts/<type>/
  manifest.json         # version, checksums, metadata
  items.parquet          # item catalogue
  interactions.parquet   # canonical interactions (train/test splits dynamically derived via adapter)
  users.parquet          # precomputed user stats and personas
  model/                 # model-specific files (sparse neighbours, TF-IDF, etc.)
  topn.parquet           # precomputed top-50 per known user
  metrics.json           # evaluation results
  demo_users.json        # selected diverse demo users
  data_report.json       # data validation report
  tuning.json            # hyperparameter search results
```

## Key Design Principle

One engine, one interface. Each content type plugs in through:
1. A **dataset adapter** (data to unified schema)
2. A **config file** (signal rules, model choice, hyperparameters, split strategy, card type)

Adding a content type requires no changes to engine core code.

## `metrics.json` Schema

The evaluation harness produces a canonical `metrics.json` file stored in `artifacts/<type>/metrics.json`:

```json
{
  "protocol": {
    "split_strategy": "chronological",
    "split_ratio": 0.8,
    "allow_repeat": false,
    "positive_threshold": 4.0,
    "total_interactions": 100000,
    "total_items": 1682,
    "evaluated_test_users": 200
  },
  "seeds": {
    "split_seed": 42,
    "model_seed": 42
  },
  "config_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "git_sha": "9e2a148",
  "created_at": "2026-10-24T18:55:00Z",
  "content_type": "movies",
  "dataset_variant": "100k",
  "k_values": [5, 10, 20],
  "models": {
    "popularity": {
      "10": {
        "precision": 0.082,
        "recall": 0.045,
        "ndcg": 0.095,
        "map": 0.038,
        "hit_rate": 0.42,
        "coverage": 0.065,
        "novelty": 7.42,
        "diversity": 0.68,
        "personalisation": 0.0
      }
    },
    "random": {
      "10": {
        "precision": 0.005,
        "recall": 0.002,
        "ndcg": 0.006,
        "map": 0.002,
        "hit_rate": 0.04,
        "coverage": 0.85,
        "novelty": 10.5,
        "diversity": 0.82,
        "personalisation": 0.98
      }
    },
    "sar": {
      "10": {
        "precision": 0.124,
        "recall": 0.081,
        "ndcg": 0.142,
        "map": 0.065,
        "hit_rate": 0.58,
        "coverage": 0.35,
        "novelty": 8.95,
        "diversity": 0.74,
        "personalisation": 0.88
      }
    }
  },
  "cold_start_curves": {
    "sar": {
      "0": { "hit_rate@10": 0.42, "ndcg@10": 0.095, "recall@10": 0.045 },
      "1": { "hit_rate@10": 0.46, "ndcg@10": 0.108, "recall@10": 0.052 },
      "5": { "hit_rate@10": 0.54, "ndcg@10": 0.131, "recall@10": 0.072 },
      "10": { "hit_rate@10": 0.58, "ndcg@10": 0.142, "recall@10": 0.081 }
    }
  },
  "sanity_checks": {
    "popularity_beats_random": true,
    "model_beats_popularity": true
  }
}
```

