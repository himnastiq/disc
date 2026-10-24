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
  interactions.parquet   # train + test interactions (flagged)
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

<!-- TODO: document after P2.8 -->
