"""Product-specific evaluation checks for Discovery Engine (Phase 4, P4.6).

Computes and records product domain checks:
1. Sparse-data behavior (ratio and stats of users with <= 5 interactions)
2. Long-tail items (bottom 80% catalogue volume share and recommendation share)
3. Category diversity of top-k recommendations (mean unique categories represented)
4. Similar alternatives quality spot-check (category sharing rate among top-5 similar items)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine.registry import register_post_train_hook


def compute_sparse_data_metrics(
    interactions: pd.DataFrame,
    threshold: int = 5,
) -> dict[str, Any]:
    """Analyze sparse user distribution."""
    user_counts = interactions["user_id"].astype(str).value_counts()
    total_users = len(user_counts)
    sparse_users = user_counts[user_counts <= threshold]
    sparse_count = len(sparse_users)
    ratio = float(sparse_count / total_users) if total_users > 0 else 0.0

    return {
        "threshold_interactions": int(threshold),
        "sparse_user_count": sparse_count,
        "total_users": total_users,
        "sparse_user_ratio": ratio,
        "mean_interactions_per_user": float(user_counts.mean()) if total_users > 0 else 0.0,
        "median_interactions_per_user": float(user_counts.median()) if total_users > 0 else 0.0,
    }


def compute_long_tail_metrics(
    interactions: pd.DataFrame,
    model: Any,
    eval_users: list[str],
    tail_percentile: float = 0.8,
    k: int = 10,
) -> dict[str, Any]:
    """Analyze long-tail item interaction share and recommendation share."""
    item_counts = interactions["item_id"].astype(str).value_counts()
    total_items = len(item_counts)
    total_interactions = len(interactions)

    tail_count = int(total_items * tail_percentile)
    # Bottom 80% items by interaction frequency
    tail_items = set(item_counts.tail(tail_count).index)
    tail_volume = int(item_counts.tail(tail_count).sum())
    volume_share = float(tail_volume / total_interactions) if total_interactions > 0 else 0.0

    # Recommendation share across eval users
    rec_tail_hits = 0
    total_recs = 0
    for u in eval_users:
        try:
            recs = model.recommend_user(user_id=u, k=k)
            for r in recs:
                total_recs += 1
                if str(r.item_id) in tail_items:
                    rec_tail_hits += 1
        except (KeyError, ValueError, RuntimeError):
            continue

    rec_share = float(rec_tail_hits / total_recs) if total_recs > 0 else 0.0

    return {
        "tail_percentile": float(tail_percentile),
        "tail_item_count": tail_count,
        "total_items": total_items,
        "tail_interaction_volume_share": volume_share,
        "tail_recommendation_share_at_k": rec_share,
        "evaluated_recommendations_count": total_recs,
        "k": int(k),
    }


def extract_item_categories(items: pd.DataFrame) -> dict[str, set[str]]:
    """Extract mapping from item_id string to category set."""
    item_cats: dict[str, set[str]] = {}
    for _, row in items.iterrows():
        c = row.get("categories")
        if isinstance(c, (list, tuple, set, np.ndarray)):
            item_cats[str(row["item_id"])] = {str(cat) for cat in c}
        elif pd.notna(c) and str(c).strip() != "":
            item_cats[str(row["item_id"])] = {str(c).strip()}
        else:
            item_cats[str(row["item_id"])] = set()
    return item_cats


def compute_category_diversity_metrics(
    model: Any,
    items: pd.DataFrame,
    eval_users: list[str],
    k: int = 10,
) -> dict[str, Any]:
    """Compute category diversity (mean unique categories) across top-k recommendations."""
    item_cats = extract_item_categories(items)

    user_cat_counts: list[int] = []
    for u in eval_users:
        try:
            recs = model.recommend_user(user_id=u, k=k)
            user_cats: set[str] = set()
            for r in recs:
                user_cats.update(item_cats.get(str(r.item_id), set()))
            user_cat_counts.append(len(user_cats))
        except (KeyError, ValueError, RuntimeError):
            continue

    if not user_cat_counts:
        return {
            "k": int(k),
            "mean_unique_categories": 0.0,
            "min_unique_categories": 0,
            "max_unique_categories": 0,
        }

    return {
        "k": int(k),
        "mean_unique_categories": float(np.mean(user_cat_counts)),
        "min_unique_categories": int(np.min(user_cat_counts)),
        "max_unique_categories": int(np.max(user_cat_counts)),
        "users_evaluated": len(user_cat_counts),
    }


def compute_similar_alternatives_spot_check(
    model: Any,
    items: pd.DataFrame,
    num_query_products: int = 10,
    k_similar: int = 5,
    seed: int = 42,
    target_threshold: float = 0.60,
) -> dict[str, Any]:
    """Spot-check that similar items for random products share categories above target rate."""
    item_cats = extract_item_categories(items)

    # Filter to items known to the model that have non-empty categories
    known_items: set[str] = set()
    if hasattr(model, "sar") and hasattr(model.sar, "item2index"):
        known_items = set(model.sar.item2index.keys())
    elif hasattr(model, "item_ids"):
        known_items = {str(i) for i in model.item_ids}

    valid_candidates = [
        str(iid)
        for iid in items["item_id"]
        if str(iid) in known_items and len(item_cats.get(str(iid), set())) > 0
    ]

    if not valid_candidates:
        return {
            "num_query_products": 0,
            "k_similar": int(k_similar),
            "total_recommendations_evaluated": 0,
            "shared_category_count": 0,
            "shared_category_rate": 0.0,
            "target_threshold": float(target_threshold),
            "passed": False,
        }

    sample_size = min(num_query_products, len(valid_candidates))
    rng = np.random.RandomState(seed)
    sampled = rng.choice(valid_candidates, size=sample_size, replace=False)

    shared_count = 0
    total_sims = 0
    query_details = []

    for q_id in sampled:
        q_cats = item_cats[q_id]
        try:
            sims = model.similar_items(item_id=q_id, k=k_similar)
        except (KeyError, ValueError, RuntimeError):
            continue

        q_shared = 0
        for s in sims:
            total_sims += 1
            s_cats = item_cats.get(str(s.item_id), set())
            if q_cats.intersection(s_cats):
                shared_count += 1
                q_shared += 1

        query_details.append(
            {
                "query_item_id": q_id,
                "query_categories": sorted(q_cats),
                "similar_count": len(sims),
                "shared_count": q_shared,
            }
        )

    rate = float(shared_count / total_sims) if total_sims > 0 else 0.0
    passed = bool(rate >= target_threshold)

    return {
        "num_query_products": sample_size,
        "k_similar": int(k_similar),
        "total_recommendations_evaluated": total_sims,
        "shared_category_count": shared_count,
        "shared_category_rate": rate,
        "target_threshold": float(target_threshold),
        "passed": passed,
        "query_details": query_details,
    }


def compute_product_specific_checks(
    model: Any,
    interactions: pd.DataFrame,
    items: pd.DataFrame,
    eval_users: list[str] | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute all product-specific checks (P4.6)."""
    if eval_users is None:
        if hasattr(model, "sar") and hasattr(model.sar, "user2index"):
            eval_users = list(model.sar.user2index.keys())[:50]
        else:
            eval_users = list(interactions["user_id"].astype(str).unique())[:50]

    sparse_metrics = compute_sparse_data_metrics(interactions, threshold=5)
    long_tail_metrics = compute_long_tail_metrics(
        interactions, model, eval_users, tail_percentile=0.8, k=10
    )
    diversity_metrics = compute_category_diversity_metrics(model, items, eval_users, k=10)
    spot_check_metrics = compute_similar_alternatives_spot_check(
        model,
        items,
        num_query_products=10,
        k_similar=5,
        seed=seed,
        target_threshold=0.60,
    )

    return {
        "sparse_data": sparse_metrics,
        "long_tail": long_tail_metrics,
        "category_diversity": diversity_metrics,
        "similar_alternatives_spot_check": spot_check_metrics,
    }


@register_post_train_hook("product_checks")
def run_product_checks_hook(
    model: Any,
    interactions: pd.DataFrame,
    items: pd.DataFrame,
    spec: Any = None,
    seed: int = 42,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute product-specific evaluation checks post-train hook."""
    results = compute_product_specific_checks(
        model=model,
        interactions=interactions,
        items=items,
        seed=seed,
    )
    return {"product_specific_checks": results}
