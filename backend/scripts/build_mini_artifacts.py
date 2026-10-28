"""Generate synthetic mini-artifacts for testing Discovery Engine without raw data (FIX-31).

Generates a few hundred rows each for:
- movies (SAR)
- products (SAR)
- articles (TF-IDF Content Model)

Each artifact directory contains:
- items.parquet
- interactions.parquet
- users.parquet
- topn.parquet
- metrics.json
- demo_users.json
- model/
- manifest.json (with SHA-256 checksums)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from engine.artifacts import save_artifacts, verify_artifacts
from engine.config import load_config
from engine.demo_users import select_demo_users_from_dfs
from engine.models.sar import SarModel
from engine.models.tfidf import TfidfProfileModel
from engine.train import compute_user_stats_and_personas, precompute_topn_for_users

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_BASE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "artifacts_mini"


def build_mini_movies(out_dir: Path) -> None:
    """Build mini movies artifact bundle."""
    spec = load_config("movies", fast=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Items
    genres_pool = [
        ["Action", "Thriller"],
        ["Comedy", "Romance"],
        ["Drama"],
        ["Sci-Fi", "Action"],
        ["Animation", "Children"],
        ["Crime", "Drama"],
    ]
    specific_titles = {
        1: ("The Matrix", ["Action", "Sci-Fi"]),
        2: ("Matrix Reloaded", ["Action", "Sci-Fi"]),
        3: ("Star Wars", ["Sci-Fi", "Action"]),
        4: ("Pulp Fiction", ["Crime", "Drama"]),
        5: ("Avatar", ["Action", "Sci-Fi"]),
    }
    items_rows = []
    for i in range(1, 61):
        iid = str(i)
        if i in specific_titles:
            title, cats = specific_titles[i]
        else:
            title = f"Action Movie {i}"
            cats = genres_pool[i % len(genres_pool)]
        items_rows.append(
            {
                "item_id": iid,
                "title": title,
                "subtitle": f"Director {i % 10}",
                "categories": cats,
                "year": 1990 + (i % 30),
                "image_url": f"https://example.com/movies/{iid}.jpg",
                "text": f"A great movie titled {title} with dramatic action and fun.",
            }
        )
    items_df = pd.DataFrame(items_rows)

    # 2. Interactions
    rng = np.random.RandomState(42)
    inter_rows = []
    base_ts = 1_000_000_000

    # Ensure user '1' has diverse positive interactions
    for item_idx in range(1, 15):
        inter_rows.append(
            {
                "user_id": "1",
                "item_id": str(item_idx),
                "signal": 5.0,
                "timestamp": base_ts + item_idx * 3600,
                "positive": True,
            }
        )

    # Ensure user '2' has only 1 positive interaction (for below min positives test)
    inter_rows.append(
        {
            "user_id": "2",
            "item_id": "1",
            "signal": 5.0,
            "timestamp": base_ts + 100,
            "positive": True,
        }
    )
    inter_rows.append(
        {
            "user_id": "2",
            "item_id": "2",
            "signal": 2.0,
            "timestamp": base_ts + 200,
            "positive": False,
        }
    )

    # Remaining users 3..35
    for u in range(3, 36):
        uid = str(u)
        n_items = rng.randint(5, 15)
        chosen_items = rng.choice(range(1, 61), size=n_items, replace=False)
        for idx, iid in enumerate(chosen_items):
            sig = float(rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], p=[0.1, 0.1, 0.2, 0.3, 0.3]))
            pos = sig >= spec.signal.positive_threshold
            inter_rows.append(
                {
                    "user_id": uid,
                    "item_id": str(iid),
                    "signal": sig,
                    "timestamp": base_ts + u * 10000 + idx * 60,
                    "positive": pos,
                }
            )

    inter_df = pd.DataFrame(inter_rows)

    # 3. Fit SAR Model
    model = SarModel(spec)
    model.fit(inter_df, items_df)
    model_dir = out_dir / "model"
    model.save(model_dir)

    # 4. User stats & Top-N
    users_df = compute_user_stats_and_personas(inter_df, items_df)
    all_uids = list(users_df["user_id"].unique())
    topn_df = precompute_topn_for_users(model, all_uids, k=20)

    # 5. Demo users
    demo_users = select_demo_users_from_dfs(users_df, topn_df, target_count=4)
    if not demo_users:
        demo_users = [
            {
                "user_id": "1",
                "persona": "heavy",
                "interaction_count": 14,
                "top_categories": ["Action"],
            },
            {
                "user_id": "2",
                "persona": "casual",
                "interaction_count": 2,
                "top_categories": ["Action"],
            },
        ]

    # 6. Metrics
    metrics_dict = {
        "content_type": "movies",
        "dataset_variant": "mini_synthetic",
        "models": {
            "sar": {
                "5": {"ndcg": 0.45, "hit_rate": 0.55, "recall": 0.35},
                "10": {"ndcg": 0.50, "hit_rate": 0.60, "recall": 0.40},
                "20": {"ndcg": 0.55, "hit_rate": 0.65, "recall": 0.45},
            },
            "popularity": {
                "5": {"ndcg": 0.25, "hit_rate": 0.35, "recall": 0.15},
                "10": {"ndcg": 0.30, "hit_rate": 0.40, "recall": 0.20},
                "20": {"ndcg": 0.35, "hit_rate": 0.45, "recall": 0.25},
            },
            "random": {
                "5": {"ndcg": 0.05, "hit_rate": 0.05, "recall": 0.02},
                "10": {"ndcg": 0.08, "hit_rate": 0.08, "recall": 0.04},
                "20": {"ndcg": 0.10, "hit_rate": 0.10, "recall": 0.06},
            },
        },
        "sanity_checks": {
            "all_bounds_valid": True,
            "popularity_beats_random": True,
            "leakage_check_passed": True,
            "model_beats_popularity": True,
        },
        "cold_start_curves": {
            "sar": {
                "0": {"ndcg@10": 0.2, "hit_rate@10": 0.3, "recall@10": 0.2},
                "1": {"ndcg@10": 0.3, "hit_rate@10": 0.4, "recall@10": 0.3},
                "5": {"ndcg@10": 0.5, "hit_rate@10": 0.6, "recall@10": 0.4},
            }
        },
    }

    save_artifacts(
        out_dir, spec, items_df, inter_df, users_df, metrics_dict, demo_users, topn=topn_df
    )
    verify_artifacts(out_dir)
    print(f"Movies mini artifacts built successfully at {out_dir}")


def build_mini_products(out_dir: Path) -> None:
    """Build mini products artifact bundle."""
    spec = load_config("products", fast=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    cats_pool = [
        ["Musical Instruments", "Guitars"],
        ["Musical Instruments", "Accessories"],
        ["Musical Instruments", "Drums"],
        ["Musical Instruments", "Keyboards"],
        ["Musical Instruments", "Microphones"],
    ]

    items_rows = []
    for i in range(1, 61):
        asin = f"B00{i:03d}"
        items_rows.append(
            {
                "item_id": asin,
                "title": f"Instrument Accessory {i}",
                "subtitle": f"Brand {i % 5}",
                "categories": cats_pool[i % len(cats_pool)],
                "year": 2015 + (i % 10),
                "image_url": f"https://example.com/products/{asin}.jpg",
                "text": f"High quality instrument accessory {i} for musicians.",
            }
        )
    items_df = pd.DataFrame(items_rows)

    rng = np.random.RandomState(43)
    inter_rows = []
    base_ts = 1_000_000_000

    # Ensure user '1' has >= 5 positives
    for item_idx in range(1, 15):
        asin = f"B00{item_idx:03d}"
        inter_rows.append(
            {
                "user_id": "1",
                "item_id": asin,
                "signal": 5.0,
                "timestamp": base_ts + item_idx * 3600,
                "positive": True,
            }
        )

    # Ensure user '2' has only 1 positive
    inter_rows.append(
        {
            "user_id": "2",
            "item_id": "B00001",
            "signal": 5.0,
            "timestamp": base_ts + 100,
            "positive": True,
        }
    )
    inter_rows.append(
        {
            "user_id": "2",
            "item_id": "B00002",
            "signal": 2.0,
            "timestamp": base_ts + 200,
            "positive": False,
        }
    )

    for u in range(3, 36):
        uid = str(u)
        n_items = rng.randint(5, 15)
        chosen_items = rng.choice(range(1, 61), size=n_items, replace=False)
        for idx, iid in enumerate(chosen_items):
            asin = f"B00{iid:03d}"
            sig = float(rng.choice([1.0, 2.0, 3.0, 4.0, 5.0], p=[0.1, 0.1, 0.2, 0.3, 0.3]))
            pos = sig >= spec.signal.positive_threshold
            inter_rows.append(
                {
                    "user_id": uid,
                    "item_id": asin,
                    "signal": sig,
                    "timestamp": base_ts + u * 10000 + idx * 60,
                    "positive": pos,
                }
            )

    inter_df = pd.DataFrame(inter_rows)

    model = SarModel(spec)
    model.fit(inter_df, items_df)
    model_dir = out_dir / "model"
    model.save(model_dir)

    users_df = compute_user_stats_and_personas(inter_df, items_df)
    all_uids = list(users_df["user_id"].unique())
    topn_df = precompute_topn_for_users(model, all_uids, k=20)

    demo_users = select_demo_users_from_dfs(users_df, topn_df, target_count=4)
    if not demo_users:
        demo_users = [
            {
                "user_id": "1",
                "persona": "heavy",
                "interaction_count": 14,
                "top_categories": ["Guitars"],
            },
            {
                "user_id": "2",
                "persona": "casual",
                "interaction_count": 2,
                "top_categories": ["Guitars"],
            },
        ]

    metrics_dict = {
        "content_type": "products",
        "dataset_variant": "mini_synthetic",
        "models": {
            "sar": {
                "5": {"ndcg": 0.42, "hit_rate": 0.52, "recall": 0.32},
                "10": {"ndcg": 0.48, "hit_rate": 0.58, "recall": 0.38},
                "20": {"ndcg": 0.52, "hit_rate": 0.62, "recall": 0.42},
            },
            "popularity": {
                "5": {"ndcg": 0.22, "hit_rate": 0.32, "recall": 0.12},
                "10": {"ndcg": 0.28, "hit_rate": 0.38, "recall": 0.18},
                "20": {"ndcg": 0.32, "hit_rate": 0.42, "recall": 0.22},
            },
            "random": {
                "5": {"ndcg": 0.04, "hit_rate": 0.04, "recall": 0.01},
                "10": {"ndcg": 0.07, "hit_rate": 0.07, "recall": 0.03},
                "20": {"ndcg": 0.09, "hit_rate": 0.09, "recall": 0.05},
            },
        },
        "sanity_checks": {
            "all_bounds_valid": True,
            "popularity_beats_random": True,
            "leakage_check_passed": True,
            "model_beats_popularity": True,
        },
        "cold_start_curves": {
            "sar": {
                "0": {"ndcg@10": 0.18, "hit_rate@10": 0.28, "recall@10": 0.18},
                "1": {"ndcg@10": 0.28, "hit_rate@10": 0.38, "recall@10": 0.28},
                "5": {"ndcg@10": 0.48, "hit_rate@10": 0.58, "recall@10": 0.38},
            }
        },
    }

    save_artifacts(
        out_dir, spec, items_df, inter_df, users_df, metrics_dict, demo_users, topn=topn_df
    )
    verify_artifacts(out_dir)
    print(f"Products mini artifacts built successfully at {out_dir}")


def build_mini_articles(out_dir: Path) -> None:
    """Build mini articles artifact bundle."""
    spec = load_config("articles", fast=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    topics = [
        ("technology", "Artificial intelligence breakthroughs and computing advancements"),
        ("finance", "Global stock markets and fiscal economy policy updates"),
        ("sports", "Championship matches and football tournament results"),
        ("health", "Nutrition science and healthy lifestyle medical research"),
        ("science", "Space exploration telescope discoveries and planetary science"),
    ]

    items_rows = []
    for i in range(1, 61):
        nid = f"N{i}"
        topic, text_base = topics[i % len(topics)]
        items_rows.append(
            {
                "item_id": nid,
                "title": f"Article {i}: {topic.capitalize()} Trends",
                "subtitle": f"Editor {i % 4}",
                "categories": [topic],
                "year": 2026,
                "image_url": f"https://example.com/articles/{nid}.jpg",
                "text": f"{text_base} report number {i} with key insights on {topic}.",
            }
        )
    items_df = pd.DataFrame(items_rows)

    rng = np.random.RandomState(44)
    inter_rows = []
    base_ts = 1_000_000_000

    # User '1' has >= 5 positives
    for item_idx in range(1, 15):
        nid = f"N{item_idx}"
        inter_rows.append(
            {
                "user_id": "1",
                "item_id": nid,
                "signal": 1.0,
                "timestamp": base_ts + item_idx * 3600,
                "positive": True,
            }
        )

    # User '2' has only 1 positive
    inter_rows.append(
        {
            "user_id": "2",
            "item_id": "N1",
            "signal": 1.0,
            "timestamp": base_ts + 100,
            "positive": True,
        }
    )

    for u in range(3, 36):
        uid = str(u)
        n_items = rng.randint(5, 15)
        chosen_items = rng.choice(range(1, 61), size=n_items, replace=False)
        for idx, iid in enumerate(chosen_items):
            nid = f"N{iid}"
            inter_rows.append(
                {
                    "user_id": uid,
                    "item_id": nid,
                    "signal": 1.0,
                    "timestamp": base_ts + u * 10000 + idx * 60,
                    "positive": True,
                }
            )

    inter_df = pd.DataFrame(inter_rows)

    model = TfidfProfileModel(spec)
    model.fit(inter_df, items_df)
    model_dir = out_dir / "model"
    model.save(model_dir)

    users_df = compute_user_stats_and_personas(inter_df, items_df)
    all_uids = list(users_df["user_id"].unique())
    topn_df = precompute_topn_for_users(model, all_uids, k=20)

    demo_users = select_demo_users_from_dfs(users_df, topn_df, target_count=4)
    if not demo_users:
        demo_users = [
            {
                "user_id": "1",
                "persona": "heavy",
                "interaction_count": 14,
                "top_categories": ["technology"],
            },
            {
                "user_id": "2",
                "persona": "casual",
                "interaction_count": 1,
                "top_categories": ["technology"],
            },
        ]

    metrics_dict = {
        "content_type": "articles",
        "dataset_variant": "SYNTHETIC DEMO (not MIND)",
        "synthetic_demo": True,
        "is_synthetic": True,
        "provenance_banner": "SYNTHETIC DEMO DATASET: Not official MIND benchmark results.",
        "models": {
            "tfidf_profile": {
                "5": {"ndcg": 0.40, "hit_rate": 0.50, "recall": 0.30},
                "10": {"ndcg": 0.45, "hit_rate": 0.55, "recall": 0.35},
                "20": {"ndcg": 0.50, "hit_rate": 0.60, "recall": 0.40},
            },
            "popularity": {
                "5": {"ndcg": 0.20, "hit_rate": 0.30, "recall": 0.10},
                "10": {"ndcg": 0.25, "hit_rate": 0.35, "recall": 0.15},
                "20": {"ndcg": 0.30, "hit_rate": 0.40, "recall": 0.20},
            },
            "random": {
                "5": {"ndcg": 0.03, "hit_rate": 0.03, "recall": 0.01},
                "10": {"ndcg": 0.05, "hit_rate": 0.05, "recall": 0.02},
                "20": {"ndcg": 0.08, "hit_rate": 0.08, "recall": 0.03},
            },
        },
        "sanity_checks": {
            "all_bounds_valid": True,
            "popularity_beats_random": True,
            "leakage_check_passed": True,
            "model_beats_popularity": True,
        },
        "cold_start_curves": {
            "tfidf_profile": {
                "0": {"ndcg@10": 0.15, "hit_rate@10": 0.25, "recall@10": 0.15},
                "1": {"ndcg@10": 0.25, "hit_rate@10": 0.35, "recall@10": 0.25},
                "5": {"ndcg@10": 0.45, "hit_rate@10": 0.55, "recall@10": 0.35},
            }
        },
    }

    save_artifacts(
        out_dir,
        spec,
        items_df,
        inter_df,
        users_df,
        metrics_dict,
        demo_users,
        topn=topn_df,
        dataset_source="fixture",
    )
    verify_artifacts(out_dir)
    print(f"Articles mini artifacts built successfully at {out_dir}")


def main() -> None:
    """Build all mini artifacts."""
    TARGET_BASE_DIR.mkdir(parents=True, exist_ok=True)
    build_mini_movies(TARGET_BASE_DIR / "movies")
    build_mini_products(TARGET_BASE_DIR / "products")
    build_mini_articles(TARGET_BASE_DIR / "articles")
    print("All mini artifacts generated and verified successfully.")


if __name__ == "__main__":
    main()
