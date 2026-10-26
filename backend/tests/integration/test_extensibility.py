"""Discovery Engine - Extensibility Proof (P6.2).

Proves that Discovery Engine is truly adaptive and extensible across arbitrary
content domains without modifying any core engine abstractions or API code:
1. Executes the synthetic `toy` pipeline end-to-end (training, artifact export, evaluation).
2. Dynamically registers an entirely external 4th/5th content type (`podcasts`) defined
   strictly within the test suite with its own YAML configuration.
3. Fits models, evaluates cold-start attribution, and serves recommendations asserting
   all R3 invariants (monotonic non-increasing scores, catalogue compliance, seen exclusion).
4. Asserts that tools/core_unchanged.py confirms zero engine core modifications.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from engine.adapters.base import DatasetAdapter
from engine.artifacts import load_artifacts
from engine.config import load_config
from engine.evaluation.checks import check_r3_model_invariants
from engine.evaluation.harness import EvaluationHarness
from engine.evaluation.splits import split_interactions
from engine.registry import build_model, get_adapter, register_adapter
from engine.schema import ValidationReport
from engine.train import run_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# =========================================================================
# Part 1: Verify built-in synthetic 'toy' pipeline extensibility
# =========================================================================


@pytest.mark.integration
def test_toy_pipeline_end_to_end(tmp_path: Path) -> None:
    """Verify that synthetic 'toy' type trains and produces valid artifacts."""
    metrics = run_pipeline(
        content_type="toy",
        fast=True,
        artifacts_dir=tmp_path,
        seed=42,
    )

    # 1. Assert required evaluation metrics structure
    assert "models" in metrics
    assert "popularity" in metrics["models"]
    assert "random" in metrics["models"]
    assert "cold_start_curves" in metrics

    # 2. Assert all 8 standard artifacts exist on disk
    loaded = load_artifacts(tmp_path, verify=True)
    assert len(loaded.items) == 25
    assert len(loaded.interactions) == 180
    assert len(loaded.users) == 15
    assert loaded.topn is not None and len(loaded.topn) > 0
    assert loaded.manifest is not None
    assert "files" in loaded.manifest
    assert len(loaded.manifest["files"]) > 0

    # 3. Load trained model and assert R3 invariants on recommendations
    spec = load_config("toy", fast=True)
    model = build_model(spec)
    model.load(tmp_path / "model")

    for user_id in ["toy_user_1", "toy_user_2"]:
        recs = model.recommend_user(user_id=user_id, k=5)
        check_r3_model_invariants(recs, k=5, catalogue=model.catalogue)

        # Assert previously seen items are never recommended
        seen = model.user_seen.get(user_id, set())
        for r in recs:
            assert r.item_id not in seen


# =========================================================================
# Part 2: Dynamically registered test-only adapter (e.g. 'podcasts')
# =========================================================================


@register_adapter("podcasts_test_extensibility")
class PodcastExtensibleAdapter(DatasetAdapter):
    """External podcast domain adapter declared solely within test scope."""

    def download(self, raw_dir: Path) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)

    def load_raw(self, raw_dir: Path) -> dict[str, str]:
        return {"status": "ok"}

    def items(self) -> pd.DataFrame:
        """Podcast episodes catalogue."""
        episodes = []
        for i in range(1, 21):
            episodes.append(
                {
                    "item_id": f"POD_{i}",
                    "title": f"Episode {i}: Tech Explorations",
                    "subtitle": "Engineering Daily",
                    "categories": ["Technology", "Software" if i % 2 == 0 else "AI"],
                    "text": f"Detailed transcript for podcast episode {i}.",
                    "year": 2024,
                    "image_url": f"https://example.com/podcasts/{i}.png",
                    "extra": {"duration_minutes": 30 + i},
                }
            )
        return pd.DataFrame(episodes)

    def interactions(self) -> pd.DataFrame:
        """Podcast listen interactions."""
        rows = []
        # 10 listeners, each listens to 6 episodes with completion rates (signal 1.0 to 5.0)
        for u in range(1, 11):
            user_id = f"LISTENER_{u}"
            for i in range(1, 7):
                item_idx = ((u + i - 2) % 20) + 1
                rows.append(
                    {
                        "user_id": user_id,
                        "item_id": f"POD_{item_idx}",
                        "signal": float(min(5, max(1, (i % 5) + 1))),
                        "timestamp": 1700000000 + (u * 1000) + (i * 60),
                    }
                )
        return pd.DataFrame(rows)

    def validate(self, interactions_df: pd.DataFrame | None = None) -> ValidationReport:
        inter = self.interactions() if interactions_df is None else interactions_df
        return ValidationReport(
            total_interactions=len(inter),
            unique_users=inter["user_id"].nunique(),
            unique_items=inter["item_id"].nunique(),
            sparsity=0.70,
            min_timestamp=int(inter["timestamp"].min()),
            max_timestamp=int(inter["timestamp"].max()),
        )

    def split(
        self, interactions_df: pd.DataFrame | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        inter = self.interactions() if interactions_df is None else interactions_df
        r = float(self.spec.split.ratio)
        ratios = (r, (1.0 - r) / 2.0, (1.0 - r) / 2.0)
        return split_interactions(
            inter,
            strategy=self.spec.split.strategy,
            ratios=ratios,
        )


@pytest.mark.integration
def test_dynamic_domain_registration_without_engine_modifications(tmp_path: Path) -> None:
    """Register, configure, train, and evaluate a new domain purely from external test code."""
    # 1. Define custom domain config in YAML
    podcast_yaml = tmp_path / "podcasts_test.yaml"
    podcast_yaml.write_text(
        """
type: podcasts_test_extensibility
display_name: Podcasts Extensibility Test
card_type: product
dataset:
  adapter: podcasts_test_extensibility
  variant: "default"
  min_user_interactions: 2
  min_item_interactions: 1
signal:
  positive_threshold: 3.0
  use_rating_as_weight: true
split:
  strategy: chronological
  ratio: 0.8
  seed: 42
model:
  name: popularity
  params: {}
  allow_repeat: false
  supports_cold_start: true
evaluation:
  k: [5, 10]
  cold_start_history_sizes: [0, 1, 3]
  baselines: [popularity, random]
serving:
  top_neighbors_per_item: 10
  max_items_in_similarity: 50
""",
        encoding="utf-8",
    )

    # 2. Parse ContentTypeSpec directly from test YAML
    spec = load_config(podcast_yaml)
    assert spec.type == "podcasts_test_extensibility"
    assert spec.card_type == "product"

    # 3. Retrieve registered adapter and execute data partition
    adapter = get_adapter(spec)
    assert isinstance(adapter, PodcastExtensibleAdapter)
    report = adapter.validate()
    assert report.total_interactions == 60
    assert report.unique_users == 10

    inter_df = adapter.interactions()
    items_df = adapter.items()
    train_df, valid_df, test_df = adapter.split(inter_df)

    # 4. Fit model and serve recommendations asserting R3 invariants
    model = build_model(spec)
    model.fit(train_df, items_df)

    recs = model.recommend_user("LISTENER_1", k=5)
    assert len(recs) == 5
    check_r3_model_invariants(recs, k=5, catalogue=model.catalogue)

    # Cold-start recommendations
    cold_recs = model.recommend_history([("POD_1", 5.0), ("POD_2", 4.0)], k=5)
    assert len(cold_recs) == 5
    check_r3_model_invariants(cold_recs, k=5, catalogue=model.catalogue)

    # 5. Run full EvaluationHarness on dynamic domain
    harness = EvaluationHarness(spec)
    metrics = harness.run(
        interactions=inter_df,
        items=items_df,
        output_path=tmp_path / "metrics.json",
        max_test_users=10,
        cold_start_sample_users=5,
        split_data=(train_df, valid_df, test_df),
    )
    assert "models" in metrics
    assert "popularity" in metrics["models"]
    assert "random" in metrics["models"]
    assert (tmp_path / "metrics.json").exists()


@pytest.mark.integration
def test_extensibility_invariance_core_unchanged() -> None:
    """Verify that tools/core_unchanged.py confirms zero engine core modifications."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from core_unchanged import GitHistoryUnavailable, check_core_unchanged

    try:
        passed, disallowed, core_violations = check_core_unchanged()
    except GitHistoryUnavailable as exc:
        pytest.skip(str(exc))

    assert passed, (
        f"Extensibility invariant violated: disallowed={disallowed}, violations={core_violations}"
    )
    assert disallowed == []
