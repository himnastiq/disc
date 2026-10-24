"""Smoke tests for vendored discovery code on tiny synthetic data (P1.7)."""

import zipfile

import pandas as pd
import pytest

from discovery.datasets.movielens import load_item_df, load_pandas_df
from discovery.datasets.python_splitters import python_chrono_split
from discovery.evaluation.python_evaluation import map_at_k, ndcg_at_k, precision_at_k, recall_at_k
from discovery.models.sar import SAR
from discovery.models.tfidf import TfidfRecommender


def test_sar_fit_and_recommend():
    """Verify SAR fit and recommendation on synthetic ratings data."""
    train_data = pd.DataFrame(
        {
            "userID": [1, 1, 1, 2, 2, 2, 3, 3],
            "itemID": [101, 102, 103, 101, 102, 104, 102, 103],
            "rating": [5.0, 4.0, 3.0, 4.0, 5.0, 2.0, 3.0, 4.0],
            "timestamp": [1000, 1010, 1020, 1005, 1015, 1025, 1012, 1022],
        }
    )

    model = SAR(
        col_user="userID",
        col_item="itemID",
        col_rating="rating",
        col_timestamp="timestamp",
        similarity_type="jaccard",
    )
    model.fit(train_data)

    test_users = pd.DataFrame({"userID": [1, 2, 3]})
    recs = model.recommend_k_items(test_users, top_k=2, remove_seen=True)

    assert not recs.empty
    assert set(recs.columns) == {"userID", "itemID", "prediction"}
    assert len(recs) <= 6

    # Test remove_seen: user 1 has seen items 101, 102, 103, so recommended items cannot include them
    u1_recs = recs[recs["userID"] == 1]["itemID"].tolist()
    for seen_item in [101, 102, 103]:
        assert seen_item not in u1_recs


def test_chronological_split_correctness():
    """Verify python_chrono_split splits chronologically per user with zero temporal leakage."""
    data = pd.DataFrame(
        {
            "userID": [1, 1, 1, 1, 2, 2, 2, 2],
            "itemID": [10, 20, 30, 40, 10, 20, 30, 40],
            "rating": [5.0, 4.0, 3.0, 2.0, 4.0, 5.0, 3.0, 1.0],
            "timestamp": [100, 200, 300, 400, 150, 250, 350, 450],
        }
    )

    train, test = python_chrono_split(
        data,
        ratio=0.75,
        min_rating=1,
        filter_by="user",
        col_user="userID",
        col_item="itemID",
        col_timestamp="timestamp",
    )

    assert len(train) == 6
    assert len(test) == 2

    # Check for each user that every train timestamp is strictly before the test timestamp
    for user_id in [1, 2]:
        user_train_max_ts = train[train["userID"] == user_id]["timestamp"].max()
        user_test_min_ts = test[test["userID"] == user_id]["timestamp"].min()
        assert user_train_max_ts < user_test_min_ts


def test_metrics_against_hand_computed_values():
    """Verify precision, recall, MAP, and NDCG match exact hand-computed values.

    Scenario:
      User 1 has true relevant items: {1, 2}
      Model recommended top-2 items: [1, 3] with predictions [2.0, 1.0]

    Hand computation:
      - Item 1 is relevant (hit), Item 3 is not relevant (miss)
      - Precision@2 = 1 hit / 2 recommended = 0.5
      - Recall@2 = 1 hit / 2 relevant = 0.5
      - MAP@2 = (Precision@1) / 2 = 1.0 / 2 = 0.5
      - DCG@2 = 1 / log2(1+1) = 1.0
      - IDCG@2 = 1 / log2(1+1) + 1 / log2(2+1) = 1.0 + 0.63092975 = 1.63092975
      - NDCG@2 = 1.0 / 1.63092975 = 0.613147...
    """
    rating_true = pd.DataFrame({"userID": [1, 1], "itemID": [1, 2], "rating": [1.0, 1.0]})
    rating_pred = pd.DataFrame({"userID": [1, 1], "itemID": [1, 3], "prediction": [2.0, 1.0]})

    p = precision_at_k(
        rating_true,
        rating_pred,
        col_user="userID",
        col_item="itemID",
        col_prediction="prediction",
        k=2,
    )
    r = recall_at_k(
        rating_true,
        rating_pred,
        col_user="userID",
        col_item="itemID",
        col_prediction="prediction",
        k=2,
    )
    m = map_at_k(
        rating_true,
        rating_pred,
        col_user="userID",
        col_item="itemID",
        col_prediction="prediction",
        k=2,
    )
    n = ndcg_at_k(
        rating_true,
        rating_pred,
        col_user="userID",
        col_item="itemID",
        col_rating="rating",
        col_prediction="prediction",
        k=2,
    )

    assert p == pytest.approx(0.5, abs=1e-6)
    assert r == pytest.approx(0.5, abs=1e-6)
    assert m == pytest.approx(0.5, abs=1e-6)
    assert n == pytest.approx(0.61314719, abs=1e-6)


def test_tfidf_recommender_on_short_documents():
    """Verify TF-IDF recommender fit and recommendation on 10 documents."""
    docs = [
        {
            "id": f"ai_{i}",
            "text": f"machine learning article number {i} artificial intelligence neural network",
        }
        for i in range(5)
    ] + [
        {
            "id": f"food_{i}",
            "text": f"cooking recipe number {i} tomato pasta Italian cheese delicious pizza",
        }
        for i in range(5)
    ]
    df = pd.DataFrame(docs)

    model = TfidfRecommender(id_col="id", tokenization_method="none")
    df_clean = model.clean_dataframe(df, ["text"], new_col_name="cleaned_text")
    tf, vectors_tokenized = model.tokenize_text(df_clean, text_col="cleaned_text")
    model.fit(tf, vectors_tokenized)

    recs = model.recommend_top_k_items(df_clean, k=3)
    assert recs.shape == (30, 4)
    assert set(recs.columns) == {"id", "rec_rank", "rec_score", "rec_id"}

    # An AI article should have another AI article as top recommendation
    ai_0_recs = recs[recs["id"] == "ai_0"]["rec_id"].tolist()
    assert any(rec_id.startswith("ai_") for rec_id in ai_0_recs)


def test_movielens_loader_parsing_offline(tmp_path):
    """Verify MovieLens parsing logic on small synthetic fixture archive without network."""
    zip_path = tmp_path / "ml-100k.zip"

    # Minimal u.data: user, item, rating, timestamp (tab-separated)
    u_data_content = "1\t101\t5\t874724710\n1\t102\t3\t874724720\n2\t101\t4\t874724730\n"

    # Minimal u.item: movie_id|title (year)|release_date|video_release_date|IMDb_URL|19 genre flags
    # Genre flags: 1 for Action (index 1), 0 for others
    genre_flags = ["0"] * 19
    genre_flags[1] = "1"  # Action
    u_item_line_1 = (
        f"101|Toy Story (1995)|01-Jan-1995||http://imdb.com/toy|{'|'.join(genre_flags)}\n"
    )

    genre_flags_2 = ["0"] * 19
    genre_flags_2[2] = "1"  # Adventure
    u_item_line_2 = (
        f"102|GoldenEye (1995)|01-Jan-1995||http://imdb.com/eye|{'|'.join(genre_flags_2)}\n"
    )

    u_item_content = u_item_line_1 + u_item_line_2

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ml-100k/u.data", u_data_content)
        zf.writestr("ml-100k/u.item", u_item_content)

    # Test load_pandas_df
    df_ratings = load_pandas_df(size="100k", local_cache_path=str(tmp_path))
    assert len(df_ratings) == 3
    assert set(df_ratings.columns) == {"userID", "itemID", "rating", "timestamp"}
    assert df_ratings["userID"].tolist() == [1, 1, 2]

    # Test load_item_df
    df_items = load_item_df(
        size="100k",
        local_cache_path=str(tmp_path),
        title_col="title",
        genres_col="genre",
        year_col="year",
    )
    assert len(df_items) == 2
    assert "title" in df_items.columns
    assert "year" in df_items.columns
    assert "genre" in df_items.columns
    assert df_items.loc[df_items["itemID"] == 101, "year"].iloc[0] == "1995"
    assert "Action" in df_items.loc[df_items["itemID"] == 101, "genre"].iloc[0]
