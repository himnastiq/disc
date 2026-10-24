#!/usr/bin/env python3
"""Download datasets to data/raw/<name>/.

Usage:
    python scripts/fetch_data.py [--type TYPE] [--dry-run] [--help]

If a download fails (network, terms, etc.), prints exact manual steps
and the expected file paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Project root (two levels up from backend/scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

DATASETS: dict[str, dict[str, str]] = {
    "movies": {
        "name": "MovieLens",
        "description": "MovieLens 100K and 1M datasets",
        "url": "https://grouplens.org/datasets/movielens/",
        "target_dir": str(DATA_DIR / "movielens"),
        "manual_steps": (
            "1. Visit https://grouplens.org/datasets/movielens/\n"
            "2. Download ml-100k.zip and ml-1m.zip\n"
            "3. Extract to data/raw/movielens/ml-100k/ and data/raw/movielens/ml-1m/"
        ),
    },
    "products": {
        "name": "Amazon Reviews",
        "description": "Amazon product reviews dataset",
        "url": "https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/",
        "target_dir": str(DATA_DIR / "amazon"),
        "manual_steps": (
            "1. Visit https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/\n"
            "2. Download a mid-size 5-core category (e.g., Electronics) and its metadata\n"
            "3. Place files in data/raw/amazon/"
        ),
    },
    "articles": {
        "name": "MIND",
        "description": "MIND-small news recommendation dataset",
        "url": "https://msnews.github.io/",
        "target_dir": str(DATA_DIR / "mind"),
        "manual_steps": (
            "1. Visit https://msnews.github.io/\n"
            "2. Download MINDsmall_train.zip and MINDsmall_dev.zip\n"
            "3. Extract to data/raw/mind/train/ and data/raw/mind/dev/"
        ),
    },
}


def print_dataset_info(name: str, info: dict[str, str], dry_run: bool = False) -> None:
    """Print information about a dataset."""
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Dataset: {info['name']}")
    print(f"  Description: {info['description']}")
    print(f"  URL: {info['url']}")
    print(f"  Target: {info['target_dir']}")
    if dry_run:
        print(f"  Would download to: {info['target_dir']}")
    else:
        print("  Status: Download will be implemented per type in Phases 3-5.")
        print("  Manual steps if needed:")
        for line in info["manual_steps"].split("\n"):
            print(f"    {line}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download datasets for Discovery Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--type",
        choices=list(DATASETS.keys()),
        help="Download a specific dataset type (movies, products, articles)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    args = parser.parse_args()

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    types_to_fetch = [args.type] if args.type else list(DATASETS.keys())

    print("Discovery Engine - Dataset Downloader")
    print("=" * 40)

    for t in types_to_fetch:
        info = DATASETS[t]
        print_dataset_info(t, info, dry_run=args.dry_run)

        if not args.dry_run:
            target = Path(info["target_dir"])
            target.mkdir(parents=True, exist_ok=True)
            print(f"\n  Target directory created: {target}")
            print("  NOTE: Actual download logic will be added in Phases 3-5.")
            print("  For now, follow the manual steps above if needed.")

    print("\n" + "=" * 40)
    print("Done.")


if __name__ == "__main__":
    main()
