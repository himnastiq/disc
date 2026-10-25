"""Unit tests for demo user selection and diversity criteria (P3.11)."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.demo_users import compute_pairwise_jaccard, select_demo_users_from_dfs


@pytest.fixture
def demo_users_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create synthetic users_df and topn_df DataFrames across personas."""
    users_rows = []
    topn_rows = []

    personas = ["heavy", "mainstream", "niche", "casual"]
    for i in range(1, 21):
        uid = f"user_{i}"
        persona = personas[(i - 1) % len(personas)]
        users_rows.append(
            {
                "user_id": uid,
                "interaction_count": 100
                if persona == "heavy"
                else (10 if persona == "casual" else 30),
                "top_categories": ["Action", "Sci-Fi"] if i % 2 == 0 else ["Drama", "Romance"],
                "first_timestamp": 1000,
                "last_timestamp": 2000,
                "persona": persona,
            }
        )

        # Generate distinct top-10 items per user
        for rank in range(1, 11):
            item_id = f"item_{(i * 5 + rank) % 100}"
            topn_rows.append(
                {
                    "user_id": uid,
                    "item_id": item_id,
                    "score": 10.0 - rank * 0.5,
                    "rank": rank,
                }
            )

    return pd.DataFrame(users_rows), pd.DataFrame(topn_rows)


def test_select_demo_users_diversity_and_schema(
    demo_users_fixture: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify demo users selection yields diverse users with pairwise Jaccard below threshold."""
    users_df, topn_df = demo_users_fixture

    demo_users = select_demo_users_from_dfs(
        users_df=users_df,
        topn_df=topn_df,
        seed=42,
        target_count=8,
        max_pairwise_jaccard=0.5,
    )

    assert len(demo_users) == 8, f"Expected 8 demo users, got {len(demo_users)}"

    # Check fields
    represented_personas = set()
    for u in demo_users:
        assert "user_id" in u
        assert "persona" in u
        assert "interaction_count" in u
        assert "top_categories" in u
        represented_personas.add(u["persona"])

    # Multiple personas must be represented
    assert len(represented_personas) >= 3

    # Check pairwise Jaccard of top-10 lists
    user_top10 = {}
    for uid, group in topn_df.groupby("user_id"):
        user_top10[str(uid)] = set(group.sort_values(by="rank").head(10)["item_id"].astype(str))

    demo_uids = [u["user_id"] for u in demo_users]
    for i in range(len(demo_uids)):
        for j in range(i + 1, len(demo_uids)):
            u1, u2 = demo_uids[i], demo_uids[j]
            jaccard = compute_pairwise_jaccard(user_top10[u1], user_top10[u2])
            assert jaccard <= 0.5, f"Pairwise Jaccard between {u1} and {u2} exceeded 0.5: {jaccard}"
