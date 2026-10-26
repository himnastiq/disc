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
import os
import shutil
import sys
import zipfile
from pathlib import Path

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
        "description": "Amazon product reviews dataset (Video Games and Musical Instruments 5-core)",
        "url": "http://snap.stanford.edu/data/amazon/productGraph/",
        "target_dir": str(DATA_DIR / "amazon"),
        "manual_steps": (
            "1. Visit http://snap.stanford.edu/data/amazon/productGraph/categoryFiles/\n"
            "2. Download reviews_Video_Games_5.json.gz and meta_Video_Games.json.gz to data/raw/amazon/video_games/\n"
            "3. Download reviews_Musical_Instruments_5.json.gz and meta_Musical_Instruments.json.gz to data/raw/amazon/instruments/"
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
        ca_bundle: str | bool
        try:
            import certifi

            ca_bundle = certifi.where()
        except ImportError:
            ca_bundle = True

        opt_out = os.environ.get("DISCOVERY_INSECURE_SSL", "0").lower() in ("1", "true", "yes")
        verify = False if opt_out else ca_bundle
        if opt_out:
            logger.warning("TLS verification disabled via DISCOVERY_INSECURE_SSL=1 for %s", url)

        r = requests.get(url, stream=True, verify=verify, timeout=30)
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


def fetch_amazon(target_dir: Path, variant: str = "both") -> bool:
    """Download Amazon reviews and metadata files for the specified category variant."""
    categories: dict[str, str] = {
        "instruments": "Musical_Instruments",
        "video_games": "Video_Games",
    }

    v_lower = variant.lower()
    if v_lower in categories:
        selected_variants = [v_lower]
    elif v_lower in ("both", "all", "default"):
        selected_variants = ["instruments", "video_games"]
    else:
        logger.error(
            "Unknown Amazon variant '%s'. Choose from %s or 'both'.",
            variant,
            list(categories.keys()),
        )
        return False

    base_url = "http://snap.stanford.edu/data/amazon/productGraph/categoryFiles"
    all_success = True

    for v in selected_variants:
        cat_name = categories[v]
        v_dir = target_dir / v
        v_dir.mkdir(parents=True, exist_ok=True)

        reviews_filename = f"reviews_{cat_name}_5.json.gz"
        meta_filename = f"meta_{cat_name}.json.gz"

        logger.info("Fetching Amazon %s (%s)...", v, cat_name)
        s1 = download_url(f"{base_url}/{reviews_filename}", v_dir / reviews_filename)
        s2 = download_url(f"{base_url}/{meta_filename}", v_dir / meta_filename)

        if not (s1 and s2):
            logger.error("Failed downloading Amazon %s dataset files.", v)
            all_success = False
        else:
            logger.info("Amazon %s (%s) files verified on disk.", v, cat_name)

    return all_success


def fetch_mind(target_dir: Path, variant: str = "small") -> bool:
    """Download and extract MIND dataset (train and dev splits).

    If direct network download is blocked due to Microsoft licensing/authentication,
    prints clear manual instructions with exact expected file paths.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    train_dir = target_dir / "train"
    dev_dir = target_dir / "dev"
    train_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)

    expected_files = [
        train_dir / "news.tsv",
        train_dir / "behaviors.tsv",
        dev_dir / "news.tsv",
        dev_dir / "behaviors.tsv",
    ]

    if all(p.exists() and p.stat().st_size > 0 for p in expected_files):
        logger.info("MIND dataset files already present in %s", target_dir)
        return True

    # Check for fixture fallback if requested or in offline development
    fixture_dir = BACKEND_DIR / "tests" / "fixtures" / "mind"
    if variant in ("fast", "mock", "demo") and fixture_dir.exists():
        for split in ("train", "dev"):
            s_dir = target_dir / split
            s_dir.mkdir(parents=True, exist_ok=True)
            for fname in ("news.tsv", "behaviors.tsv"):
                src = fixture_dir / split / fname
                dst = s_dir / fname
                if src.exists() and not dst.exists():
                    shutil.copy(src, dst)
        if all(p.exists() and p.stat().st_size > 0 for p in expected_files):
            logger.info("MIND fast/mock fixture files initialized in %s", target_dir)
            return True

    # Try downloading via candidate URLs
    candidate_urls = [
        (
            "https://recodatasets.z20.web.core.windows.net/newsrec/MINDsmall_train.zip",
            "https://recodatasets.z20.web.core.windows.net/newsrec/MINDsmall_dev.zip",
        ),
        (
            "https://mind201910.blob.core.windows.net/mind/MINDsmall_train.zip",
            "https://mind201910.blob.core.windows.net/mind/MINDsmall_dev.zip",
        ),
    ]

    download_success = False
    for train_url, dev_url in candidate_urls:
        train_zip = target_dir / "MINDsmall_train.zip"
        dev_zip = target_dir / "MINDsmall_dev.zip"
        if download_url(train_url, train_zip) and download_url(dev_url, dev_zip):
            try:
                with zipfile.ZipFile(train_zip, "r") as z:
                    z.extractall(train_dir)
                with zipfile.ZipFile(dev_zip, "r") as z:
                    z.extractall(dev_dir)
                train_zip.unlink(missing_ok=True)
                dev_zip.unlink(missing_ok=True)
                download_success = True
                break
            except Exception as e:
                logger.warning("Extraction failed for downloaded MIND zips: %s", e)

    if not download_success:
        print("\n" + "=" * 60)
        print("  [!] AUTOMATED DOWNLOAD BLOCKED: MIND (Microsoft News Dataset)")
        print("=" * 60)
        print("  Direct public blob access to the Microsoft Azure storage container")
        print("  is restricted. The official MIND repository now requires accepting")
        print("  the Microsoft Research License Agreement.")
        print("\n  MANUAL SETUP INSTRUCTIONS:")
        print("  1. Visit the official Hugging Face mirror:")
        print("     https://huggingface.co/datasets/yjw1029/MIND")
        print(
            "     (or Kaggle: https://www.kaggle.com/datasets/swiftQuiet/mind-microsoft-news-dataset)"
        )
        print("  2. Download MINDsmall_train.zip and MINDsmall_dev.zip")
        print("  3. Extract to the following exact locations:")
        print(f"     - {train_dir / 'news.tsv'}")
        print(f"     - {train_dir / 'behaviors.tsv'}")
        print(f"     - {dev_dir / 'news.tsv'}")
        print(f"     - {dev_dir / 'behaviors.tsv'}")
        print("=" * 60 + "\n")
        return False

    return True


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
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL/TLS certificate verification (opt-out fallback)",
    )
    args = parser.parse_args()

    if args.insecure:
        os.environ["DISCOVERY_INSECURE_SSL"] = "1"

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
            elif t == "products":
                success = fetch_amazon(target, variant=args.variant)
                if not success:
                    print(
                        "\n[!] Amazon Products fetch finished with errors or required manual steps."
                    )
            elif t == "articles":
                success = fetch_mind(target, variant=args.variant)
                if not success:
                    print(
                        "\n[!] MIND Articles fetch finished with blocked note or required manual steps."
                    )

    print("\n" + "=" * 40)
    print("Done.")


if __name__ == "__main__":
    main()
