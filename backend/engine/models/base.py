"""Discovery Engine - Base recommender model interface (P2.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    import pandas as pd

    from engine.schema import ContentTypeSpec, Reason, ScoredItem


class RecommenderModel(ABC):
    """Abstract interface for all recommendation algorithms.

    Defines training, single-user recommendation, cold-start history recommendation,
    similarity queries, popularity fallbacks, explanations, and artifact persistence.
    """

    def __init__(self, spec: ContentTypeSpec) -> None:
        """Initialize model with content type specification.

        Args:
            spec: Validated ContentTypeSpec containing model parameters and constraints.
        """
        self.spec = spec

    @property
    @abstractmethod
    def supports_cold_start(self) -> bool:
        """Whether this model natively supports cold-start recommendations from interaction histories."""

    @abstractmethod
    def fit(self, train_interactions: pd.DataFrame, items: pd.DataFrame) -> None:
        """Fit model on training interactions and item catalogue.

        Args:
            train_interactions: Canonical interactions DataFrame conforming to engine schema.
            items: Canonical items DataFrame conforming to engine schema.
        """

    @abstractmethod
    def recommend_user(
        self,
        user_id: str,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k recommendations for a known training user.

        Args:
            user_id: String user ID known to the model.
            k: Number of recommendations to produce (1 <= k <= 50).
            exclude_ids: Collection of item IDs that must not appear in results (e.g. seen items).

        Returns:
            list[ScoredItem]: Top-k scored items sorted descending by score.

        Raises:
            UnknownUser: If user_id was not present in the training interactions.
        """

    @abstractmethod
    def recommend_history(
        self,
        history: list[tuple[str, float]],
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k recommendations for an arbitrary interaction history (cold-start / anonymous user).

        Args:
            history: List of (item_id, signal) tuples representing user preference history.
            k: Number of recommendations to produce (1 <= k <= 50).
            exclude_ids: Collection of item IDs that must not appear in results.

        Returns:
            list[ScoredItem]: Top-k scored items sorted descending by score.

        Raises:
            ColdStartUnsupported: If this model does not support history-based cold start.
        """

    @abstractmethod
    def similar_items(
        self,
        item_id: str,
        k: int,
    ) -> list[ScoredItem]:
        """Find top-k most similar items to query item.

        Query item itself must NEVER be returned in the results.

        Args:
            item_id: Target item ID.
            k: Number of similar items to return.

        Returns:
            list[ScoredItem]: Top-k similar items sorted descending by similarity.

        Raises:
            UnknownItem: If item_id is not in the model catalogue.
        """

    @abstractmethod
    def popular(
        self,
        k: int,
        exclude_ids: Collection[str] = (),
    ) -> list[ScoredItem]:
        """Generate top-k global popular items.

        Ties must be broken deterministically (e.g. by item_id ascending).

        Args:
            k: Number of recommendations to return.
            exclude_ids: Collection of item IDs to exclude.

        Returns:
            list[ScoredItem]: Top-k popular items sorted descending by popularity score.
        """

    @abstractmethod
    def explain(
        self,
        history_item_ids: list[str],
        recommended_item_id: str,
        min_threshold: float | None = None,
    ) -> Reason | None:
        """Produce a faithful explanation identifying which history item contributed most to the score.

        Args:
            history_item_ids: List of item IDs from the user's history.
            recommended_item_id: Recommended item ID to explain.
            min_threshold: Optional minimum contribution share threshold (defaults to serving config).

        Returns:
            Reason | None: Faithful attribution reason, or None if no sufficient attribution exists.
        """

    @abstractmethod
    def save(self, dir_path: Path) -> None:
        """Persist model parameters and indices to directory.

        Must NOT use arbitrary Python pickles for serving artifacts (use npz, parquet, json, scipy sparse).

        Args:
            dir_path: Target directory path.
        """

    @abstractmethod
    def load(self, dir_path: Path) -> None:
        """Load model parameters and indices from directory.

        Args:
            dir_path: Source directory path containing saved model artifacts.
        """
