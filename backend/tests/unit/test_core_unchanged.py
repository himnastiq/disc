"""Unit tests for tools/core_unchanged.py (P4.7).

Verifies that the core unchanged check properly identifies core engine files,
permits domain extensions (adapters, configs, tests, docs, tools), and asserts
that real Phase 4 git history contains zero core engine changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from core_unchanged import (  # noqa: E402
    check_core_unchanged,
    is_allowed_path,
    is_core_engine_file,
)


def test_path_classification() -> None:
    """Verify that domain extension paths are allowed and engine files are flagged."""
    # Allowed domain extensions
    assert is_allowed_path("backend/engine/adapters/amazon.py")
    assert is_allowed_path("backend/engine/adapters/mind.py")
    assert is_allowed_path("backend/engine/configs/products.yaml")
    assert is_allowed_path("backend/engine/configs/articles.yaml")
    assert is_allowed_path("backend/tests/unit/test_amazon_adapter.py")
    assert is_allowed_path("docs/DATASETS.md")
    assert is_allowed_path("docs/DECISIONS.md")
    assert is_allowed_path("tools/product_checks.py")
    assert is_allowed_path("backend/scripts/fetch_data.py")
    assert is_allowed_path("IMPLEMENTATION_PLAN.md")

    # Exempt from core engine violations
    assert not is_core_engine_file("backend/engine/adapters/amazon.py")
    assert not is_core_engine_file("backend/engine/configs/products.yaml")
    assert not is_core_engine_file("backend/tests/unit/test_sar.py")

    # Core engine files that MUST trigger core violation
    assert is_core_engine_file("backend/engine/schema.py")
    assert is_core_engine_file("backend/engine/registry.py")
    assert is_core_engine_file("backend/engine/artifacts.py")
    assert is_core_engine_file("backend/engine/train.py")
    assert is_core_engine_file("backend/engine/models/sar.py")
    assert is_core_engine_file("backend/engine/evaluation/harness.py")
    assert is_core_engine_file("backend/engine/evaluation/metrics.py")


def test_disallowed_arbitrary_files() -> None:
    """Verify arbitrary new files outside allowed dirs are flagged as disallowed."""
    assert not is_allowed_path("random_script.py")
    assert not is_allowed_path("backend/extra_module.py")


PHASE_4_END_COMMIT = "c31af6e"


def test_phase_4_git_history_zero_core_violations() -> None:
    """Verify that Phase 4 real git history (6da1d3a..c31af6e) contains zero core engine changes."""
    passed, disallowed, core_violations = check_core_unchanged(
        base_commit="6da1d3a", target=PHASE_4_END_COMMIT
    )
    assert passed, (
        f"Phase 4 check failed! Disallowed: {disallowed}, Core violations: {core_violations}"
    )
    assert disallowed == []
    assert core_violations == []


def test_real_repo_passes_core_unchanged() -> None:
    """Verify that current repo passes core unchanged check and any core additions are documented."""
    passed, disallowed, core_violations = check_core_unchanged()
    assert passed, (
        f"Core unchanged check failed! Disallowed: {disallowed}, Core violations: {core_violations}"
    )
    assert disallowed == []
