"""Discovery Engine - SAR (Simple Algorithm for Recommendations) model wrapper (P3.5)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from scipy import sparse

from discovery.models.sar.sar_singlenode import SARSingleNode
from engine.coldstart import normalize_history
from engine.errors import UnknownItem, UnknownUser
from engine.explain import find_top_contributor, format_reason
from engine.models.base import RecommenderModel
from engine.registry import register_model
from engine.schema import ContentTypeSpec, Reason, ScoredItem

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path


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


def sparsify_similarity(
    sim: np.ndarray | sparse.spmatrix,
    top_k: int,
    chunk_size: int = 1000,
) -> sparse.csr_matrix:
    """Retain only the top_k highest similarity neighbors per item row (excluding self).

    Zeroes out diagonal (self-similarity), drops non-positive scores, and retains at most
    top_k highest similarity entries per row, returning a compact scipy CSR matrix.
    Processes rows in chunks so peak memory stays near the size of the sparse result.
    """
    n = sim.shape[0]
    if n == 0:
        return sparse.csr_matrix((0, 0), dtype=float)

    if chunk_size <= 0:
        chunk_size = 1000

    chunks: list[sparse.csr_matrix] = []
    kth = n - top_k

    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        chunk_len = end - start

        if isinstance(sim, sparse.spmatrix):
            chunk = sim[start:end].toarray()
        else:
            chunk = np.array(sim[start:end], copy=True)

        # Zero out diagonal (self-similarity is not a neighbor)
        chunk[np.arange(chunk_len), np.arange(start, end)] = 0.0

        if n - 1 <= top_k:
            chunk[chunk <= 0.0] = 0.0
        else:
            partitioned_indices = np.argpartition(chunk, kth, axis=1)
            rows = np.arange(chunk_len)[:, None]
            cols_to_zero = partitioned_indices[:, :kth]
            chunk[rows, cols_to_zero] = 0.0
            chunk[chunk <= 0.0] = 0.0

        chunks.append(sparse.csr_matrix(chunk))

    if len(chunks) == 1:
        return chunks[0]
    return sparse.vstack(chunks, format="csr")


@register_model("sar")
class SarModel(RecommenderModel):
    """Wrapper over vendored SAR (Simple Algorithm for Recommendations).

    Provides collaborative filtering recommendations, sparse item similarity,
    popular item fallbacks, cold-start history scoring, and explainability.
    """

    def __init__(self, spec: ContentTypeSpec) -> None:
        super().__init__(spec)
        self.sar: SARSingleNode | None = None
        self.catalogue: list[str] = []
        self.item_counts: dict[str, int] = {}
        self.sorted_popular: list[str] = []
        self.user_seen: dict[str, set[str]] = {}
        self._is_fitted: bool = False

    @property
    def supports_cold_start(self) -> bool:
        return True

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        """Fit SAR model on training interactions and item catalogue.

        Args:
            train_interactions: Interactions DataFrame with columns (user_id, item_id, signal, timestamp).
            items: Item catalogue DataFrame with column item_id.
        """
        self.catalogue = sorted(items["item_id"].astype(str).unique())

        # Compute popular item ordering from positive training interactions using current threshold
        threshold = self.spec.signal.positive_threshold
        positive_df = train_interactions[train_interactions["signal"] >= threshold]

        counts_dict = positive_df["item_id"].astype(str).value_counts().to_dict()
        self.item_counts = {item_id: int(counts_dict.get(item_id, 0)) for item_id in self.catalogue}
        self.sorted_popular = sorted(
            self.catalogue,
            key=lambda x: (-self.item_counts[x], x),
        )

        # Record seen items per user for filtering when allow_repeat is False
        self.user_seen = {}
        for uid, group in train_interactions.groupby("user_id"):
            self.user_seen[str(uid)] = set(group["item_id"].astype(str))

        # Format DataFrame for SARSingleNode
        params = self.spec.model.params or {}
        sim_type = str(params.get("similarity_type", "jaccard"))
        decay_coef = float(params.get("time_decay_coefficient", 30))
        timedecay_flag = bool(params.get("timedecay_formula", False))
        threshold = int(params.get("threshold", 1))
        normalize = bool(params.get("normalize", False))

        sar_df = pd.DataFrame(
            {
                "user_id": train_interactions["user_id"].astype(str),
                "item_id": train_interactions["item_id"].astype(str),
                "rating": train_interactions["signal"].astype(float),
                "timestamp": train_interactions["timestamp"].astype(int),
            }
        )

        # SARSingleNode requires unique (user_id, item_id) pairs if no decay,
        # or unique (user_id, item_id, timestamp) if decay is active.
        dedup_cols = (
            ["user_id", "item_id", "timestamp"] if timedecay_flag else ["user_id", "item_id"]
        )
        sar_df = sar_df.drop_duplicates(subset=dedup_cols, keep="last").reset_index(drop=True)

        self.sar = SARSingleNode(
            col_user="user_id",
            col_item="item_id",
            col_rating="rating",
            col_timestamp="timestamp",
            col_prediction="prediction",
            similarity_type=sim_type,
            time_decay_coefficient=decay_coef,
            timedecay_formula=timedecay_flag,
            threshold=threshold,
            normalize=normalize,
        )

        # Cap similarity matrix items by popularity if budget exceeded
        max_items = self.spec.serving.max_items_in_similarity
        if len(self.sorted_popular) > max_items:
            sim_items_set = set(self.sorted_popular[:max_items])
            sar_df = sar_df[sar_df["item_id"].isin(sim_items_set)].reset_index(drop=True)
            cat_items_series = pd.Series(sorted(sim_items_set))
        else:
            cat_items_series = pd.Series(sorted(set(self.catalogue).union(set(sar_df["item_id"]))))

        users_series = pd.Series(sorted(sar_df["user_id"].unique()))

        self.sar.index2item = dict(enumerate(cat_items_series))
        self.sar.index2user = dict(enumerate(users_series))
        self.sar.item2index = {v: k for k, v in self.sar.index2item.items()}
        self.sar.user2index = {v: k for k, v in self.sar.index2user.items()}
        self.sar.n_users = len(self.sar.user2index)
        self.sar.n_items = len(self.sar.index2item)

        self.sar.fit(sar_df)

        # Sparsify similarity matrix to top_neighbors_per_item
        top_k_neighbors = self.spec.serving.top_neighbors_per_item
        self.sar.item_similarity = sparsify_similarity(
            self.sar.item_similarity, top_k=top_k_neighbors
        )

        self._is_fitted = True

    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k recommendations for a known training user."""
        if not self._is_fitted or self.sar is None:
            raise RuntimeError("Model has not been fitted.")

        uid = str(user_id)
        if uid not in self.sar.user2index:
            raise UnknownUser(user_id=uid, content_type=self.spec.type)

        u_idx = self.sar.user2index[uid]
        user_vec = self.sar.user_affinity[u_idx, :]
        raw_scores = user_vec.dot(self.sar.item_similarity)

        exclusions = set(str(x) for x in exclude_ids)
        if not self.spec.model.allow_repeat:
            exclusions.update(self.user_seen.get(uid, set()))

        # Collect and rank scored candidates
        candidates: list[tuple[float, str]] = []
        if isinstance(raw_scores, sparse.spmatrix):
            raw_coo = raw_scores.tocoo()
            for i_idx, score_val in zip(raw_coo.col, raw_coo.data, strict=False):
                item_id = self.sar.index2item[int(i_idx)]
                if item_id in exclusions:
                    continue
                s = float(score_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, item_id))
        else:
            scores_arr = np.asarray(raw_scores).flatten()
            for i_idx, score_val in enumerate(scores_arr):
                item_id = self.sar.index2item[i_idx]
                if item_id in exclusions:
                    continue
                s = float(score_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, item_id))

        # Sort descending by score, breaking ties by item_id ascending
        candidates.sort(key=lambda x: (-x[0], x[1]))

        # If candidates are fewer than k, pad with popular items
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

    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
        max_history_length: int | None = None,
    ) -> list[ScoredItem]:
        """Generate recommendations for arbitrary interaction history (cold start)."""
        if not self._is_fitted or self.sar is None:
            raise RuntimeError("Model has not been fitted.")

        exclusions = set(str(x) for x in exclude_ids)
        if not history:
            return self.popular(k=k, exclude_ids=exclusions)

        norm_res = normalize_history(
            history, catalogue=self.catalogue, max_history_length=max_history_length
        )
        if not norm_res.normalized_history:
            return self.popular(k=k, exclude_ids=exclusions)

        # Still exclude all history items from results (FIX-46)
        if not self.spec.model.allow_repeat:
            exclusions.update(item_id for item_id, _ in norm_res.normalized_history)

        # Build affinity sparse row vector using only evidence with signal >= positive_threshold (FIX-46)
        pos_thresh = float(self.spec.signal.positive_threshold)
        indices = []
        data = []
        for item_id, signal in norm_res.normalized_history:
            if float(signal) >= pos_thresh and item_id in self.sar.item2index:
                indices.append(self.sar.item2index[item_id])
                data.append(float(signal))

        if not indices:
            return self.popular(k=k, exclude_ids=exclusions)

        affinity_vec = sparse.csr_matrix(
            (data, ([0] * len(indices), indices)),
            shape=(1, self.sar.n_items),
        )

        raw_scores = affinity_vec.dot(self.sar.item_similarity)

        candidates: list[tuple[float, str]] = []
        if isinstance(raw_scores, sparse.spmatrix):
            raw_coo = raw_scores.tocoo()
            for i_idx, score_val in zip(raw_coo.col, raw_coo.data, strict=False):
                item_id = self.sar.index2item[int(i_idx)]
                if item_id in exclusions:
                    continue
                s = float(score_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, item_id))
        else:
            scores_arr = np.asarray(raw_scores).flatten()
            for i_idx, score_val in enumerate(scores_arr):
                item_id = self.sar.index2item[i_idx]
                if item_id in exclusions:
                    continue
                s = float(score_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, item_id))

        candidates.sort(key=lambda x: (-x[0], x[1]))

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

    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        """Find top-k most similar items to query item from similarity matrix."""
        if not self._is_fitted or self.sar is None:
            raise RuntimeError("Model has not been fitted.")

        target_id = str(item_id)
        if target_id not in self.catalogue:
            raise UnknownItem(item_id=target_id, content_type=self.spec.type)

        if target_id not in self.sar.item2index:
            # Item was capped out of similarity matrix by budget or has no interactions;
            # Fall back to popular items
            return self.popular(k=k, exclude_ids={target_id})

        i_idx = self.sar.item2index[target_id]
        sim_row = self.sar.item_similarity[i_idx, :]

        candidates: list[tuple[float, str]] = []
        if isinstance(sim_row, sparse.csr_matrix):
            cols = sim_row.indices
            vals = sim_row.data
            for other_idx, s_val in zip(cols, vals, strict=False):
                if other_idx == i_idx:
                    continue
                other_id = self.sar.index2item[other_idx]
                s = float(s_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, other_id))
        else:
            sim_scores = np.asarray(
                sim_row.toarray() if isinstance(sim_row, sparse.spmatrix) else sim_row
            ).flatten()
            for other_idx, s_val in enumerate(sim_scores):
                # Query item itself must NEVER be returned
                if other_idx == i_idx:
                    continue
                other_id = self.sar.index2item[other_idx]
                s = float(s_val)
                if np.isfinite(s) and s > 0.0:
                    candidates.append((s, other_id))

        candidates.sort(key=lambda x: (-x[0], x[1]))

        # If fewer than k similar items exist, pad with popular items
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
        """Generate top-k global popular items."""
        exclusions = set(str(x) for x in exclude_ids)
        result: list[ScoredItem] = []
        rank = 1

        for item_id in self.sorted_popular:
            if item_id in exclusions:
                continue
            count = float(self.item_counts.get(item_id, 0))
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
        """Produce faithful attribution identifying which history item contributed most.

        For recommended item `r` and history `H` (or known `user_id`), the reason item is:
            argmax_{h in H} affinity(h) * sim(h, r)
        Show only when contribution share exceeds configurable threshold.
        """
        if not self._is_fitted or self.sar is None:
            return None

        if history is None and "history_item_ids" in kwargs:
            history = kwargs["history_item_ids"]

        threshold = (
            min_threshold
            if min_threshold is not None
            else self.spec.serving.explanation_min_threshold
        )

        rec_id = str(recommended_item_id)
        if rec_id not in self.sar.item2index:
            return None

        rec_idx = self.sar.item2index[rec_id]

        # 1. Derive user affinities if known user provided
        user_affinities: dict[str, float] = {}
        if user_id is not None:
            uid = str(user_id)
            if uid in self.sar.user2index:
                u_idx = self.sar.user2index[uid]
                user_row = self.sar.user_affinity[u_idx, :]
                if isinstance(user_row, sparse.csr_matrix):
                    for h_idx, aff_val in zip(user_row.indices, user_row.data, strict=False):
                        if aff_val > 0.0:
                            h_id = self.sar.index2item[h_idx]
                            user_affinities[h_id] = float(aff_val)
                else:
                    user_arr = np.asarray(
                        user_row.toarray() if isinstance(user_row, sparse.spmatrix) else user_row
                    ).flatten()
                    for h_idx, aff_val in enumerate(user_arr):
                        if aff_val > 0.0:
                            h_id = self.sar.index2item[h_idx]
                            user_affinities[h_id] = float(aff_val)

        # 2. Extract affinities from history if provided
        affinities: dict[str, float] = {}
        if history:
            norm_res = normalize_history(history, catalogue=self.catalogue, max_history_length=None)
            for h_id, sig in norm_res.normalized_history:
                # If known user has time-decayed affinity and history provided as plain IDs, use user affinity
                if (
                    user_affinities
                    and h_id in user_affinities
                    and (isinstance(history[0], str) if history else False)
                ):
                    affinities[h_id] = user_affinities[h_id]
                elif sig > 0.0:
                    affinities[h_id] = float(sig)
        elif user_affinities:
            affinities = user_affinities

        if not affinities:
            return None

        # 3. Compute contributions: affinity(h) * sim(h, r)
        contributions: dict[str, float] = {}
        for h_id, aff in affinities.items():
            h_str = str(h_id)
            if h_str == rec_id:
                continue
            if h_str not in self.sar.item2index:
                continue
            h_idx = self.sar.item2index[h_str]
            sim_val = float(self.sar.item_similarity[h_idx, rec_idx])
            if sim_val > 0.0 and aff > 0.0:
                contributions[h_str] = aff * sim_val

        top = find_top_contributor(list(affinities.keys()), contributions)
        if top is not None:
            best_item, _, share = top
            return format_reason(
                best_item,
                kind="similar_item",
                contribution_share=share,
                min_threshold=threshold,
            )

        return None

    def save(self, dir_path: Path) -> None:
        """Persist model parameters and indices without arbitrary pickles."""
        if not self._is_fitted or self.sar is None:
            raise RuntimeError("Model has not been fitted; cannot save.")

        dir_path.mkdir(parents=True, exist_ok=True)

        def _json_default(obj: Any) -> Any:
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, set):
                return list(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # 1. Save metadata and indices
        meta = {
            "similarity_type": self.sar.similarity_type,
            "time_decay_half_life": self.sar.time_decay_half_life,
            "time_decay_flag": self.sar.time_decay_flag,
            "threshold": self.sar.threshold,
            "normalize": self.sar.normalize,
            "time_now": self.sar.time_now,
            "n_users": int(self.sar.n_users),
            "n_items": int(self.sar.n_items),
            "catalogue": self.catalogue,
            "item_counts": {str(k): int(v) for k, v in self.item_counts.items()},
            "user_seen": {k: sorted(v) for k, v in sorted(self.user_seen.items())},
        }
        for p, s in [
            (dir_path / "model_meta.json", json.dumps(meta, indent=2, default=_json_default)),
            (
                dir_path / "index2item.json",
                json.dumps(self.sar.index2item, indent=2, default=_json_default),
            ),
            (
                dir_path / "index2user.json",
                json.dumps(self.sar.index2user, indent=2, default=_json_default),
            ),
        ]:
            p.write_bytes((s.replace("\r\n", "\n") + "\n").encode("utf-8"))

        # 2. Save sparse matrices
        if isinstance(self.sar.item_similarity, sparse.spmatrix):
            sparse.save_npz(dir_path / "item_similarity.npz", self.sar.item_similarity.tocsr())
        else:
            sparse.save_npz(
                dir_path / "item_similarity.npz", sparse.csr_matrix(self.sar.item_similarity)
            )

        if isinstance(self.sar.user_affinity, sparse.spmatrix):
            sparse.save_npz(dir_path / "user_affinity.npz", self.sar.user_affinity.tocsr())
        else:
            sparse.save_npz(
                dir_path / "user_affinity.npz", sparse.csr_matrix(self.sar.user_affinity)
            )

        # 3. Save frequencies
        np.save(dir_path / "item_frequencies.npy", self.sar.item_frequencies)

    def load(self, dir_path: Path) -> None:
        """Load model parameters and indices from directory."""
        meta_p = dir_path / "model_meta.json"
        if not meta_p.exists():
            raise FileNotFoundError(f"Missing model_meta.json in {dir_path}")

        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        self.catalogue = meta["catalogue"]
        self.item_counts = {str(k): int(v) for k, v in meta["item_counts"].items()}
        self.sorted_popular = sorted(
            self.catalogue,
            key=lambda x: (-self.item_counts.get(x, 0), x),
        )
        self.user_seen = {k: set(v) for k, v in meta["user_seen"].items()}

        raw_index2item = json.loads((dir_path / "index2item.json").read_text(encoding="utf-8"))
        raw_index2user = json.loads((dir_path / "index2user.json").read_text(encoding="utf-8"))

        self.sar = SARSingleNode(
            similarity_type=meta["similarity_type"],
            threshold=meta["threshold"],
            timedecay_formula=meta["time_decay_flag"],
            normalize=meta["normalize"],
        )
        self.sar.time_decay_half_life = meta["time_decay_half_life"]
        self.sar.time_now = meta["time_now"]

        if isinstance(raw_index2item, list):
            self.sar.index2item = dict(enumerate(str(v) for v in raw_index2item))
        else:
            self.sar.index2item = {int(k): str(v) for k, v in raw_index2item.items()}

        if isinstance(raw_index2user, list):
            self.sar.index2user = dict(enumerate(str(v) for v in raw_index2user))
        else:
            self.sar.index2user = {int(k): str(v) for k, v in raw_index2user.items()}

        self.sar.item2index = {v: k for k, v in self.sar.index2item.items()}
        self.sar.user2index = {v: k for k, v in self.sar.index2user.items()}
        self.sar.n_users = len(self.sar.user2index)
        self.sar.n_items = len(self.sar.index2item)

        self.sar.item_similarity = sparse.load_npz(dir_path / "item_similarity.npz")
        self.sar.user_affinity = sparse.load_npz(dir_path / "user_affinity.npz")
        self.sar.item_frequencies = np.load(dir_path / "item_frequencies.npy")

        self._is_fitted = True

    def get_modelled_user_ids(self) -> set[str]:
        """Return set of user IDs known and modelled by SAR (FIX-55)."""
        if self._is_fitted and self.sar is not None and hasattr(self.sar, "user2index"):
            return set(self.sar.user2index.keys())
        return set()
