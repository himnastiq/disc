#!/usr/bin/env python3
"""Download datasets to data/raw/<name>/.

Usage:
    python backend/scripts/fetch_data.py [--type TYPE] [--variant VARIANT] [--dry-run] [--help]

If a download fails (network, terms, etc.), prints exact manual steps
and the expected file paths.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import zipfile
from pathlib import Path

import urllib3

# Suppress insecure request warnings if fallback SSL is used on restricted systems
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Project root (two levels up from backend/scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data" / "raw"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_data")


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


def download_url(url: str, dest_path: Path) -> bool:
    """Download url to dest_path with SSL verification fallback and progress reporting."""
    import requests

    if dest_path.exists() and dest_path.stat().st_size > 0:
        logger.info("File already exists: %s", dest_path)
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

    try:
        try:
            r = requests.get(url, stream=True, timeout=30)
        except requests.exceptions.SSLError:
            logger.warning(
                "SSL verification failed for %s. Retrying with fallback (verify=False)...", url
            )
            r = requests.get(url, stream=True, verify=False, timeout=30)

        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(temp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        if total_size > 0 and downloaded < total_size:
            raise OSError(f"Truncated download: expected {total_size} bytes, got {downloaded}")

        temp_path.replace(dest_path)
        logger.info("Successfully downloaded: %s (%d bytes)", dest_path.name, downloaded)
        return True
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        logger.error("Download failed for %s: %s", url, e)
        return False


def fetch_movielens(target_dir: Path, variant: str = "both") -> bool:
    """Download and extract MovieLens 100k and/or 1m datasets, then verify loading."""
    target_dir.mkdir(parents=True, exist_ok=True)
    variants = ["100k", "1m"] if variant == "both" else [variant.lower()]
    base_url = "https://files.grouplens.org/datasets/movielens/"
    all_success = True

    for v in variants:
        zip_name = f"ml-{v}.zip"
        zip_path = target_dir / zip_name
        url = f"{base_url}{zip_name}"

        logger.info("Fetching MovieLens %s from %s...", v.upper(), url)
        if not download_url(url, zip_path):
            print(f"\n[!] Automatic download failed for MovieLens {v.upper()}.")
            print(f"    Manual step: Download {url} and save to {zip_path}\n")
            all_success = False
            continue

        # Extract zip
        logger.info("Extracting %s...", zip_name)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(target_dir)

        # Ensure flat rating & item paths exist in target_dir for discovery loader compatibility
        if v == "100k":
            u_data = target_dir / "ml-100k" / "u.data"
            u_item = target_dir / "ml-100k" / "u.item"
            if u_data.exists():
                shutil.copyfile(u_data, target_dir / "u.data")
            if u_item.exists():
                shutil.copyfile(u_item, target_dir / "u.item")
        elif v == "1m":
            ratings_dat = target_dir / "ml-1m" / "ratings.dat"
            movies_dat = target_dir / "ml-1m" / "movies.dat"
            if ratings_dat.exists():
                shutil.copyfile(ratings_dat, target_dir / "ratings.dat")
            if movies_dat.exists():
                shutil.copyfile(movies_dat, target_dir / "movies.dat")

    # Confirm loading with discovery loader
    try:
        from discovery.datasets.movielens import load_pandas_df

        for v in variants:
            df = load_pandas_df(size=v, local_cache_path=str(target_dir))
            logger.info(
                "MovieLens %s verified: %d interactions loaded successfully.", v.upper(), len(df)
            )
    except Exception as e:
        logger.error("Failed to verify MovieLens loading with discovery package: %s", e)
        all_success = False

    return all_success


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
        "--variant",
        default="both",
        help="Variant to download if supported by dataset type (e.g. 100k, 1m, or both)",
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

            if t == "movies":
                success = fetch_movielens(target, variant=args.variant)
                if not success:
                    print("\n[!] MovieLens fetch finished with errors or required manual steps.")
            else:
                print(f"\n  Target directory created: {target}")
                print(f"  NOTE: Actual download logic for {t} will be added in Phases 4-5.")
                print("  For now, follow the manual steps above if needed.")

    print("\n" + "=" * 40)
    print("Done.")


if __name__ == "__main__":
    main()
