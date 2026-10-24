"""Property tests for faithful SAR explanations (P3.7 / R3).

Verifies with Hypothesis:
- The reason item is always a member of the history.
- The reason item is the true maximum contributor:
    argmax_{h in H} affinity(h) * sim(h, r)
- Explanations are only returned when the contribution share exceeds the threshold.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.config import load_config
from engine.models.sar import SarModel


@pytest.fixture(scope="module")
def fitted_sar_fixture() -> SarModel:
    """Create a fitted SarModel instance with small diverse catalogue."""
    items = pd.DataFrame(
        [
            {"item_id": f"movie_{i}", "title": f"Movie {i}", "categories": ["Action"]}
            for i in range(1, 21)
        ]
    )

    interactions_list = []
    for u in range(1, 10):
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
    return model


@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    history_indices=st.lists(
        st.integers(min_value=1, max_value=20), min_size=1, max_size=10, unique=True
    ),
    recommended_idx=st.integers(min_value=1, max_value=20),
    threshold=st.floats(min_value=0.0, max_value=0.5),
)
def test_sar_explanation_properties(
    fitted_sar_fixture: SarModel,
    history_indices: list[int],
    recommended_idx: int,
    threshold: float,
) -> None:
    """Hypothesis property test for faithful SAR explanation invariants."""
    model = fitted_sar_fixture
    assert model.sar is not None
    history_items = [f"movie_{i}" for i in history_indices]
    rec_item = f"movie_{recommended_idx}"

    reason = model.explain(
        history_item_ids=history_items,
        recommended_item_id=rec_item,
        min_threshold=threshold,
    )

    # Compute ground truth manual contributions
    rec_idx = model.sar.item2index[rec_item]
    manual_contribs: dict[str, float] = {}

    for h in history_items:
        h_idx = model.sar.item2index[h]
        sim_val = float(model.sar.item_similarity[h_idx, rec_idx])
        if sim_val > 0.0:
            manual_contribs[h] = sim_val

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

        # Verify reason.item_id achieved the maximum contribution
        reason_sim = manual_contribs.get(reason.item_id or "", 0.0)
        assert pytest.approx(reason_sim, rel=1e-5) == best_contrib, (
            f"Reason item {reason.item_id} contrib {reason_sim} is not maximum {best_contrib}"
        )
