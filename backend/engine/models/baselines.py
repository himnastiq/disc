"""Discovery Engine - Baseline models (Popularity, Random) (P2.4)."""

from __future__ import annotations

import hashlib
import json
import random
from typing import TYPE_CHECKING, Any

from engine.errors import UnknownItem, UnknownUser
from engine.models.base import RecommenderModel
from engine.schema import ContentTypeSpec, Reason, ScoredItem

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    import pandas as pd


class PopularityModel(RecommenderModel):
    """Popularity baseline model.

    Recommends items with the highest count of positive interactions.
    Ties are broken deterministically by item ID in ascending lexicographical order.
    """

    def __init__(self, spec: ContentTypeSpec) -> None:
        super().__init__(spec)
        self.catalogue: list[str] = []
        self.item_counts: dict[str, int] = {}
        self.sorted_items: list[str] = []
        self.known_users: set[str] = set()
        self.user_seen: dict[str, set[str]] = {}

    @property
    def supports_cold_start(self) -> bool:
        return True

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        """Fit model on training interactions and item catalogue."""
        self.catalogue = sorted(items["item_id"].astype(str).unique())

        if "positive" in train_interactions.columns:
            positive_df = train_interactions[train_interactions["positive"] == True]  # noqa: E712
        else:
            threshold = self.spec.signal.positive_threshold
            positive_df = train_interactions[train_interactions["signal"] >= threshold]

        counts_series = positive_df["item_id"].astype(str).value_counts()
        counts_dict = counts_series.to_dict()

        self.item_counts = {item_id: int(counts_dict.get(item_id, 0)) for item_id in self.catalogue}

        # Deterministic sorting: highest positive interaction count first,
        # ties broken by item_id ascending.
        self.sorted_items = sorted(
            self.catalogue,
            key=lambda x: (-self.item_counts[x], x),
        )

        if not train_interactions.empty:
            self.known_users = set(train_interactions["user_id"].astype(str).unique())
            # Map known users to seen items
            seen_groups = train_interactions.groupby("user_id")["item_id"].apply(
                lambda s: set(s.astype(str))
            )
            self.user_seen = {str(u): set(s) for u, s in seen_groups.items()}
        else:
            self.known_users = set()
            self.user_seen = {}

    def _select_top_k(
        self,
        k: int,
        exclude_set: set[str],
    ) -> list[ScoredItem]:
        results: list[ScoredItem] = []
        rank = 1
        for item_id in self.sorted_items:
            if item_id not in exclude_set:
                score = float(self.item_counts[item_id])
                results.append(ScoredItem(item_id=item_id, score=score, rank=rank))
                rank += 1
                if len(results) >= k:
                    break
        return results

    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        if user_id not in self.known_users:
            raise UnknownUser(user_id=user_id, content_type=self.spec.type)

        exclude_set = set(exclude_ids)
        if not self.spec.model.allow_repeat:
            exclude_set |= self.user_seen.get(user_id, set())

        return self._select_top_k(k, exclude_set)

    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        exclude_set = set(exclude_ids)
        if not self.spec.model.allow_repeat:
            exclude_set |= {item_id for item_id, _ in history}

        return self._select_top_k(k, exclude_set)

    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        if item_id not in self.item_counts:
            raise UnknownItem(item_id=item_id, content_type=self.spec.type)

        # Similar items fallback for popularity: most popular other items
        exclude_set = {item_id}
        return self._select_top_k(k, exclude_set)

    def popular(
        self,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        exclude_set = set(exclude_ids)
        return self._select_top_k(k, exclude_set)

    def explain(
        self,
        recommended_item_id: str = "",
        history: list[tuple[str, float]] | list[str] | None = None,
        user_id: str | None = None,
        min_threshold: float | None = None,
        **kwargs: Any,
    ) -> Reason | None:
        # Popularity recommendations are independent of user history items.
        return None

    def save(self, dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        data = {
            "item_counts": self.item_counts,
            "sorted_items": self.sorted_items,
            "known_users": sorted(self.known_users),
            "user_seen": {u: sorted(s) for u, s in self.user_seen.items()},
        }
        (dir_path / "popularity_model.json").write_text(json.dumps(data), encoding="utf-8")

    def load(self, dir_path: Path) -> None:
        file_path = dir_path / "popularity_model.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        self.item_counts = data["item_counts"]
        self.sorted_items = data["sorted_items"]
        self.catalogue = sorted(self.item_counts.keys())
        self.known_users = set(data["known_users"])
        self.user_seen = {u: set(s) for u, s in data["user_seen"].items()}


class RandomModel(RecommenderModel):
    """Random baseline model.

    Generates pseudo-random recommendations deterministic per user and per seed.
    """

    def __init__(self, spec: ContentTypeSpec, seed: int = 42) -> None:
        super().__init__(spec)
        self.seed = getattr(spec.split, "seed", seed) or seed
        self.catalogue: list[str] = []
        self.known_users: set[str] = set()
        self.user_seen: dict[str, set[str]] = {}

    @property
    def supports_cold_start(self) -> bool:
        return True

    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        """Fit model on training interactions and item catalogue."""
        self.catalogue = sorted(items["item_id"].astype(str).unique())

        if not train_interactions.empty:
            self.known_users = set(train_interactions["user_id"].astype(str).unique())
            seen_groups = train_interactions.groupby("user_id")["item_id"].apply(
                lambda s: set(s.astype(str))
            )
            self.user_seen = {str(u): set(s) for u, s in seen_groups.items()}
        else:
            self.known_users = set()
            self.user_seen = {}

    def _derive_seed(self, context: str) -> int:
        raw_bytes = f"{self.seed}:{context}".encode()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        return int(digest[:8], 16)

    def _sample_k(
        self,
        k: int,
        exclude_set: set[str],
        context: str,
    ) -> list[ScoredItem]:
        candidates = [item for item in self.catalogue if item not in exclude_set]
        if not candidates:
            return []

        rng = random.Random(self._derive_seed(context))
        sampled = rng.sample(candidates, min(k, len(candidates)))

        results: list[ScoredItem] = []
        n = len(sampled)
        for rank, item_id in enumerate(sampled, start=1):
            score = 1.0 - ((rank - 1) / max(n, 1))
            results.append(ScoredItem(item_id=item_id, score=score, rank=rank))
        return results

    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        if user_id not in self.known_users:
            raise UnknownUser(user_id=user_id, content_type=self.spec.type)

        exclude_set = set(exclude_ids)
        if not self.spec.model.allow_repeat:
            exclude_set |= self.user_seen.get(user_id, set())

        return self._sample_k(k, exclude_set, f"user:{user_id}")

    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        exclude_set = set(exclude_ids)
        if not self.spec.model.allow_repeat:
            exclude_set |= {item_id for item_id, _ in history}

        context = "history:" + ",".join(sorted(f"{item_id}:{sig:.2f}" for item_id, sig in history))
        return self._sample_k(k, exclude_set, context)

    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        if item_id not in self.catalogue:
            raise UnknownItem(item_id=item_id, content_type=self.spec.type)

        exclude_set = {item_id}
        return self._sample_k(k, exclude_set, f"similar:{item_id}")

    def popular(
        self,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        exclude_set = set(exclude_ids)
        return self._sample_k(k, exclude_set, "global_popular")

    def explain(
        self,
        recommended_item_id: str = "",
        history: list[tuple[str, float]] | list[str] | None = None,
        user_id: str | None = None,
        min_threshold: float | None = None,
        **kwargs: Any,
    ) -> Reason | None:
        # Random model recommendations are independent of user history items.
        return None

    def save(self, dir_path: Path) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        data = {
            "seed": self.seed,
            "catalogue": self.catalogue,
            "known_users": sorted(self.known_users),
            "user_seen": {u: sorted(s) for u, s in self.user_seen.items()},
        }
        (dir_path / "random_model.json").write_text(json.dumps(data), encoding="utf-8")

    def load(self, dir_path: Path) -> None:
        file_path = dir_path / "random_model.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        self.seed = data["seed"]
        self.catalogue = data["catalogue"]
        self.known_users = set(data["known_users"])
        self.user_seen = {u: set(s) for u, s in data["user_seen"].items()}
