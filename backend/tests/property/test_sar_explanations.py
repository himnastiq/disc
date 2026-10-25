"""Property tests for faithful SAR explanations (P3.7 / R3 / FIX-13).

Verifies:
- The reason item is always a member of the history (or known user interactions).
- The reason item is the true maximum contributor:
    argmax_{h in H} affinity(h) * sim(h, r)
  computed independently from first principles (sets, intersections, unions),
  not by reading model.sar.user_affinity or model.sar.item_similarity.
- Explanations are only returned when the contribution share exceeds the threshold.
- A 5-star item with lower similarity beats a 4-star item with slightly higher similarity.
- Known user affinities with time-decay weights are faithfully attributed.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.config import load_config
from engine.models.sar import SarModel


def compute_independent_jaccard_similarity(
    interactions: pd.DataFrame,
    catalogue: list[str],
    top_k: int = 50,
) -> dict[tuple[str, str], float]:
    """Compute item-item Jaccard similarity matrix independently from raw interaction sets.

    Calculates:
        J(i, j) = |U_i intersect U_j| / |U_i union U_j|
    with J(i, i) = 0 and top-k sparsification per item row.
    """
    # Build user interaction sets per item
    item_users: dict[str, set[str]] = {item_id: set() for item_id in catalogue}
    for _, row in interactions.iterrows():
        item_id = str(row["item_id"])
        if item_id in item_users:
            item_users[item_id].add(str(row["user_id"]))

    sims: dict[tuple[str, str], float] = {}
    for i in catalogue:
        u_i = item_users[i]
        c_ii = len(u_i)
        candidates: list[tuple[str, float]] = []
        for j in catalogue:
            if i == j:
                continue
            u_j = item_users[j]
            c_jj = len(u_j)
            intersect = len(u_i & u_j)
            denom = c_ii + c_jj - intersect
            jaccard = (intersect / denom) if denom > 0 else 0.0
            if jaccard > 0.0:
                candidates.append((j, jaccard))

        # Top-k sparsification
        candidates.sort(key=lambda x: -x[1])
        top_candidates = candidates[:top_k]
        for j, s in top_candidates:
            sims[(i, j)] = s

    return sims


@pytest.fixture(scope="module")
def fitted_sar_fixture() -> tuple[SarModel, dict[tuple[str, str], float]]:
    """Create a fitted SarModel and precomputed independent ground-truth similarities."""
    catalogue = [f"movie_{i}" for i in range(1, 21)]
    items = pd.DataFrame(
        [{"item_id": m, "title": f"Movie {m}", "categories": ["Action"]} for m in catalogue]
    )

    interactions_list = []
    for u in range(1, 15):
        uid = f"user_{u}"
        for step in range(1, 8):
            item_idx = ((u * 3 + step) % 20) + 1
            interactions_list.append(
                {
                    "user_id": uid,
                    "item_id": f"movie_{item_idx}",
                    "signal": 5.0 if step % 2 == 0 else 3.0,
                    "timestamp": 1000 * u + step * 10,
                    "positive": True,
                }
            )

    interactions = pd.DataFrame(interactions_list)
    spec = load_config("movies", fast=True)
    model = SarModel(spec)
    model.fit(interactions, items)

    independent_sims = compute_independent_jaccard_similarity(
        interactions, catalogue, top_k=spec.serving.top_neighbors_per_item
    )
    return model, independent_sims


@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    history_pairs=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=20),
            st.floats(min_value=1.0, max_value=5.0),
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[0],
    ),
    recommended_idx=st.integers(min_value=1, max_value=20),
    threshold=st.floats(min_value=0.0, max_value=0.5),
)
def test_sar_explanation_properties(
    fitted_sar_fixture: tuple[SarModel, dict[tuple[str, str], float]],
    history_pairs: list[tuple[int, float]],
    recommended_idx: int,
    threshold: float,
) -> None:
    """Hypothesis property test: faithful explanation attribution invariant against independent ground truth."""
    model, independent_sims = fitted_sar_fixture
    rec_item = f"movie_{recommended_idx}"
    history = [(f"movie_{i}", float(sig)) for i, sig in history_pairs]
    history_items = [item_id for item_id, _ in history]

    reason = model.explain(
        recommended_item_id=rec_item,
        history=history,
        min_threshold=threshold,
    )

    # Compute ground truth manual contributions independently from raw sets/formula
    manual_contribs: dict[str, float] = {}
    for h, sig in history:
        if h == rec_item:
            continue
        sim_val = independent_sims.get((h, rec_item), 0.0)
        if sim_val > 0.0 and sig > 0.0:
            manual_contribs[h] = sig * sim_val

    if not manual_contribs:
        # If no history item has positive similarity, reason must be None
        assert reason is None
        return

    best_item = max(manual_contribs.keys(), key=lambda k: manual_contribs[k])
    best_contrib = manual_contribs[best_item]
    total_positive = sum(manual_contribs.values())
    share = (best_contrib / total_positive) if total_positive > 0.0 else 0.0

    if share < threshold:
        # Below threshold must produce None
        assert reason is None
    else:
        # When reason is produced, verify faithfulness
        assert reason is not None
        assert reason.item_id in history_items, (
            f"Reason {reason.item_id} not in history {history_items}"
        )
        assert reason.kind == "similar_item"

        # Verify reason.item_id achieved the maximum independent contribution
        reason_contrib = manual_contribs.get(reason.item_id or "", 0.0)
        assert pytest.approx(reason_contrib, rel=1e-5) == best_contrib, (
            f"Reason item {reason.item_id} contrib {reason_contrib} is not maximum {best_contrib}"
        )


def test_5_star_lower_sim_beats_4_star_higher_sim() -> None:
    """Explicitly verify that a 5-star item with lower similarity beats a 4-star item with higher similarity."""
    # Setup controlled dataset:
    # item_rec: "movie_rec"
    # item_4star: "movie_4star" (sim to rec = 0.60)
    # item_5star: "movie_5star" (sim to rec = 0.50)
    #
    # Rating:
    # 4-star item contrib = 4.0 * 0.60 = 2.40
    # 5-star item contrib = 5.0 * 0.50 = 2.50
    #
    # 2.50 > 2.40 => 5-star item must be chosen as explanation despite lower similarity!
    catalogue = ["movie_rec", "movie_4star", "movie_5star"]
    items = pd.DataFrame([{"item_id": m, "title": m, "categories": ["Drama"]} for m in catalogue])

    interactions_list = []
    # Users 1..6 interact with movie_4star, movie_rec, AND movie_5star
    for u in range(1, 7):
        uid = f"user_{u}"
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_rec",
                "signal": 5.0,
                "timestamp": 100,
                "positive": True,
            }
        )
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_4star",
                "signal": 4.0,
                "timestamp": 100,
                "positive": True,
            }
        )
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_5star",
                "signal": 5.0,
                "timestamp": 100,
                "positive": True,
            }
        )

    # Users 7, 8 interact only with movie_4star (makes total users for 4star = 8)
    for u in range(7, 9):
        uid = f"user_{u}"
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_4star",
                "signal": 4.0,
                "timestamp": 100,
                "positive": True,
            }
        )

    # Users 9, 10 interact only with movie_rec (makes total users for rec = 8)
    for u in range(9, 11):
        uid = f"user_{u}"
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_rec",
                "signal": 5.0,
                "timestamp": 100,
                "positive": True,
            }
        )

    # Users 11..14 (4 users) interact only with movie_5star (makes total users for 5star = 10)
    for u in range(11, 15):
        uid = f"user_{u}"
        interactions_list.append(
            {
                "user_id": uid,
                "item_id": "movie_5star",
                "signal": 5.0,
                "timestamp": 100,
                "positive": True,
            }
        )

    interactions = pd.DataFrame(interactions_list)
    spec = load_config("movies", fast=True)
    model = SarModel(spec)
    model.fit(interactions, items)

    assert model.sar is not None
    idx_rec = model.sar.item2index["movie_rec"]
    idx_4star = model.sar.item2index["movie_4star"]
    idx_5star = model.sar.item2index["movie_5star"]

    sim_4star = float(model.sar.item_similarity[idx_4star, idx_rec])
    sim_5star = float(model.sar.item_similarity[idx_5star, idx_rec])

    # Check similarities:
    # Jaccard(4star, rec) = 6 / (8 + 8 - 6) = 6/10 = 0.60
    # Jaccard(5star, rec) = 6 / (10 + 8 - 6) = 6/12 = 0.50
    assert pytest.approx(sim_4star, rel=1e-4) == 0.60
    assert pytest.approx(sim_5star, rel=1e-4) == 0.50
    assert sim_5star < sim_4star, f"Expected sim_5star ({sim_5star}) < sim_4star ({sim_4star})"

    # Cold start history: 5-star item has signal 5.0, 4-star item has signal 4.0
    history = [("movie_5star", 5.0), ("movie_4star", 4.0)]

    reason = model.explain(
        recommended_item_id="movie_rec",
        history=history,
        min_threshold=0.1,
    )

    assert reason is not None
    assert reason.item_id == "movie_5star", (
        f"Expected 5-star item ('movie_5star') to beat 4-star item ('movie_4star'), got {reason.item_id}"
    )


def test_known_user_time_decay_explanation() -> None:
    """Verify that known user explain uses time-decayed user affinities."""
    catalogue = ["movie_rec", "movie_recent", "movie_old"]
    items = pd.DataFrame([{"item_id": m, "title": m, "categories": ["Action"]} for m in catalogue])

    interactions_list = [
        # Target user: interacted with movie_recent at t=1000, movie_old at t=10
        {
            "user_id": "u_target",
            "item_id": "movie_recent",
            "signal": 5.0,
            "timestamp": 1000,
            "positive": True,
        },
        {
            "user_id": "u_target",
            "item_id": "movie_old",
            "signal": 5.0,
            "timestamp": 10,
            "positive": True,
        },
        # Background co-occurrence users: identical co-occurrence for recent and old with movie_rec
        {
            "user_id": "u_other1",
            "item_id": "movie_rec",
            "signal": 5.0,
            "timestamp": 500,
            "positive": True,
        },
        {
            "user_id": "u_other1",
            "item_id": "movie_recent",
            "signal": 5.0,
            "timestamp": 500,
            "positive": True,
        },
        {
            "user_id": "u_other1",
            "item_id": "movie_old",
            "signal": 5.0,
            "timestamp": 500,
            "positive": True,
        },
    ]

    interactions = pd.DataFrame(interactions_list)
    spec = load_config("movies", fast=True)
    # Enable time decay formula
    spec.model.params["timedecay_formula"] = True
    spec.model.params["time_decay_coefficient"] = 30  # 30 days half life

    model = SarModel(spec)
    model.fit(interactions, items)

    # Explanation for u_target: movie_recent has much higher time-decayed affinity than movie_old
    reason = model.explain(recommended_item_id="movie_rec", user_id="u_target", min_threshold=0.1)
    assert reason is not None
    assert reason.item_id == "movie_recent"
