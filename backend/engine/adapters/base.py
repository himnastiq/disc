"""Discovery Engine - Base dataset adapter interface (P2.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

    from engine.schema import ContentTypeSpec, ValidationReport


class DatasetAdapter(ABC):
    """Abstract dataset adapter interface.

    Adapters own all dataset-specific logic (parsing, title cleaning, ID mapping,
    filtering, and raw downloading). The core engine contains no dataset-specific code.
    """

    def __init__(self, spec: ContentTypeSpec) -> None:
        """Initialize adapter with content type specification.

        Args:
            spec: Validated ContentTypeSpec containing dataset parameters and rules.
        """
        self.spec = spec

    @abstractmethod
    def download(self, raw_dir: Path) -> None:
        """Download raw dataset assets into the specified directory if not already present.

        Args:
            raw_dir: Target directory where raw dataset archives or files should be stored.
        """

    @abstractmethod
    def load_raw(self, raw_dir: Path) -> Any:
        """Load raw dataset records or dataframes into memory.

        Args:
            raw_dir: Path to directory where raw dataset files are stored.

        Returns:
            Dataset-specific intermediate data object or container.
        """

    @abstractmethod
    def interactions(self) -> pd.DataFrame:
        """Extract canonical interactions DataFrame conforming to engine schema.

        Required columns:
            - user_id (str): Unique user identifier.
            - item_id (str): Unique item identifier.
            - signal (float): Interaction weight or rating score.
            - timestamp (int): Unix epoch timestamp in seconds.
            - positive (bool): True if signal meets or exceeds positive_threshold.

        Returns:
            pd.DataFrame: Cleaned canonical interactions.
        """

    @abstractmethod
    def items(self) -> pd.DataFrame:
        """Extract canonical items/catalogue DataFrame conforming to engine schema.

        Required columns:
            - item_id (str): Unique item identifier.
            - title (str): Clean display title.
            - subtitle (str | None): Secondary info, brand, or category line.
            - categories (list[str]): List of category tags or genre names.
            - text (str | None): Abstract, description, or content text.
            - year (int | None): Release or publication year.
            - image_url (str | None): Optional URL for cover/poster.
            - extra (dict): Arbitrary type-specific metadata dictionary.

        Returns:
            pd.DataFrame: Canonical item metadata catalogue.
        """

    @abstractmethod
    def validate(self) -> ValidationReport:
        """Validate datasets against schema, quality constraints, and R1 requirements.

        Returns:
            ValidationReport: Summary of counts, sparsity, timestamp ranges, and health.
        """

    @abstractmethod
    def split(self, interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split interactions into train, validation, and test partitions according to config strategy.

        Args:
            interactions: Canonical interactions DataFrame.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: (train_df, valid_df, test_df)
        """
