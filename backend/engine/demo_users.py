"""Discovery Engine - Demo users selection and diversity criteria (P3.11).

Selects diverse demo users across distinct personas (heavy, mainstream, niche, casual)
ensuring that their precomputed top-10 recommendations have pairwise Jaccard similarity
strictly below the configured threshold.
"""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING, Any

import pandas as pd

from engine.artifacts import as_str_list

if TYPE_CHECKING:
    from pathlib import Path


def compute_pairwise_jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two item sets."""
    intersect = len(set_a & set_b)
    union = len(set_a | set_b)
    return (intersect / union) if union > 0 else 0.0


def select_demo_users_from_dfs(
    users_df: pd.DataFrame,
    topn_df: pd.DataFrame,
    seed: int = 42,
    target_count: int = 8,
    max_pairwise_jaccard: float = 0.5,
) -> list[dict[str, Any]]:
    """Select ~8 demo users directly from in-memory users and top-N DataFrames."""
    user_top10: dict[str, set[str]] = {}
    for uid, group in topn_df.groupby("user_id"):
        user_top10[str(uid)] = set(group.sort_values(by="rank").head(10)["item_id"].astype(str))

    valid_users_df = users_df[users_df["user_id"].astype(str).isin(user_top10.keys())].copy()

    rng = random.Random(seed)
    personas = ["heavy", "mainstream", "niche", "casual"]

    selected_users: list[dict[str, Any]] = []
    selected_recs: list[set[str]] = []

    # First pass: try to pick up to 2 users per persona meeting diversity constraint
    for persona in personas:
        matching = valid_users_df[valid_users_df["persona"] == persona]
        candidate_ids = list(matching["user_id"])
        rng.shuffle(candidate_ids)

        picked_for_persona = 0
        for uid in candidate_ids:
            recs = user_top10[uid]
            if all(
                compute_pairwise_jaccard(recs, existing) <= max_pairwise_jaccard
                for existing in selected_recs
            ):
                row = matching[matching["user_id"] == uid].iloc[0]
                top_cats = as_str_list(row.get("top_categories"))
                selected_users.append(
                    {
                        "user_id": str(uid),
                        "persona": persona,
                        "interaction_count": int(row["interaction_count"]),
                        "top_categories": top_cats,
                    }
                )
                selected_recs.append(recs)
                picked_for_persona += 1
                if picked_for_persona >= 2:
                    break

    # Second pass: fill remaining slots up to target_count
    all_candidates = list(valid_users_df["user_id"])
    rng.shuffle(all_candidates)
    for uid in all_candidates:
        if len(selected_users) >= target_count:
            break
        if any(u["user_id"] == str(uid) for u in selected_users):
            continue
        recs = user_top10[uid]
        if all(
            compute_pairwise_jaccard(recs, existing) <= max_pairwise_jaccard
            for existing in selected_recs
        ):
            row = valid_users_df[valid_users_df["user_id"] == uid].iloc[0]
            top_cats = as_str_list(row.get("top_categories"))
            selected_users.append(
                {
                    "user_id": str(uid),
                    "persona": str(row["persona"]),
                    "interaction_count": int(row["interaction_count"]),
                    "top_categories": top_cats,
                }
            )
            selected_recs.append(recs)

    # Fallback if strict threshold produced fewer than 4 users
    if len(selected_users) < 4:
        for uid in all_candidates:
            if len(selected_users) >= target_count:
                break
            if any(u["user_id"] == str(uid) for u in selected_users):
                continue
            row = valid_users_df[valid_users_df["user_id"] == uid].iloc[0]
            top_cats = as_str_list(row.get("top_categories"))
            selected_users.append(
                {
                    "user_id": str(uid),
                    "persona": str(row["persona"]),
                    "interaction_count": int(row["interaction_count"]),
                    "top_categories": top_cats,
                }
            )

    return selected_users


def select_demo_users(
    content_type: str = "default",
    artifacts_dir: Path | None = None,
    seed: int = 42,
    target_count: int = 8,
    max_pairwise_jaccard: float = 0.5,
) -> list[dict[str, Any]]:
    """Select ~8 demo users with diverse tastes and verified pairwise Jaccard < threshold.

    Args:
        content_type: Content type identifier (e.g. 'default').
        artifacts_dir: Path to content type artifacts directory.
        seed: Random seed for deterministic selection.
        target_count: Target number of demo users (default 8).
        max_pairwise_jaccard: Maximum allowed pairwise Jaccard similarity between recommendations.

    Returns:
        list[dict[str, Any]]: List of selected demo user records with personas and interaction counts.
    """
    from pathlib import Path

    target_dir = artifacts_dir or (
        Path(__file__).resolve().parent.parent.parent / "artifacts" / content_type
    )

    users_path = target_dir / "users.parquet"
    topn_path = target_dir / "topn.parquet"

    if not users_path.exists() or not topn_path.exists():
        raise FileNotFoundError(f"Missing required parquet artifacts in {target_dir}")

    users_df = pd.read_parquet(users_path)
    topn_df = pd.read_parquet(topn_path)

    selected_users = select_demo_users_from_dfs(
        users_df=users_df,
        topn_df=topn_df,
        seed=seed,
        target_count=target_count,
        max_pairwise_jaccard=max_pairwise_jaccard,
    )

    out_path = target_dir / "demo_users.json"
    out_path.write_text(json.dumps(selected_users, indent=2), encoding="utf-8")

    manifest_path = target_dir / "manifest.json"
    if manifest_path.exists():
        from engine.artifacts import compute_file_sha256

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "files" in manifest_data:
            manifest_data["files"]["demo_users.json"] = compute_file_sha256(out_path)
            manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return selected_users
