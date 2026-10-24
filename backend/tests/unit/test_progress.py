"""Unit tests for tools/progress.py."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Add project root to path so we can import the tool
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "tools"))

from progress import PhaseStats, build_dashboard, parse_phases, update_plan


SAMPLE_PLAN = textwrap.dedent("""\
    # Title

    <!-- PROGRESS:START -->
    old content here
    <!-- PROGRESS:END -->

    ## PHASE 0: Scaffolding

    - [x] **P0.1** Task one. *Acceptance:* done.
    - [x] **P0.2** Task two. *Acceptance:* done.
    - [ ] **P0.3** Task three. *Acceptance:* todo.

    ## PHASE 1: Vendor code

    - [~] **P1.1** In progress task.
    - [!] **P1.2** Blocked task.
    - [ ] **P1.3** Not started.
    - [ ] **P1.4** Not started.
""")


class TestParsePhases:
    def test_counts_markers(self):
        phases = parse_phases(SAMPLE_PLAN)
        assert len(phases) == 2

        p0 = phases[0]
        assert p0.number == 0
        assert p0.name == "Scaffolding"
        assert p0.done == 2
        assert p0.in_progress == 0
        assert p0.blocked == 0
        assert p0.not_started == 1
        assert p0.total == 3
        assert p0.pct == 66

        p1 = phases[1]
        assert p1.number == 1
        assert p1.name == "Vendor code"
        assert p1.done == 0
        assert p1.in_progress == 1
        assert p1.blocked == 1
        assert p1.not_started == 2
        assert p1.total == 4
        assert p1.pct == 0

    def test_empty_text(self):
        phases = parse_phases("")
        assert phases == []

    def test_no_tasks(self):
        phases = parse_phases("## PHASE 0: Empty phase\n\nNo tasks here.\n")
        assert len(phases) == 1
        assert phases[0].total == 0
        assert phases[0].pct == 0


class TestBuildDashboard:
    def test_contains_phase_rows(self):
        phases = parse_phases(SAMPLE_PLAN)
        dashboard = build_dashboard(phases)
        assert "Scaffolding" in dashboard
        assert "Vendor code" in dashboard
        assert "**Overall**" in dashboard
        assert "2/7" in dashboard  # 2 done out of 7 total

    def test_progress_bar(self):
        phases = [PhaseStats(number=0, name="Test", done=10, not_started=10)]
        dashboard = build_dashboard(phases)
        assert "50%" in dashboard
        assert "10/20" in dashboard


class TestUpdatePlan:
    def test_idempotent(self, tmp_path):
        plan_file = tmp_path / "IMPLEMENTATION_PLAN.md"
        plan_file.write_text(SAMPLE_PLAN, encoding="utf-8")

        # First run should change
        changed1 = update_plan(plan_file)
        assert changed1

        content_after_first = plan_file.read_text(encoding="utf-8")

        # Second run should not change
        changed2 = update_plan(plan_file)
        assert not changed2

        content_after_second = plan_file.read_text(encoding="utf-8")
        assert content_after_first == content_after_second

    def test_preserves_surrounding_content(self, tmp_path):
        plan_file = tmp_path / "IMPLEMENTATION_PLAN.md"
        plan_file.write_text(SAMPLE_PLAN, encoding="utf-8")

        update_plan(plan_file)
        content = plan_file.read_text(encoding="utf-8")

        # Content before and after markers should be preserved
        assert content.startswith("# Title")
        assert "## PHASE 0: Scaffolding" in content
        assert "## PHASE 1: Vendor code" in content
