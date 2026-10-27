"""Discovery Engine - TF-IDF Profile Recommender Model for Articles (P5.4)."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from engine.coldstart import normalize_history
from engine.errors import UnknownItem, UnknownUser
from engine.models.base import RecommenderModel
from engine.registry import register_model
from engine.schema import ContentTypeSpec, Reason, ScoredItem

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    import pandas as pd


def clean_article_text(text: str) -> str:
    """Normalize unicode, remove HTML tags, symbols, punctuation, and lowercase."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", str(text))
    clean = re.sub(r"<.*?>", " ", norm)
    clean = clean.replace("\xa0", " ").replace("\n", " ").replace("\t", " ").replace("\r", " ")
    clean = re.sub(r"([^\s\w]|_)+", " ", clean)
    return clean.strip().lower()


def parse_recency_window(window: int | float | str | None) -> float | None:
    """Parse recency window specification to seconds."""
    if window is None:
        return None
    if isinstance(window, (int, float)):
        return float(window)
    s = str(window).strip().lower()
    if not s or s in ("none", "null"):
        return None
    if s.endswith("d"):
        return float(s[:-1]) * 86400.0
    if s.endswith("h"):
        return float(s[:-1]) * 3600.0
    if s.endswith("m"):
        return float(s[:-1]) * 60.0
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


def _pad_with_popular(
    candidates: list[tuple[float, str]],
    pop_recs: list[ScoredItem],
) -> list[tuple[float, str]]:
    """Append popular items to candidates ensuring scores remain non-increasing."""
    result = list(candidates)
    if not pop_recs:
        return result

    if result:
        last_score = result[-1][0]
        for step, p in enumerate(pop_recs, start=1):
            padded_score = last_score / (1.0 + step) if last_score > 0 else 0.0
            result.append((padded_score, p.item_id))
    else:
        for p in pop_recs:
            result.append((p.score, p.item_id))

    return result


def _build_doc_text(row: pd.Series | dict[str, Any]) -> str:
    """Build combined document string from title, text/abstract, and categories."""
    title = str(row.get("title") or "")
    raw_text = row.get("text")
    body = str(raw_text or "") if raw_text else ""

    cats = row.get("categories") or []
    if isinstance(cats, (list, tuple, np.ndarray)):
        cat_str = " ".join(str(c) for c in cats if c)
    elif isinstance(cats, str):
        cat_str = cats
    else:
        cat_str = ""

    parts = [p for p in (title, body, cat_str) if p]
    return " ".join(parts)


@register_model("tfidf_profile")
class TfidfProfileModel(RecommenderModel):
    """Content-based recommendation model using TF-IDF article representations.

    Features:
    - Trains vocabulary strictly on train-period articles to prevent representation leakage.
    - User profile is a weighted mean of clicked article vectors (recency-weighted if configured).
    - Recommendations scored by cosine similarity between user profile and candidate article vectors.
    - Native cold-start via history vector construction.
    - Popularity fallback for cold users or empty interaction histories.
    """

    def __init__(self, spec: ContentTypeSpec, **kwargs: Any) -> None:
        super().__init__(spec)
        self.vectorizer: TfidfVectorizer | None = None
        self.tfidf_matrix: sparse.csr_matrix | None = None
        self.item_ids: list[str] = []
        self.item2index: dict[str, int] = {}
        self.index2item: dict[int, str] = {}
        self.item_titles: dict[str, str] = {}
        self.user_seen: dict[str, set[str]] = {}
        self.user_history: dict[str, list[tuple[str, float, int]]] = {}
        self.item_counts: dict[str, int] = {}
        self.sorted_popular: list[str] = []
        self.recency_window: float | None = parse_recency_window(
            getattr(spec.serving, "recency_window", None) or spec.evaluation.recency_window
        )
        self.fresh_candidates: set[str] | None = None
        self.window_item_counts: dict[str, int] = {}
        self.sorted_window_popular: list[str] = []
        self.catalogue: set[str] = set()
        self._is_fitted: bool = False

    @property
    def supports_cold_start(self) -> bool:
        """Native cold start is supported via history profile vector aggregation."""
        return True

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        """Fit TF-IDF vocabulary on train articles only and precompute catalogue vectors.

        Args:
            train_interactions: Canonical interactions conforming to engine schema.
            items: Canonical items conforming to engine schema.
        """
        # 1. Establish catalogue items and deterministic indexing
        ordered_items = items.drop_duplicates(subset=["item_id"]).sort_values("item_id")
        self.item_ids = [str(x) for x in ordered_items["item_id"]]
        self.item2index = {item_id: idx for idx, item_id in enumerate(self.item_ids)}
        self.index2item = {idx: item_id for idx, item_id in enumerate(self.item_ids)}
        self.catalogue = set(self.item_ids)

        self.item_titles = {
            str(row["item_id"]): str(row.get("title") or row["item_id"])
            for _, row in ordered_items.iterrows()
        }

        # 2. Extract train article IDs to fit vocabulary strictly on training data
        if not train_interactions.empty:
            train_item_ids = set(train_interactions["item_id"].astype(str).unique())
        else:
            train_item_ids = set()

        train_subset = ordered_items[ordered_items["item_id"].astype(str).isin(train_item_ids)]
        if train_subset.empty:
            train_subset = ordered_items

        train_texts = [
            clean_article_text(_build_doc_text(row)) for _, row in train_subset.iterrows()
        ]

        # 3. Fit TfidfVectorizer on training documents only
        params = self.spec.model.params
        max_features = int(params.get("max_features", 10000))
        min_df_cfg = params.get("min_df", 2)
        min_df = 1 if isinstance(min_df_cfg, int) and min_df_cfg >= len(train_texts) else min_df_cfg

        max_df_cfg = params.get("max_df", 0.95)
        if len(train_texts) <= 2:
            max_df: float | int = 1.0
        else:
            max_df = max_df_cfg

        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=min_df,
            max_df=max_df,
            stop_words="english",
            norm="l2",
        )
        try:
            self.vectorizer.fit(train_texts)
        except ValueError:
            # Defensive fallback if pruning removes all features on small/disjoint/multilingual corpora
            self.vectorizer = TfidfVectorizer(
                max_features=max_features,
                min_df=1,
                max_df=1.0,
                norm="l2",
            )
            self.vectorizer.fit(train_texts)

        # 4. Transform all catalogue items using the fitted training vocabulary
        all_texts = [
            clean_article_text(_build_doc_text(row)) for _, row in ordered_items.iterrows()
        ]
        self.tfidf_matrix = self.vectorizer.transform(all_texts).tocsr()

        # 5. Build popularity baseline from positive training interactions
        pos_threshold = float(self.spec.signal.positive_threshold)
        self.item_counts = {}
        self.user_seen = {}
        self.user_history = {}

        if not train_interactions.empty:
            for row in train_interactions.itertuples(index=False):
                uid = str(row.user_id)
                iid = str(row.item_id)
                raw_sig = getattr(row, "signal", 1.0)
                try:
                    sig = float(raw_sig)
                except (ValueError, TypeError):
                    sig = 1.0

                raw_ts = getattr(row, "timestamp", 0)
                try:
                    ts = int(raw_ts)
                except (ValueError, TypeError):
                    ts = 0

                if iid not in self.catalogue:
                    continue

                if uid not in self.user_seen:
                    self.user_seen[uid] = set()
                    self.user_history[uid] = []

                self.user_seen[uid].add(iid)

                if sig >= pos_threshold:
                    self.item_counts[iid] = self.item_counts.get(iid, 0) + 1
                    self.user_history[uid].append((iid, sig, ts))

        # Sort each user's history chronologically
        for uid in self.user_history:
            self.user_history[uid].sort(key=lambda x: x[2])

        # Compute deterministic global popularity
        self.sorted_popular = sorted(
            self.item_ids,
            key=lambda x: (-self.item_counts.get(x, 0), x),
        )

        # Compute fresh recency window candidates and window popularity
        self._compute_fresh_candidates(train_interactions)

        self._is_fitted = True

    def _compute_fresh_candidates(self, train_interactions: pd.DataFrame) -> None:
        """Identify fresh articles within the recency window and compute window popularity."""
        if self.recency_window is None or train_interactions.empty:
            self.fresh_candidates = None
            self.window_item_counts = {}
            self.sorted_window_popular = []
            return

        has_ts = "timestamp" in train_interactions.columns
        if not has_ts:
            self.fresh_candidates = None
            return

        max_ts = float(train_interactions["timestamp"].max())
        cutoff_ts = max_ts - self.recency_window

        window_df = train_interactions[train_interactions["timestamp"] >= cutoff_ts]
        fresh_ids = {str(x) for x in window_df["item_id"].unique() if str(x) in self.catalogue}

        if fresh_ids:
            self.fresh_candidates = fresh_ids
            pos_thresh = float(self.spec.signal.positive_threshold)
            pos_window = window_df[window_df["signal"] >= pos_thresh]
            self.window_item_counts = {
                str(k): int(v) for k, v in pos_window["item_id"].value_counts().items()
            }
            self.sorted_window_popular = sorted(
                fresh_ids,
                key=lambda x: (-self.window_item_counts.get(x, 0), x),
            )
        else:
            self.fresh_candidates = None

    def set_fresh_candidates(
        self,
        candidate_ids: Collection[str] | None,
        item_counts: dict[str, int] | None = None,
    ) -> None:
        """Explicitly set or clear the pool of fresh candidate items for serving or evaluation."""
        if candidate_ids is None:
            self.fresh_candidates = None
            self.window_item_counts = {}
            self.sorted_window_popular = []
            return

        valid_ids = {str(x) for x in candidate_ids if str(x) in self.catalogue}
        self.fresh_candidates = valid_ids
        if item_counts is not None:
            self.window_item_counts = {str(k): int(v) for k, v in item_counts.items()}
        else:
            self.window_item_counts = {x: self.item_counts.get(x, 0) for x in valid_ids}

        self.sorted_window_popular = sorted(
            valid_ids,
            key=lambda x: (-self.window_item_counts.get(x, 0), x),
        )

    def _build_profile_vector(
        self,
        history: list[tuple[str, float, int]] | list[tuple[str, float]],
    ) -> sparse.csr_matrix | None:
        """Construct L2-normalized user profile vector from clicked article history.

        Applies exponential recency weighting if recency_weight is configured and
        valid history articles exist.
        """
        if not history or self.tfidf_matrix is None:
            return None

        recency_weight = bool(self.spec.model.params.get("recency_weight", True))

        # Filter valid items in catalogue
        valid_entries: list[tuple[int, float, int]] = []
        for entry in history:
            iid = entry[0]
            sig = float(entry[1])
            ts = entry[2] if len(entry) >= 3 else 0
            if iid in self.item2index:
                valid_entries.append((self.item2index[iid], sig, ts))

        if not valid_entries:
            return None

        # Determine timestamps and weights
        timestamps = [e[2] for e in valid_entries]
        has_varying_timestamps = len(set(timestamps)) > 1 and max(timestamps) > 0

        weights: list[float] = []
        if recency_weight:
            if has_varying_timestamps:
                t_max = max(timestamps)
                half_life = float(self.spec.model.params.get("half_life_days", 7.0)) * 86400.0
                if half_life <= 0:
                    half_life = 86400.0 * 7.0
                for _, sig, ts in valid_entries:
                    dt = max(0, t_max - ts)
                    decay = 2.0 ** (-dt / half_life)
                    weights.append(sig * decay)
            else:
                # Sequence-based exponential recency decay
                m = len(valid_entries)
                for idx, (_, sig, _) in enumerate(valid_entries):
                    decay = 2.0 ** (-(m - 1 - idx) / 5.0)
                    weights.append(sig * decay)
        else:
            weights = [sig for _, sig, _ in valid_entries]

        total_weight = sum(weights)
        if total_weight <= 0.0:
            total_weight = 1.0

        # Weighted combination of article TF-IDF vectors
        row_indices = [idx for idx, _, _ in valid_entries]
        sub_matrix = self.tfidf_matrix[row_indices, :]  # shape: (len(valid_entries), D)
        weights_arr = np.array(weights, dtype=float) / total_weight

        # profile = weights_arr @ sub_matrix
        profile = sparse.csr_matrix(weights_arr).dot(sub_matrix)

        # L2-normalize profile vector
        norm = float(sparse.linalg.norm(profile))
        if norm > 0.0:
            profile = profile / norm
            return profile.tocsr()

        return None

    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k recommendations for a known training user."""
        if not self._is_fitted or self.tfidf_matrix is None:
            raise RuntimeError("Model has not been fitted.")

        uid = str(user_id)
        if uid not in self.user_history:
            raise UnknownUser(user_id=uid, content_type=self.spec.type)

        user_hist = self.user_history[uid]
        exclusions = set(str(x) for x in exclude_ids)
        if not self.spec.model.allow_repeat:
            exclusions.update(self.user_seen.get(uid, set()))

        profile = self._build_profile_vector(user_hist)
        if profile is None:
            return self.popular(k=k, exclude_ids=exclusions)

        return self._score_candidates(profile, k=k, exclusions=exclusions)

    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
        max_history_length: int | None = None,
    ) -> list[ScoredItem]:
        """Generate recommendations for arbitrary cold-start interaction history."""
        if not self._is_fitted or self.tfidf_matrix is None:
            raise RuntimeError("Model has not been fitted.")

        exclusions = set(str(x) for x in exclude_ids)
        if not history:
            return self.popular(k=k, exclude_ids=exclusions)

        norm_res = normalize_history(
            history, catalogue=self.catalogue, max_history_length=max_history_length
        )
        if not norm_res.normalized_history:
            return self.popular(k=k, exclude_ids=exclusions)

        if not self.spec.model.allow_repeat:
            exclusions.update(item_id for item_id, _ in norm_res.normalized_history)

        profile = self._build_profile_vector(norm_res.normalized_history)
        if profile is None:
            return self.popular(k=k, exclude_ids=exclusions)

        return self._score_candidates(profile, k=k, exclusions=exclusions)

    def _score_candidates(
        self,
        profile: sparse.csr_matrix,
        k: int,
        exclusions: set[str],
    ) -> list[ScoredItem]:
        """Compute cosine similarities between profile and catalogue items, ranking top-k."""
        if self.tfidf_matrix is None:
            raise RuntimeError("TF-IDF model has not been fitted; tfidf_matrix is None.")
        # profile shape: (1, D), tfidf_matrix shape: (N, D)
        scores_mat = self.tfidf_matrix.dot(profile.T)  # (N, 1)
        scores_arr = np.asarray(scores_mat.toarray()).flatten()

        candidates: list[tuple[float, str]] = []
        for idx, score_val in enumerate(scores_arr):
            item_id = self.index2item[idx]
            if self.fresh_candidates is not None and item_id not in self.fresh_candidates:
                continue
            if item_id in exclusions:
                continue
            s = float(score_val)
            if np.isfinite(s) and s > 0.0:
                candidates.append((s, item_id))

        # Sort descending by similarity, breaking ties deterministically by item_id ascending
        candidates.sort(key=lambda x: (-x[0], x[1]))

        # Pad with popular if fewer than k candidates found
        if len(candidates) < k:
            selected_ids = {c[1] for c in candidates}
            combined_exclude = exclusions.union(selected_ids)
            pop_recs = self.popular(k=k - len(candidates), exclude_ids=combined_exclude)
            candidates = _pad_with_popular(candidates, pop_recs)

        top_k = candidates[:k]
        return [
            ScoredItem(item_id=item_id, score=float(score), rank=rank)
            for rank, (score, item_id) in enumerate(top_k, start=1)
        ]

    def score_candidate_items(
        self,
        candidate_ids: Collection[str],
        user_id: str | None = None,
        history: list[tuple[str, float]] | list[str] | None = None,
    ) -> list[float]:
        """Compute predicted preference scores for a list of candidate items.

        Used in impression ranking evaluation to score candidate pools without full catalogue ranking.

        Args:
            candidate_ids: Collection of target candidate item IDs to score.
            user_id: Optional known user ID to look up in training history.
            history: Optional interaction history if user is cold or unobserved.

        Returns:
            list[float]: Predicted scores for each candidate in candidate_ids order.
        """
        if not self._is_fitted or self.tfidf_matrix is None:
            raise RuntimeError("Model has not been fitted.")

        profile: sparse.csr_matrix | None = None
        if user_id is not None and str(user_id) in self.user_history:
            profile = self._build_profile_vector(self.user_history[str(user_id)])
        elif history:
            norm_res = normalize_history(history, catalogue=self.catalogue)
            profile = self._build_profile_vector(norm_res.normalized_history)

        scores: list[float] = []
        if profile is not None:
            for cid in candidate_ids:
                item_str = str(cid)
                if item_str in self.item2index:
                    idx = self.item2index[item_str]
                    vec = self.tfidf_matrix[idx, :]
                    raw_sim = float(vec.dot(profile.T).toarray()[0, 0])
                    if np.isfinite(raw_sim) and raw_sim > 0.0:
                        scores.append(raw_sim)
                    else:
                        pop_cnt = self.window_item_counts.get(
                            item_str, self.item_counts.get(item_str, 0)
                        )
                        scores.append(float(pop_cnt) * 1e-6)
                else:
                    scores.append(0.0)
        else:
            for cid in candidate_ids:
                item_str = str(cid)
                pop_cnt = self.window_item_counts.get(item_str, self.item_counts.get(item_str, 0))
                scores.append(float(pop_cnt))

        return scores

    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        """Find top-k most similar articles to query article by TF-IDF cosine similarity."""
        if not self._is_fitted or self.tfidf_matrix is None:
            raise RuntimeError("Model has not been fitted.")

        target_id = str(item_id)
        if target_id not in self.catalogue:
            raise UnknownItem(item_id=target_id, content_type=self.spec.type)

        target_idx = self.item2index[target_id]
        item_vec = self.tfidf_matrix[target_idx, :]

        scores_mat = self.tfidf_matrix.dot(item_vec.T)
        scores_arr = np.asarray(scores_mat.toarray()).flatten()

        candidates: list[tuple[float, str]] = []
        for idx, score_val in enumerate(scores_arr):
            if idx == target_idx:
                # Query item itself must NEVER be returned
                continue
            other_id = self.index2item[idx]
            if self.fresh_candidates is not None and other_id not in self.fresh_candidates:
                continue
            s = float(score_val)
            if np.isfinite(s) and s > 0.0:
                candidates.append((s, other_id))

        candidates.sort(key=lambda x: (-x[0], x[1]))

        if len(candidates) < k:
            selected_ids = {c[1] for c in candidates}
            combined_exclude = selected_ids.union({target_id})
            pop_recs = self.popular(k=k - len(candidates), exclude_ids=combined_exclude)
            candidates = _pad_with_popular(candidates, pop_recs)

        top_k = candidates[:k]
        return [
            ScoredItem(item_id=cand_id, score=float(score), rank=rank)
            for rank, (score, cand_id) in enumerate(top_k, start=1)
        ]

    def popular(
        self,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k global popular articles (restricted to window if recency_window active)."""
        exclusions = set(str(x) for x in exclude_ids)
        result: list[ScoredItem] = []
        rank = 1

        source_list = (
            self.sorted_window_popular if self.fresh_candidates is not None else self.sorted_popular
        )
        counts_dict = (
            self.window_item_counts if self.fresh_candidates is not None else self.item_counts
        )

        for item_id in source_list:
            if item_id in exclusions:
                continue
            count = float(counts_dict.get(item_id, 0))
            result.append(ScoredItem(item_id=item_id, score=count, rank=rank))
            rank += 1
            if len(result) >= k:
                break

        return result

    def explain(
        self,
        recommended_item_id: str = "",
        history: list[tuple[str, float]] | list[str] | None = None,
        user_id: str | None = None,
        min_threshold: float | None = None,
        **kwargs: Any,
    ) -> Reason | None:
        """Produce faithful explanation identifying which history article contributed most."""
        if not self._is_fitted or self.tfidf_matrix is None:
            return None

        rec_id = str(recommended_item_id)
        if rec_id not in self.item2index:
            return None

        rec_idx = self.item2index[rec_id]
        rec_vec = self.tfidf_matrix[rec_idx, :]

        # Extract history
        history_pairs: list[tuple[str, float]] = []
        if user_id is not None:
            uid = str(user_id)
            if uid in self.user_history:
                history_pairs = [(e[0], e[1]) for e in self.user_history[uid]]
        elif history is not None:
            for item in history:
                if isinstance(item, tuple) and len(item) >= 2:
                    history_pairs.append((str(item[0]), float(item[1])))
                elif isinstance(item, str):
                    history_pairs.append((item, 1.0))

        if not history_pairs:
            return None

        best_h: str | None = None
        best_contrib = -1.0
        total_contrib = 0.0

        for h_id, sig in history_pairs:
            if h_id not in self.item2index:
                continue
            h_idx = self.item2index[h_id]
            h_vec = self.tfidf_matrix[h_idx, :]
            sim = float(h_vec.dot(rec_vec.T).toarray()[0, 0])
            contrib = max(0.0, sim * float(sig))
            total_contrib += contrib
            if contrib > best_contrib:
                best_contrib = contrib
                best_h = h_id

        threshold = (
            min_threshold
            if min_threshold is not None
            else self.spec.serving.explanation_min_threshold
        )

        if best_h is not None and total_contrib > 0.0:
            share = best_contrib / total_contrib
            if share >= threshold:
                h_title = self.item_titles.get(best_h, best_h)
                shared_terms = self._get_shared_terms(best_h, rec_id, max_terms=3)
                if shared_terms:
                    text = f"Recommended based on reading '{h_title}' (topics: {', '.join(shared_terms)})"
                else:
                    text = f"Recommended based on reading '{h_title}'"
                return Reason(
                    kind="article_similarity",
                    item_id=best_h,
                    text=text,
                )

        return None

    def _get_shared_terms(self, item_a: str, item_b: str, max_terms: int = 3) -> list[str]:
        """Find top shared TF-IDF terms between two articles by elementwise weight product."""
        if (
            self.tfidf_matrix is None
            or self.vectorizer is None
            or item_a not in self.item2index
            or item_b not in self.item2index
        ):
            return []

        idx_a = self.item2index[item_a]
        idx_b = self.item2index[item_b]

        vec_a = self.tfidf_matrix[idx_a, :]
        vec_b = self.tfidf_matrix[idx_b, :]

        shared = vec_a.multiply(vec_b)
        if shared.nnz == 0:
            return []

        feature_names = self.vectorizer.get_feature_names_out()
        cols = shared.indices
        vals = shared.data

        top_order = np.argsort(-vals)[:max_terms]
        return [str(feature_names[cols[i]]) for i in top_order]

    def save(self, dir_path: Path) -> None:
        """Persist model sparse matrix, vocabulary, and metadata to directory."""
        if not self._is_fitted or self.tfidf_matrix is None or self.vectorizer is None:
            raise RuntimeError("Model has not been fitted.")

        dir_path.mkdir(parents=True, exist_ok=True)

        sparse.save_npz(dir_path / "tfidf_matrix.npz", self.tfidf_matrix)

        vocab = {str(k): int(v) for k, v in self.vectorizer.vocabulary_.items()}
        (dir_path / "vocabulary.json").write_bytes(
            (json.dumps(vocab, indent=2).replace("\r\n", "\n") + "\n").encode("utf-8")
        )

        np.save(dir_path / "idf.npy", self.vectorizer.idf_)

        (dir_path / "item_ids.json").write_bytes(
            (json.dumps(self.item_ids, indent=2).replace("\r\n", "\n") + "\n").encode("utf-8")
        )
        (dir_path / "item_titles.json").write_bytes(
            (json.dumps(self.item_titles, indent=2).replace("\r\n", "\n") + "\n").encode("utf-8")
        )

        meta = {
            "model_name": "tfidf_profile",
            "catalogue": list(self.catalogue),
            "item_counts": {str(k): int(v) for k, v in self.item_counts.items()},
            "user_seen": {k: list(v) for k, v in self.user_seen.items()},
            "user_history": {
                k: [(e[0], e[1], e[2]) for e in v] for k, v in self.user_history.items()
            },
            "recency_window": self.recency_window,
            "fresh_candidates": (
                list(self.fresh_candidates) if self.fresh_candidates is not None else None
            ),
            "window_item_counts": self.window_item_counts,
            "vectorizer_params": {
                "max_features": self.vectorizer.max_features,
                "min_df": self.vectorizer.min_df,
                "max_df": self.vectorizer.max_df,
                "stop_words": self.vectorizer.stop_words,
            },
        }
        (dir_path / "model_meta.json").write_bytes(
            (json.dumps(meta, indent=2).replace("\r\n", "\n") + "\n").encode("utf-8")
        )

    def load(self, dir_path: Path) -> None:
        """Load model parameters and representations from directory."""
        meta_path = dir_path / "model_meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing model_meta.json in {dir_path}")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.item_ids = json.loads((dir_path / "item_ids.json").read_text(encoding="utf-8"))
        self.item2index = {item_id: idx for idx, item_id in enumerate(self.item_ids)}
        self.index2item = {idx: item_id for idx, item_id in enumerate(self.item_ids)}
        self.catalogue = set(meta["catalogue"])

        self.item_titles = json.loads((dir_path / "item_titles.json").read_text(encoding="utf-8"))

        self.item_counts = {str(k): int(v) for k, v in meta["item_counts"].items()}
        self.user_seen = {str(k): set(v) for k, v in meta["user_seen"].items()}
        self.user_history = {
            str(k): [(str(e[0]), float(e[1]), int(e[2])) for e in v]
            for k, v in meta["user_history"].items()
        }

        self.sorted_popular = sorted(
            self.item_ids,
            key=lambda x: (-self.item_counts.get(x, 0), x),
        )

        self.recency_window = meta.get("recency_window")
        fresh_raw = meta.get("fresh_candidates")
        self.fresh_candidates = set(fresh_raw) if fresh_raw is not None else None
        self.window_item_counts = {
            str(k): int(v) for k, v in meta.get("window_item_counts", {}).items()
        }
        if self.fresh_candidates is not None:
            self.sorted_window_popular = sorted(
                self.fresh_candidates,
                key=lambda x: (-self.window_item_counts.get(x, 0), x),
            )
        else:
            self.sorted_window_popular = []

        self.tfidf_matrix = sparse.load_npz(dir_path / "tfidf_matrix.npz")

        raw_vocab = json.loads((dir_path / "vocabulary.json").read_text(encoding="utf-8"))
        vocab = {str(k): int(v) for k, v in raw_vocab.items()}
        idf = np.load(dir_path / "idf.npy")

        v_params = meta.get("vectorizer_params", {})
        self.vectorizer = TfidfVectorizer(
            max_features=v_params.get("max_features"),
            min_df=v_params.get("min_df", 1),
            max_df=v_params.get("max_df", 1.0),
            stop_words=v_params.get("stop_words", "english"),
            norm="l2",
        )
        self.vectorizer.vocabulary_ = vocab
        self.vectorizer.idf_ = idf

        self._is_fitted = True
