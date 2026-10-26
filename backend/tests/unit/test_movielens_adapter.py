"""Unit tests for MovieLensAdapter and title cleaning (P3.2)."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from engine.adapters.movielens import MovieLensAdapter, clean_movie_title
from engine.config import load_config

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("raw_title", "expected_title", "expected_year"),
    [
        ("Toy Story (1995)", "Toy Story", 1995),
        ("Matrix, The (1999)", "The Matrix", 1999),
        ("Clockwork Orange, A (1971)", "A Clockwork Orange", 1971),
        ("Affair, An (1998)", "An Affair", 1998),
        ("Postman, The (L' Postino) (1994)", "The Postman", 1994),
        ("Seven (Se7en) (1995)", "Seven", 1995),
        (
            "City of Lost Children, The (Cité des enfants perdus, La) (1995)",
            "The City of Lost Children",
            1995,
        ),
        ("Amélie (Fabuleux destin d'Amélie Poulain, Le) (2001)", "Amélie", 2001),
        ("Good, the Bad and the Ugly, The (1966)", "The Good, the Bad and the Ugly", 1966),
        ("Nightmare Before Christmas, The (1993)", "The Nightmare Before Christmas", 1993),
        ("American President, The (1995)", "The American President", 1995),
        ("Movie With No Year", "Movie With No Year", None),
        ("Movie With Extra Spaces, The   (1985)  ", "The Movie With Extra Spaces", 1985),
        ("Complex Title (a.k.a. Extra) (Another Extra) (2020)", "Complex Title", 2020),
    ],
)
def test_clean_movie_title_edge_cases(
    raw_title: str,
    expected_title: str,
    expected_year: int | None,
) -> None:
    """Verify title cleaning strips years, alternate titles, moves articles, and handles non-ASCII."""
    clean_title, parsed_year = clean_movie_title(raw_title)
    assert clean_title == expected_title
    assert parsed_year == expected_year


def test_movielens_adapter_mock_pipeline(tmp_path: Path) -> None:
    """Verify MovieLensAdapter items, interactions, and filtering on mock fixture."""
    # Create fake ml-100k data structure
    ml_dir = tmp_path / "ml-100k"
    ml_dir.mkdir(parents=True, exist_ok=True)

    # 3 movies
    u_item_lines = [
        "1|Toy Story (1995)|01-Jan-1995||http://imdb.com/1|0|0|0|1|1|1|0|0|0|0|0|0|0|0|0|0|0|0|0\n",
        "2|GoldenEye (1995)|01-Jan-1995||http://imdb.com/2|0|1|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0\n",
        "3|Matrix, The (1999)|01-Jan-1999||http://imdb.com/3|0|1|0|0|0|0|0|0|0|0|0|0|0|0|0|1|1|0|0\n",
    ]
    (ml_dir / "u.item").write_text("".join(u_item_lines), encoding="ISO-8859-1")

    # Interactions: user 10 has 3 ratings, user 20 has 1 rating
    u_data_lines = [
        "10\t1\t5\t1000\n",
        "10\t2\t4\t1010\n",
        "10\t3\t2\t1020\n",
        "20\t1\t4\t1030\n",
    ]
    (ml_dir / "u.data").write_text("".join(u_data_lines), encoding="utf-8")

    # Zip for loader
    zip_path = tmp_path / "ml-100k.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(ml_dir / "u.data", arcname="ml-100k/u.data")
        zf.write(ml_dir / "u.item", arcname="ml-100k/u.item")

    # Copy flat files into tmp_path
    (tmp_path / "u.data").write_text("".join(u_data_lines), encoding="utf-8")
    (tmp_path / "u.item").write_text("".join(u_item_lines), encoding="ISO-8859-1")

    spec = load_config("movies", fast=True)
    # min_user_interactions = 2, min_item_interactions = 1
    spec.dataset.min_user_interactions = 2
    spec.dataset.min_item_interactions = 1

    adapter = MovieLensAdapter(spec, raw_dir=tmp_path)

    # 1. Test items
    items_df = adapter.items()
    assert len(items_df) == 3
    assert set(items_df.columns) == {
        "item_id",
        "title",
        "subtitle",
        "categories",
        "text",
        "year",
        "image_url",
        "extra",
    }
    assert items_df.loc[items_df["item_id"] == "3", "title"].iloc[0] == "The Matrix"
    assert items_df.loc[items_df["item_id"] == "3", "year"].iloc[0] == 1999

    # 2. Test interactions & filtering
    interactions_df = adapter.interactions()
    # User 20 should be dropped by min_user_interactions = 2
    assert "20" not in interactions_df["user_id"].values
    assert "10" in interactions_df["user_id"].values
    assert len(interactions_df) == 3
    assert set(interactions_df.columns) == {"user_id", "item_id", "signal", "timestamp", "positive"}
    assert isinstance(interactions_df["user_id"].iloc[0], str)
    assert isinstance(interactions_df["item_id"].iloc[0], str)

    # 3. Test validation report
    report = adapter.validate()
    assert report.total_interactions == 3
    assert report.unique_users == 1
    assert report.unique_items == 3


@pytest.mark.real_data
def test_movielens_adapter_real_100k_data() -> None:
    """Verify MovieLensAdapter loads real downloaded 100K data cleanly with R1 passing."""
    spec = load_config("movies", fast=True)
    adapter = MovieLensAdapter(spec)

    # Real data was downloaded in P3.1 to data/raw/movielens
    if (
        not (adapter.raw_dir / "ml-100k").exists()
        and not (adapter.raw_dir / "ml-100k.zip").exists()
    ):
        pytest.skip("Real MovieLens data not found in data/raw/movielens")

    items_df = adapter.items()
    interactions_df = adapter.interactions()

    assert len(items_df) == 1682
    assert len(interactions_df) > 90000
    assert "Toy Story" in items_df["title"].values
    assert "The Shawshank Redemption" in items_df["title"].values

    # Test R1 validation
    report = adapter.validate()
    assert report.total_interactions == len(interactions_df)
    assert report.sparsity > 0.0

    # Test splitting with leakage check
    train_df, valid_df, test_df = adapter.split(interactions_df)
    assert len(train_df) > len(valid_df)
    assert len(train_df) > len(test_df)
    assert not train_df.empty


def test_movielens_adapter_validate_writes_report(tmp_path: Path) -> None:
    """Verify validate(output_path) writes full R1 data report JSON file."""
    import json

    # Create isolated mock raw data in tmp_path/raw
    raw_dir = tmp_path / "raw"
    ml_dir = raw_dir / "ml-100k"
    ml_dir.mkdir(parents=True, exist_ok=True)
    u_item_lines = [
        "1|Toy Story (1995)|01-Jan-1995||http://imdb.com/1|0|0|0|1|1|1|0|0|0|0|0|0|0|0|0|0|0|0|0\n",
        "2|GoldenEye (1995)|01-Jan-1995||http://imdb.com/2|0|1|1|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0\n",
    ]
    (ml_dir / "u.item").write_text("".join(u_item_lines), encoding="ISO-8859-1")
    u_data_lines = [
        "10\t1\t5\t1000\n",
        "10\t2\t4\t1010\n",
    ]
    (ml_dir / "u.data").write_text("".join(u_data_lines), encoding="utf-8")
    (raw_dir / "u.data").write_text("".join(u_data_lines), encoding="utf-8")
    (raw_dir / "u.item").write_text("".join(u_item_lines), encoding="ISO-8859-1")

    spec = load_config("movies", fast=True)
    spec.dataset.min_user_interactions = 1
    spec.dataset.min_item_interactions = 1
    adapter = MovieLensAdapter(spec, raw_dir=raw_dir)

    out_file = tmp_path / "data_report.json"
    report = adapter.validate(output_path=out_file)

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))

    assert data["total_interactions"] == report.total_interactions
    assert data["unique_users"] == report.unique_users
    assert data["unique_items"] == report.unique_items
    assert data["sparsity"] == report.sparsity
    assert "filtered_users" in data
    assert "filtered_items" in data
    assert "min_timestamp" in data
    assert "max_timestamp" in data
    assert "details" in data
