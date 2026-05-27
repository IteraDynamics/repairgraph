"""
HTML report export CLI for RepairGraph workflow intelligence.

Generates self-contained workflow and replay HTML reports from the deterministic
Accord projected state and writes them to data/extracted/state/.

Usage:
    python -m repairgraph.state.report_cli

All outputs are advisory workflow intelligence. They do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import sys
from pathlib import Path

from repairgraph.state.blockers import get_open_blockers
from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.html_report import build_replay_html_report, build_workflow_html_report
from repairgraph.state.replay import replay_repair_state

_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "extracted" / "state"

WORKFLOW_FILENAME = "accord_workflow_report.html"
REPLAY_FILENAME = "accord_replay_report.html"


def run_report_cli() -> None:
    """Generate and export Accord workflow and replay HTML reports."""
    print("RepairGraph HTML Report CLI")
    print("─" * 40)

    print("Building Accord projected state...")
    projected = build_accord_projected_state()
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    snapshots = replay_repair_state(initial, events)

    phase_count = len(projected.phases)
    open_blocker_count = len(get_open_blockers(projected))
    event_count = len(projected.events)
    snapshot_count = len(snapshots)

    print(f"  phases:           {phase_count}")
    print(f"  open blockers:    {open_blocker_count}")
    print(f"  events:           {event_count}")
    print(f"  replay snapshots: {snapshot_count}")
    print()

    print("Generating workflow report HTML...")
    workflow_html = build_workflow_html_report(projected)

    print("Generating replay report HTML...")
    replay_html = build_replay_html_report(initial, events)

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    workflow_path = _OUTPUT_DIR / WORKFLOW_FILENAME
    replay_path = _OUTPUT_DIR / REPLAY_FILENAME

    workflow_path.write_text(workflow_html, encoding="utf-8")
    replay_path.write_text(replay_html, encoding="utf-8")

    print("Reports written:")
    print(f"  workflow: {workflow_path}")
    print(f"  replay:   {replay_path}")
    print()
    print("Advisory: All outputs are workflow projections requiring OEM verification.")


if __name__ == "__main__":
    run_report_cli()
