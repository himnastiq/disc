"""Discovery Engine - Toy dataset adapter for testing and verification (P2.12)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.adapters.base import DatasetAdapter
from engine.evaluation.checks import check_r1_data_validity
from engine.evaluation.splits import split_interactions
from engine.registry import register_adapter

if TYPE_CHECKING:
    from pathlib import Path

    from engine.schema import ContentTypeSpec, ValidationReport


@register_adapter("toy")
class ToyAdapter(DatasetAdapter):
    """Synthetic dataset adapter used for unit testing, fast validation, and CLI checks."""

    def __init__(self, spec: ContentTypeSpec) -> None:
        super().__init__(spec)
        self.raw_data: dict[str, Any] = {}

    def download(self, raw_dir: Path) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "toy_info.txt").write_text(
            "Synthetic toy dataset generated in-memory.\n", encoding="utf-8"
        )

    def load_raw(self, raw_dir: Path) -> Any:
        return {"loaded_from": str(raw_dir)}

    def items(self) -> pd.DataFrame:
        """Generate canonical toy catalogue."""
        items_rows = []
        for i in range(1, 26):
            items_rows.append(
                {
                    "item_id": f"toy_item_{i}",
                    "title": f"Toy Item {i}",
                    "subtitle": f"Brand {((i - 1) % 5) + 1}",
                    "categories": ["Category A" if i % 2 == 0 else "Category B"],
                    "text": f"Description for toy item {i} with sample keywords.",
                    "year": 2020 + (i % 5),
                    "image_url": f"https://example.com/images/toy_{i}.jpg",
                    "extra": {"price": 10.0 + i},
                }
            )
        return pd.DataFrame(items_rows)

    def interactions(self) -> pd.DataFrame:
        """Generate canonical toy interactions."""
        rows = []
        # 15 users, each with 12 interactions
        for u in range(1, 16):
            user_id = f"toy_user_{u}"
            for step in range(1, 13):
                item_idx = ((u + step) % 25) + 1
                signal = 5.0 if step % 3 != 0 else 2.0
                rows.append(
                    {
                        "user_id": user_id,
                        "item_id": f"toy_item_{item_idx}",
                        "signal": float(signal),
                        "timestamp": 1000 * u + 10 * step,
                        "positive": signal >= self.spec.signal.positive_threshold,
                    }
                )
        return pd.DataFrame(rows)

    def validate(self) -> ValidationReport:
        """Run R1 validation checks on toy dataset."""
        return check_r1_data_validity(
            interactions=self.interactions(),
            items=self.items(),
            positive_threshold=self.spec.signal.positive_threshold,
        )

    def split(self, interactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split toy interactions according to config strategy."""
        split_ratio = self.spec.split.ratio
        test_ratio = (1.0 - split_ratio) / 2.0
        return split_interactions(
            interactions=interactions,
            strategy=self.spec.split.strategy,
            ratios=(split_ratio, test_ratio, test_ratio),
            run_leakage_check=True,
        )
