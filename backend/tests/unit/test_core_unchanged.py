"""Unit tests for tools/core_unchanged.py (P4.7).

Verifies that the core unchanged check properly identifies core engine files,
permits domain extensions (adapters, configs, tests, docs, tools), and asserts
that real Phase 4 git history contains zero core engine changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add tools to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from core_unchanged import (  # noqa: E402
    PHASE_3_END_TAG,
    PHASE_4_END_TAG,
    GitHistoryUnavailable,
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
    assert is_allowed_path("backend/uv.lock")
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


def test_phase_4_git_history_zero_core_violations() -> None:
    """Verify that Phase 4 real git history (phase-3-end..phase-4-end) contains zero core engine changes."""
    try:
        passed, disallowed, core_violations = check_core_unchanged(
            base_commit=PHASE_3_END_TAG, target=PHASE_4_END_TAG
        )
    except GitHistoryUnavailable as exc:
        pytest.skip(str(exc))

    assert passed, (
        f"Phase 4 check failed! Disallowed: {disallowed}, Core violations: {core_violations}"
    )
    assert disallowed == []
    assert core_violations == []


def test_real_repo_passes_core_unchanged() -> None:
    """Verify that current repo passes core unchanged check and any core additions are documented."""
    try:
        passed, disallowed, core_violations = check_core_unchanged()
    except GitHistoryUnavailable as exc:
        pytest.skip(str(exc))

    assert passed, (
        f"Core unchanged check failed! Disallowed: {disallowed}, Core violations: {core_violations}"
    )
    assert disallowed == []


def test_shallow_clone_skip_behaviour(tmp_path: Path) -> None:
    """Verify check_core_unchanged raises GitHistoryUnavailable and triggers skip on shallow clone."""
    import subprocess

    clone_dir = tmp_path / "shallow_clone"
    repo_url = f"file://{REPO_ROOT.resolve().as_posix()}"
    clone_res = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
        capture_output=True,
        text=True,
    )
    if clone_res.returncode != 0:
        pytest.skip(f"git clone failed in test environment: {clone_res.stderr}")

    # Assert GitHistoryUnavailable is raised when history is shallow
    with pytest.raises(GitHistoryUnavailable) as exc_info:
        check_core_unchanged(
            base_commit=PHASE_3_END_TAG,
            target="HEAD",
            repo_root=clone_dir,
        )
    assert (
        "missing or does not resolve" in str(exc_info.value)
        or "unavailable" in str(exc_info.value).lower()
    )

    # Assert test handling catches it and triggers pytest.skip with the reason
    with pytest.raises(pytest.skip.Exception) as skip_info:
        try:
            check_core_unchanged(
                base_commit=PHASE_3_END_TAG,
                target="HEAD",
                repo_root=clone_dir,
            )
        except GitHistoryUnavailable as exc:
            pytest.skip(f"Git history unavailable in shallow clone: {exc}")

    assert "Git history unavailable in shallow clone" in str(skip_info.value)
