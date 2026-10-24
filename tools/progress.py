#!/usr/bin/env python3
"""Parse IMPLEMENTATION_PLAN.md and update the Progress Dashboard.

Counts [x], [~], [!], and [ ] task markers inside ## PHASE sections,
then rewrites the table between <!-- PROGRESS:START --> and <!-- PROGRESS:END -->.
Idempotent: running twice changes nothing the second time.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Regex patterns
PHASE_HEADER_RE = re.compile(r"^## PHASE (\d+):\s*(.+)$", re.IGNORECASE)
TASK_RE = re.compile(r"^- \[([ x~!])\] \*\*P\d+\.\d+\*\*")
PROGRESS_START = "<!-- PROGRESS:START -->"
PROGRESS_END = "<!-- PROGRESS:END -->"


@dataclass
class PhaseStats:
    """Statistics for a single phase."""

    number: int
    name: str
    done: int = 0
    in_progress: int = 0
    blocked: int = 0
    not_started: int = 0

    @property
    def total(self) -> int:
        return self.done + self.in_progress + self.blocked + self.not_started

    @property
    def pct(self) -> int:
        if self.total == 0:
            return 0
        return int(100 * self.done / self.total)


def parse_phases(text: str) -> list[PhaseStats]:
    """Parse phase sections and count task markers."""
    phases: list[PhaseStats] = []
    current: PhaseStats | None = None

    for line in text.splitlines():
        m = PHASE_HEADER_RE.match(line)
        if m:
            current = PhaseStats(number=int(m.group(1)), name=m.group(2).strip())
            phases.append(current)
            continue

        if current is None:
            continue

        tm = TASK_RE.match(line)
        if tm:
            marker = tm.group(1)
            if marker == "x":
                current.done += 1
            elif marker == "~":
                current.in_progress += 1
            elif marker == "!":
                current.blocked += 1
            else:
                current.not_started += 1

    return phases


def build_dashboard(phases: list[PhaseStats]) -> str:
    """Build the markdown dashboard table."""
    lines: list[str] = []

    # Table header
    lines.append("| Phase | Name | Done | In progress | Blocked | Total | % |")
    lines.append("|---|---|---|---|---|---|---|")

    total_done = 0
    total_ip = 0
    total_blocked = 0
    total_all = 0

    for p in phases:
        lines.append(
            f"| {p.number} | {p.name} | {p.done} | {p.in_progress} "
            f"| {p.blocked} | {p.total} | {p.pct}% |"
        )
        total_done += p.done
        total_ip += p.in_progress
        total_blocked += p.blocked
        total_all += p.total

    overall_pct = int(100 * total_done / total_all) if total_all > 0 else 0
    lines.append(
        f"| | **Overall** | **{total_done}** | | | **{total_all}** | **{overall_pct}%** |"
    )

    # Progress bar (20 chars wide)
    filled = int(20 * total_done / total_all) if total_all > 0 else 0
    bar = "#" * filled + "-" * (20 - filled)
    lines.append("")
    lines.append(f"`[{bar}] {overall_pct}%  ({total_done}/{total_all} tasks)`")

    return "\n".join(lines)


def update_plan(plan_path: Path) -> bool:
    """Read the plan, update the dashboard, write back. Returns True if changed."""
    text = plan_path.read_text(encoding="utf-8")

    start_idx = text.find(PROGRESS_START)
    end_idx = text.find(PROGRESS_END)

    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find PROGRESS:START/END markers in the plan file.")
        return False

    phases = parse_phases(text)
    if not phases:
        print("WARNING: No phases found in the plan file.")
        return False

    dashboard = build_dashboard(phases)

    # Build new content between markers
    before = text[: start_idx + len(PROGRESS_START)]
    after = text[end_idx:]
    new_text = before + "\n" + dashboard + "\n" + after

    if new_text == text:
        print("Dashboard already up to date.")
        return False

    plan_path.write_text(new_text, encoding="utf-8")
    print(
        f"Dashboard updated: {sum(p.done for p in phases)}/{sum(p.total for p in phases)} tasks done."
    )
    return True


def main() -> None:
    # Find the plan file
    plan_path = Path(__file__).resolve().parent.parent / "IMPLEMENTATION_PLAN.md"
    if not plan_path.exists():
        # Try current directory
        plan_path = Path("IMPLEMENTATION_PLAN.md")
    if not plan_path.exists():
        print("ERROR: Cannot find IMPLEMENTATION_PLAN.md")
        sys.exit(1)

    update_plan(plan_path)


if __name__ == "__main__":
    main()
