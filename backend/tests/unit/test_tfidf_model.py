"""Discovery Engine - Unit tests for TfidfProfileModel (P5.4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.config import load_config
from engine.errors import UnknownItem, UnknownUser
from engine.models.tfidf import TfidfProfileModel, clean_article_text


@pytest.fixture
def sample_articles_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Provide realistic articles and interactions DataFrame for testing."""
    items = pd.DataFrame(
        [
            {
                "item_id": "N001",
                "title": "Quantum Computing Breakthrough in Silicon",
                "subtitle": "technology / hardware",
                "categories": ["technology", "computing", "silicon"],
                "text": "Physicists achieve high-fidelity silicon quantum processor.",
                "year": None,
                "image_url": None,
            },
            {
                "item_id": "N002",
                "title": "Superconductor Advance at Room Temperature",
                "subtitle": "science / physics",
                "categories": ["science", "physics", "quantum"],
                "text": "New material exhibits superconductivity under pressure.",
                "year": None,
                "image_url": None,
            },
            {
                "item_id": "N003",
                "title": "Italian Pasta Recipe and Culinary Secrets",
                "subtitle": "lifestyle / food",
                "categories": ["lifestyle", "food", "cooking"],
                "text": "Traditional handmade tagliatelle with classic ragu bolognese.",
                "year": None,
                "image_url": None,
            },
            {
                "item_id": "N004",
                "title": "Gourmet Bread Baking at Home",
                "subtitle": "lifestyle / food",
                "categories": ["lifestyle", "food", "baking"],
                "text": "Mastering natural sourdough fermentation and high hydration loafs.",
                "year": None,
                "image_url": None,
            },
            {
                "item_id": "N005",
                "title": "World Cup Championship Finals Highlights",
                "subtitle": "sports / soccer",
                "categories": ["sports", "soccer"],
                "text": "Dramatic penalty shootout decides the international football title.",
                "year": None,
                "image_url": None,
            },
            {
                "item_id": "N006",
                "title": "Test Article Not In Training Interactions",
                "subtitle": "test / unread",
                "categories": ["test", "rare_unseen_token_xyz"],
                "text": "Article published later that was never clicked during training.",
                "year": None,
                "image_url": None,
            },
        ]
    )

    interactions = pd.DataFrame(
        [
            # User 1 is a tech enthusiast
            {"user_id": "U1", "item_id": "N001", "signal": 1.0, "timestamp": 1000},
            {"user_id": "U1", "item_id": "N002", "signal": 1.0, "timestamp": 2000},
            # User 2 is a food lover
            {"user_id": "U2", "item_id": "N003", "signal": 1.0, "timestamp": 1500},
            {"user_id": "U2", "item_id": "N004", "signal": 1.0, "timestamp": 2500},
            # User 3 has clicked both sports and food
            {"user_id": "U3", "item_id": "N005", "signal": 1.0, "timestamp": 1200},
            {"user_id": "U3", "item_id": "N003", "signal": 1.0, "timestamp": 1800},
        ]
    )
    return items, interactions


def test_clean_article_text() -> None:
    """Verify unicode normalization, punctuation removal, and lowercasing."""
    raw = "<p>Quantum &amp; Silicon—Processor:\t\n100%Â\xa0Valid!</p>"
    cleaned = clean_article_text(raw)
    assert "<p>" not in cleaned
    assert "amp" not in cleaned or "silicon" in cleaned
    assert "quantum" in cleaned
    assert "silicon" in cleaned
    assert "processor" in cleaned
    assert "!" not in cleaned
    assert "Â" not in cleaned


def test_profile_identical_history_equals_article_vector_direction(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Acceptance criterion: profile of identical history equals that article's vector direction."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    assert model.tfidf_matrix is not None
    # Compare profile of N001 with N001's vector
    idx_1 = model.item2index["N001"]
    v1 = model.tfidf_matrix[idx_1, :].toarray().flatten()
    v1_norm = v1 / np.linalg.norm(v1)

    # 1. Single interaction history
    prof_single = model._build_profile_vector([("N001", 1.0)])
    assert prof_single is not None
    u_single = prof_single.toarray().flatten()

    # Cosine similarity must be exactly 1.0 (collinear)
    cosine_sim_single = float(np.dot(u_single, v1_norm))
    assert pytest.approx(1.0, rel=1e-5) == cosine_sim_single

    # 2. Repeated identical history with varying signals
    prof_repeated = model._build_profile_vector([("N001", 1.0), ("N001", 3.5)])
    assert prof_repeated is not None
    u_repeated = prof_repeated.toarray().flatten()

    cosine_sim_repeated = float(np.dot(u_repeated, v1_norm))
    assert pytest.approx(1.0, rel=1e-5) == cosine_sim_repeated


def test_empty_history_gives_popularity(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Acceptance criterion: empty history returns global popularity."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    pop_recs = model.popular(k=4)
    hist_recs = model.recommend_history([], k=4)

    assert len(hist_recs) == 4
    assert [r.item_id for r in hist_recs] == [p.item_id for p in pop_recs]
    assert [r.score for r in hist_recs] == [p.score for p in pop_recs]
    assert [r.rank for r in hist_recs] == [p.rank for p in pop_recs]


def test_vocabulary_fitted_on_train_period_only(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify R2 representation leakage: vocabulary is fitted only on train articles."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    assert model.vectorizer is not None
    # N006 was not in interactions; its unique token must NOT appear in vocabulary
    assert "rare_unseen_token_xyz" not in model.vectorizer.vocabulary_


def test_unknown_user_raises(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """recommend_user must raise UnknownUser for unknown user IDs."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    with pytest.raises(UnknownUser) as exc:
        model.recommend_user("UNKNOWN_USER_404", k=5)
    assert exc.value.user_id == "UNKNOWN_USER_404"
    assert exc.value.content_type == "articles"


def test_unknown_item_in_similar_items_raises(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """similar_items must raise UnknownItem for items not in catalogue."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    with pytest.raises(UnknownItem) as exc:
        model.similar_items("MISSING_ITEM", k=3)
    assert exc.value.item_id == "MISSING_ITEM"
    assert exc.value.content_type == "articles"


def test_similar_items_never_returns_query_item(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """similar_items must never include the target item itself."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    recs = model.similar_items("N001", k=5)
    assert all(r.item_id != "N001" for r in recs)
    # The most similar article to quantum computing should be superconductor physics
    assert recs[0].item_id == "N002"


def test_seen_items_excluded_by_default(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Seen items in train interactions must be excluded when allow_repeat is False."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    spec.model.allow_repeat = False
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    recs = model.recommend_user("U1", k=5)
    seen = model.user_seen["U1"]
    assert "N001" in seen
    assert "N002" in seen
    assert all(r.item_id not in seen for r in recs)


def test_scores_are_monotonic(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Recommended items must have non-increasing scores."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    recs = model.recommend_user("U1", k=5)
    scores = [r.score for r in recs]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_explain_identifies_top_contributor(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Faithful explanation attributes recommendation to the highest similarity history article."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    # History with both a tech article (N001) and food article (N003)
    history = [("N001", 1.0), ("N003", 1.0)]
    # Superconductor article N002 should be explained by quantum computing N001
    reason = model.explain("N002", history=history, min_threshold=0.1)
    assert reason is not None
    assert reason.item_id == "N001"
    assert "Quantum Computing" in reason.text or "N001" in reason.text


def test_save_and_load_roundtrip(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Model must save and load without pickle, producing identical scores."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    save_dir = tmp_path / "tfidf_model"
    save_dir.mkdir(parents=True, exist_ok=True)
    model.save(save_dir)

    # Check that required files exist
    assert (save_dir / "tfidf_matrix.npz").exists()
    assert (save_dir / "vocabulary.json").exists()
    assert (save_dir / "idf.npy").exists()
    assert (save_dir / "item_ids.json").exists()
    assert (save_dir / "model_meta.json").exists()

    loaded_model = TfidfProfileModel(spec)
    loaded_model.load(save_dir)

    # Verify identical recommendations for known user
    orig_user_recs = model.recommend_user("U1", k=4)
    loaded_user_recs = loaded_model.recommend_user("U1", k=4)
    assert [r.item_id for r in orig_user_recs] == [r.item_id for r in loaded_user_recs]
    for r1, r2 in zip(orig_user_recs, loaded_user_recs, strict=True):
        assert pytest.approx(r1.score, rel=1e-5) == r2.score

    # Verify identical cold-start recommendations
    hist = [("N004", 1.0)]
    orig_hist_recs = model.recommend_history(hist, k=3)
    loaded_hist_recs = loaded_model.recommend_history(hist, k=3)
    assert [r.item_id for r in orig_hist_recs] == [r.item_id for r in loaded_hist_recs]
    for r1, r2 in zip(orig_hist_recs, loaded_hist_recs, strict=True):
        assert pytest.approx(r1.score, rel=1e-5) == r2.score


def test_recency_window_restricts_candidates(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Acceptance criterion: recommendations never include articles outside the recency window."""
    items, _ = sample_articles_data
    # Interactions with old clicks (timestamp 1000) and recent clicks (timestamp 200,000)
    timed_interactions = pd.DataFrame(
        [
            # Old period clicks (e.g. Day 1, ~2 days ago)
            {"user_id": "U1", "item_id": "N001", "signal": 1.0, "timestamp": 1000},
            {"user_id": "U1", "item_id": "N002", "signal": 1.0, "timestamp": 2000},
            # Recent period clicks (Day 3, within last 86,400s)
            {"user_id": "U2", "item_id": "N003", "signal": 1.0, "timestamp": 190000},
            {"user_id": "U2", "item_id": "N004", "signal": 1.0, "timestamp": 195000},
            {"user_id": "U3", "item_id": "N005", "signal": 1.0, "timestamp": 200000},
        ]
    )
    spec = load_config("articles", fast=True)
    spec.serving.recency_window = 86400  # 1 day window
    model = TfidfProfileModel(spec)
    model.fit(timed_interactions, items)

    assert model.fresh_candidates is not None
    # Maximum timestamp is 200,000. Cutoff is 200,000 - 86,400 = 113,600.
    # N001 and N002 (timestamps 1000, 2000) are outside the window.
    # N003, N004, N005 (timestamps >= 190,000) are inside the window.
    assert model.fresh_candidates == {"N003", "N004", "N005"}
    assert "N001" not in model.fresh_candidates
    assert "N002" not in model.fresh_candidates

    # Invariant: recommendations must never include articles outside the window!
    # 1. User recommendations for U1 (who only liked old tech articles)
    user_recs = model.recommend_user("U1", k=5)
    assert len(user_recs) > 0
    assert all(r.item_id in model.fresh_candidates for r in user_recs)

    # 2. Cold-start recommendations
    cold_recs = model.recommend_history([("N001", 1.0)], k=5)
    assert len(cold_recs) > 0
    assert all(r.item_id in model.fresh_candidates for r in cold_recs)

    # 3. Popular recommendations
    pop_recs = model.popular(k=5)
    assert len(pop_recs) > 0
    assert all(r.item_id in model.fresh_candidates for r in pop_recs)

    # 4. Similar items for an old article
    sim_recs = model.similar_items("N001", k=5)
    assert len(sim_recs) > 0
    assert all(r.item_id in model.fresh_candidates for r in sim_recs)


def test_set_fresh_candidates_explicitly(
    sample_articles_data: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Explicitly setting fresh candidates pool enforces candidate isolation."""
    items, interactions = sample_articles_data
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    model.fit(interactions, items)

    # Restrict candidate pool to only N004 and N005
    model.set_fresh_candidates({"N004", "N005"})

    recs_user = model.recommend_user("U1", k=5)
    assert all(r.item_id in {"N004", "N005"} for r in recs_user)

    recs_pop = model.popular(k=5)
    assert all(r.item_id in {"N004", "N005"} for r in recs_pop)

    recs_sim = model.similar_items("N003", k=5)
    assert all(r.item_id in {"N004", "N005"} for r in recs_sim)


def test_tfidf_model_score_candidates_unfitted_raises_runtime_error() -> None:
    """F-020: TF-IDF _score_candidates must raise RuntimeError when unfitted."""
    spec = load_config("articles", fast=True)
    model = TfidfProfileModel(spec)
    with pytest.raises(RuntimeError, match=r"TF-IDF model has not been fitted"):
        model._score_candidates(profile=None, k=5, exclusions=set())
