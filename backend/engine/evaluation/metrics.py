"""Discovery Engine - Evaluation metrics (P2.7 / R4).

Wraps vendored ranking metrics (precision, recall, ndcg, map at k) and implements
original metrics: hit rate, catalogue coverage, novelty, intra-list diversity,
and personalisation score.
"""

from __future__ import annotations

import itertools
import math
import random
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from discovery.evaluation.python_evaluation import (
    map_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

if TYPE_CHECKING:
    from collections.abc import Collection


def _get_top_k_per_user(
    df: pd.DataFrame,
    k: int,
    col_user: str = "user_id",
    col_prediction: str = "score",
) -> pd.DataFrame:
    """Filter DataFrame to at most top-k items per user sorted descending by prediction."""
    if df.empty:
        return df.copy()
    sorted_df = df.sort_values(by=[col_user, col_prediction], ascending=[True, False])
    return sorted_df.groupby(col_user, as_index=False).head(k).reset_index(drop=True)


def _clean_ranking_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any pre-existing 'rank' column to prevent merge collisions in vendored metrics."""
    if "rank" in df.columns:
        return df.drop(columns=["rank"])
    return df


def precision(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Compute Precision@K."""
    if true_df.empty or pred_df.empty:
        return 0.0
    return float(
        precision_at_k(
            rating_true=_clean_ranking_df(true_df),
            rating_pred=_clean_ranking_df(pred_df),
            col_user=col_user,
            col_item=col_item,
            col_prediction=col_prediction,
            relevancy_method="top_k",
            k=k,
        )
    )


def recall(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Compute Recall@K."""
    if true_df.empty or pred_df.empty:
        return 0.0
    return float(
        recall_at_k(
            rating_true=_clean_ranking_df(true_df),
            rating_pred=_clean_ranking_df(pred_df),
            col_user=col_user,
            col_item=col_item,
            col_prediction=col_prediction,
            relevancy_method="top_k",
            k=k,
        )
    )


def ndcg(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
    col_rating: str = "signal",
) -> float:
    """Compute NDCG@K."""
    if true_df.empty or pred_df.empty:
        return 0.0

    common_users = set(true_df[col_user].astype(str)).intersection(
        set(pred_df[col_user].astype(str))
    )
    if not common_users:
        return 0.0

    t_df = _clean_ranking_df(true_df[true_df[col_user].astype(str).isin(common_users)])
    p_df = _clean_ranking_df(pred_df[pred_df[col_user].astype(str).isin(common_users)])
    actual_col_rating = (
        col_rating
        if col_rating in t_df.columns
        else ("rating" if "rating" in t_df.columns else t_df.columns[2])
    )

    return float(
        ndcg_at_k(
            rating_true=t_df,
            rating_pred=p_df,
            col_user=col_user,
            col_item=col_item,
            col_rating=actual_col_rating,
            col_prediction=col_prediction,
            relevancy_method="top_k",
            k=k,
        )
    )


def mean_average_precision(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Compute Mean Average Precision (MAP@K)."""
    if true_df.empty or pred_df.empty:
        return 0.0
    return float(
        map_at_k(
            rating_true=_clean_ranking_df(true_df),
            rating_pred=_clean_ranking_df(pred_df),
            col_user=col_user,
            col_item=col_item,
            col_prediction=col_prediction,
            relevancy_method="top_k",
            k=k,
        )
    )


def hit_rate(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Fraction of common users with >= 1 relevant item in their top-K recommendations."""
    if true_df.empty or pred_df.empty:
        return 0.0

    common_users = set(true_df[col_user].astype(str)).intersection(
        set(pred_df[col_user].astype(str))
    )
    if not common_users:
        return 0.0

    top_pred = _get_top_k_per_user(
        pred_df[pred_df[col_user].astype(str).isin(common_users)],
        k=k,
        col_user=col_user,
        col_prediction=col_prediction,
    )

    pred_user_items = (
        top_pred.groupby(col_user)[col_item].apply(lambda s: set(s.astype(str))).to_dict()
    )
    true_user_items = (
        true_df[true_df[col_user].astype(str).isin(common_users)]
        .groupby(col_user)[col_item]
        .apply(lambda s: set(s.astype(str)))
        .to_dict()
    )

    hits = 0
    for u in common_users:
        user_preds = pred_user_items.get(u, set())
        user_trues = true_user_items.get(u, set())
        if user_preds.intersection(user_trues):
            hits += 1

    return float(hits / len(common_users))


def coverage(
    pred_df: pd.DataFrame,
    catalog_items: Collection[str] | pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Fraction of unique catalogue items recommended at least once in top-K."""
    if isinstance(catalog_items, pd.DataFrame):
        catalog_set = set(catalog_items[col_item].astype(str))
    else:
        catalog_set = {str(x) for x in catalog_items}

    if not catalog_set or pred_df.empty:
        return 0.0

    top_pred = _get_top_k_per_user(pred_df, k=k, col_user=col_user, col_prediction=col_prediction)
    rec_items = set(top_pred[col_item].astype(str))

    recommended_in_catalog = rec_items.intersection(catalog_set)
    return float(len(recommended_in_catalog) / len(catalog_set))


def novelty(
    pred_df: pd.DataFrame,
    train_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Mean negative log2 popularity of recommended items.

    Self-information of an item is -log2(p(item)), where p(item) is the item's
    frequency in the training dataset. Higher novelty indicates less mainstream recommendations.
    """
    if pred_df.empty or train_df.empty:
        return 0.0

    n_train = len(train_df)
    if n_train == 0:
        return 0.0

    train_counts = train_df[col_item].astype(str).value_counts().to_dict()

    top_pred = _get_top_k_per_user(pred_df, k=k, col_user=col_user, col_prediction=col_prediction)
    if top_pred.empty:
        return 0.0

    self_infos = []
    for item in top_pred[col_item].astype(str):
        # Smoothed count if 0 to prevent div by zero
        cnt = max(train_counts.get(item, 0), 1)
        p = cnt / n_train
        self_infos.append(-math.log2(p))

    return float(np.mean(self_infos))


def intra_list_diversity(
    pred_df: pd.DataFrame,
    item_categories: dict[str, list[str]] | pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
) -> float:
    """Mean pairwise category Jaccard distance within each user's top-K recommendation list."""
    if pred_df.empty:
        return 0.0

    if isinstance(item_categories, pd.DataFrame):
        cat_map: dict[str, set[str]] = {
            str(row[col_item]): (
                set(row["categories"])
                if isinstance(row["categories"], (list, set, tuple))
                else set()
            )
            for _, row in item_categories.iterrows()
        }
    else:
        cat_map = {str(k_): set(v) for k_, v in item_categories.items()}

    top_pred = _get_top_k_per_user(pred_df, k=k, col_user=col_user, col_prediction=col_prediction)

    user_diversities = []
    for _, group in top_pred.groupby(col_user):
        items = list(group[col_item].astype(str))
        n = len(items)
        if n <= 1:
            user_diversities.append(0.0)
            continue

        pair_distances = []
        for i in range(n):
            for j in range(i + 1, n):
                cats_i = cat_map.get(items[i], set())
                cats_j = cat_map.get(items[j], set())
                union = cats_i | cats_j
                if not union:
                    # Both items have no categories: treat distance as 1.0 (disjoint)
                    dist = 1.0
                else:
                    jaccard = len(cats_i & cats_j) / len(union)
                    dist = 1.0 - jaccard
                pair_distances.append(dist)

        user_diversities.append(float(np.mean(pair_distances)))

    return float(np.mean(user_diversities)) if user_diversities else 0.0


def personalisation_score(
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_prediction: str = "score",
    max_sample_users: int = 200,
    seed: int = 42,
) -> float:
    """Mean pairwise Jaccard distance between top-K recommendation lists of users (R4).

    A value near 0 indicates all users receive the exact same items (model collapsed to popularity).
    """
    if pred_df.empty:
        return 0.0

    top_pred = _get_top_k_per_user(pred_df, k=k, col_user=col_user, col_prediction=col_prediction)

    grouped = top_pred.groupby(col_user)[col_item].apply(lambda s: set(s.astype(str)))
    user_lists: dict[str, set[str]] = {str(u): set(s) for u, s in grouped.items()}
    users: list[str] = sorted(user_lists.keys())
    if len(users) <= 1:
        return 0.0

    if len(users) > max_sample_users:
        rng = random.Random(seed)
        users = sorted(rng.sample(users, max_sample_users))

    distances = []
    for u1, u2 in itertools.combinations(users, 2):
        s1 = user_lists[u1]
        s2 = user_lists[u2]
        union = s1 | s2
        if not union:
            dist = 0.0
        else:
            jaccard = len(s1 & s2) / len(union)
            dist = 1.0 - jaccard
        distances.append(dist)

    return float(np.mean(distances)) if distances else 0.0


def impression_roc_auc(
    y_true: Collection[int] | np.ndarray,
    y_score: Collection[float] | np.ndarray,
) -> float | None:
    """Compute Area Under the ROC Curve (AUC) for a single impression's candidate list.

    If an impression has only negative or only positive candidates, AUC is undefined and returns None.

    Args:
        y_true: Binary ground-truth click labels (0 or 1).
        y_score: Model predicted preference scores for candidates.

    Returns:
        float | None: Impression ROC-AUC in [0.0, 1.0], or None if only one class is present.
    """
    labels = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_score, dtype=float)

    if len(labels) == 0 or len(labels) != len(scores):
        return None

    unique_labels = np.unique(labels)
    if len(unique_labels) < 2:
        return None

    from sklearn.metrics import roc_auc_score

    try:
        return float(roc_auc_score(labels, scores))
    except ValueError:
        return None


def impression_mrr(
    y_true: Collection[int] | np.ndarray,
    y_score: Collection[float] | np.ndarray,
    candidate_ids: Collection[str] | None = None,
) -> float:
    """Compute Mean Reciprocal Rank (MRR) for a single impression's candidate list.

    Ranks candidates descending by predicted score, with deterministic tie-breaking.
    Returns 1.0 / rank of the first clicked candidate (1-indexed).

    Args:
        y_true: Binary ground-truth click labels (0 or 1).
        y_score: Model predicted preference scores for candidates.
        candidate_ids: Optional candidate IDs used for deterministic tie-breaking.

    Returns:
        float: Reciprocal rank in [0.0, 1.0], or 0.0 if no clicked candidate exists.
    """
    labels = list(y_true)
    scores = list(y_score)
    cands = (
        list(candidate_ids) if candidate_ids is not None else [str(i) for i in range(len(labels))]
    )

    if not labels or len(labels) != len(scores):
        return 0.0

    indexed = [(scores[i], cands[i], labels[i]) for i in range(len(labels))]
    indexed.sort(key=lambda x: (-x[0], x[1]))

    for rank, (_, _, label) in enumerate(indexed, start=1):
        if label == 1:
            return 1.0 / rank

    return 0.0


def impression_ndcg(
    y_true: Collection[int] | np.ndarray,
    y_score: Collection[float] | np.ndarray,
    k: int = 10,
    candidate_ids: Collection[str] | None = None,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at K (nDCG@K) for a single impression.

    Args:
        y_true: Binary ground-truth click labels (0 or 1).
        y_score: Model predicted preference scores for candidates.
        k: Truncation cutoff rank.
        candidate_ids: Optional candidate IDs used for deterministic tie-breaking.

    Returns:
        float: Normalized DCG@K in [0.0, 1.0].
    """
    labels = list(y_true)
    scores = list(y_score)
    cands = (
        list(candidate_ids) if candidate_ids is not None else [str(i) for i in range(len(labels))]
    )

    if not labels or len(labels) != len(scores):
        return 0.0

    indexed = [(scores[i], cands[i], labels[i]) for i in range(len(labels))]
    indexed.sort(key=lambda x: (-x[0], x[1]))

    dcg = 0.0
    for j in range(min(k, len(indexed))):
        rel = indexed[j][2]
        if rel > 0:
            dcg += float(rel) / math.log2(j + 2)

    ideal_labels = sorted(labels, reverse=True)
    idcg = 0.0
    for j in range(min(k, len(ideal_labels))):
        rel = ideal_labels[j]
        if rel > 0:
            idcg += float(rel) / math.log2(j + 2)

    if idcg <= 0.0:
        return 0.0

    return float(dcg / idcg)
