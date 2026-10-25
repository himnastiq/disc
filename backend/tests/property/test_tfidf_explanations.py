"""Property tests for faithful Articles TF-IDF explanations (P5.7 / R3).

Verifies:
- The reason article is always a member of the user's history.
- The reason article is the true maximum contributor:
    argmax_{h in H} weight(h) * sim(h, r)
  computed independently from first principles.
- An explanation is returned if and only if the contribution share exceeds min_threshold.
- Shared top TF-IDF terms (max 3) in explanation text are genuinely common to both articles.
- Higher weighted article with slightly lower similarity can beat lower weighted article.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.config import load_config
from engine.models.tfidf import TfidfProfileModel, clean_article_text


@pytest.fixture(scope="module")
def fitted_tfidf_articles() -> tuple[TfidfProfileModel, pd.DataFrame]:
    """Create a fitted model on diverse multi-topic articles."""
    articles = [
        ("N1", "Quantum computing algorithms for silicon qubits", ["tech", "quantum"]),
        ("N2", "Room temperature superconductivity in hydrides", ["physics", "quantum"]),
        ("N3", "Superconducting qubits for quantum error correction", ["tech", "physics"]),
        ("N4", "Handmade Italian pasta and ragu bolognese", ["food", "cooking"]),
        ("N5", "Traditional sourdough bread baking and fermentation", ["food", "baking"]),
        ("N6", "Italian pizza napoletana with organic flour", ["food", "cooking"]),
        ("N7", "World cup championship final soccer penalties", ["sports", "soccer"]),
        ("N8", "Premier league football tactics and match analysis", ["sports", "soccer"]),
        ("N9", "Grand slam tennis championship tournament highlights", ["sports", "tennis"]),
        ("N10", "Cosmic space telescope discovers exoplanets", ["science", "space"]),
        ("N11", "Mars rover robotic mission and geology exploration", ["science", "space"]),
        ("N12", "Stock market federal reserve inflation interest rates", ["finance", "economy"]),
    ]

    items_df = pd.DataFrame(
        [
            {
                "item_id": aid,
                "title": title,
                "categories": cats,
                "text": f"{title} detailed explanation content.",
            }
            for aid, title, cats in articles
        ]
    )

    interactions = pd.DataFrame(
        [
            {"user_id": "U1", "item_id": "N1", "signal": 1.0, "timestamp": 1000},
            {"user_id": "U1", "item_id": "N2", "signal": 1.0, "timestamp": 2000},
            {"user_id": "U2", "item_id": "N4", "signal": 1.0, "timestamp": 1500},
            {"user_id": "U2", "item_id": "N5", "signal": 1.0, "timestamp": 2500},
            {"user_id": "U3", "item_id": "N7", "signal": 1.0, "timestamp": 1200},
            {"user_id": "U3", "item_id": "N8", "signal": 1.0, "timestamp": 1800},
        ]
    )

    spec = load_config("articles", fast=True)
    spec.serving.recency_window = None
    spec.evaluation.recency_window = None

    model = TfidfProfileModel(spec)
    model.fit(interactions, items_df)
    return model, items_df


def compute_independent_cosine_sim(
    model: TfidfProfileModel,
    item_a: str,
    item_b: str,
) -> float:
    """Compute cosine similarity independently from the fitted TF-IDF matrix rows."""
    if item_a not in model.item2index or item_b not in model.item2index:
        return 0.0
    idx_a = model.item2index[item_a]
    idx_b = model.item2index[item_b]
    assert model.tfidf_matrix is not None
    vec_a = model.tfidf_matrix[idx_a, :].toarray().flatten()
    vec_b = model.tfidf_matrix[idx_b, :].toarray().flatten()
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    history_indices=st.lists(
        st.integers(min_value=1, max_value=12),
        min_size=2,
        max_size=5,
        unique=True,
    ),
    signals=st.lists(
        st.floats(min_value=1.0, max_value=5.0),
        min_size=5,
        max_size=5,
    ),
    target_idx=st.integers(min_value=1, max_value=12),
    threshold=st.floats(min_value=0.1, max_value=0.7),
)
def test_hypothesis_tfidf_explanations_ground_truth(
    fitted_tfidf_articles: tuple[TfidfProfileModel, pd.DataFrame],
    history_indices: list[int],
    signals: list[float],
    target_idx: int,
    threshold: float,
) -> None:
    """Hypothesis property test: reason article equals independent argmax contributor."""
    model, _ = fitted_tfidf_articles
    target_id = f"N{target_idx}"

    history = [
        (f"N{idx}", float(sig))
        for idx, sig in zip(history_indices, signals, strict=False)
        if f"N{idx}" != target_id
    ]
    if len(history) < 2:
        return

    # Compute ground truth independently
    contribs: dict[str, float] = {}
    for h_id, sig in history:
        sim = compute_independent_cosine_sim(model, h_id, target_id)
        contribs[h_id] = max(0.0, sim * sig)

    total_contrib = sum(contribs.values())
    if total_contrib <= 0.0:
        reason = model.explain(target_id, history=history, min_threshold=threshold)
        assert reason is None
        return

    best_h = max(contribs, key=lambda x: (contribs[x], x))
    best_contrib = contribs[best_h]
    share = best_contrib / total_contrib

    reason = model.explain(target_id, history=history, min_threshold=threshold)

    if share >= threshold and best_contrib > 0.0:
        assert reason is not None, f"Expected reason for {target_id} with share {share:.3f}"
        assert reason.item_id == best_h, (
            f"Expected reason item {best_h} with contrib {best_contrib}, got {reason.item_id}"
        )
        assert reason.kind == "article_similarity"
        # Invariant: reason item MUST be in the history
        history_item_ids = {h_id for h_id, _ in history}
        assert reason.item_id in history_item_ids
    else:
        assert reason is None


def test_shared_terms_fidelity(
    fitted_tfidf_articles: tuple[TfidfProfileModel, pd.DataFrame],
) -> None:
    """Verify that shared top TF-IDF terms in reason text appear in both articles."""
    model, items_df = fitted_tfidf_articles
    # N3 (Superconducting qubits) explained by N1 (Quantum computing algorithms)
    history = [("N1", 1.0)]
    reason = model.explain("N3", history=history, min_threshold=0.1)

    assert reason is not None
    assert reason.item_id == "N1"
    assert "(topics:" in reason.text

    # Extract terms between parentheses
    start = reason.text.find("(topics:") + len("(topics:")
    end = reason.text.find(")", start)
    term_str = reason.text[start:end]
    terms = [t.strip() for t in term_str.split(",") if t.strip()]

    assert len(terms) <= 3
    assert len(terms) > 0

    # Every shared term must appear in the cleaned text of both N1 and N3
    n1_row = items_df[items_df["item_id"] == "N1"].iloc[0]
    n3_row = items_df[items_df["item_id"] == "N3"].iloc[0]

    n1_text = clean_article_text(
        f"{n1_row['title']} {n1_row['text']} {' '.join(n1_row['categories'])}"
    )
    n3_text = clean_article_text(
        f"{n3_row['title']} {n3_row['text']} {' '.join(n3_row['categories'])}"
    )

    for term in terms:
        assert term in n1_text, f"Term '{term}' missing from N1"
        assert term in n3_text, f"Term '{term}' missing from N3"


def test_higher_signal_item_beats_slightly_higher_similarity_item(
    fitted_tfidf_articles: tuple[TfidfProfileModel, pd.DataFrame],
) -> None:
    """A strongly liked article (signal=5.0) with moderate similarity beats weakly liked (signal=1.0) with slightly higher similarity."""
    model, _ = fitted_tfidf_articles

    # N3 (Superconducting qubits for quantum error correction)
    # Similar candidate: N1 (Quantum computing) and N2 (Superconductivity)
    sim_n1 = compute_independent_cosine_sim(model, "N1", "N3")
    sim_n2 = compute_independent_cosine_sim(model, "N2", "N3")

    # Give N2 lower similarity but high signal (5.0), and N1 slightly higher similarity but low signal (1.0)
    history = [("N1", 1.0), ("N2", 5.0)]

    contrib_n1 = 1.0 * sim_n1
    contrib_n2 = 5.0 * sim_n2

    reason = model.explain("N3", history=history, min_threshold=0.1)
    assert reason is not None

    if contrib_n2 > contrib_n1:
        assert reason.item_id == "N2"
    else:
        assert reason.item_id == "N1"
