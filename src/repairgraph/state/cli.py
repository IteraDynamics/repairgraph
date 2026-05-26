"""
CLI demo: initialize a Honda 2025 Accord repair state, apply a deterministic
sample event ledger, project the resulting state, and export JSON.

Run:
    python -m repairgraph.state.cli
"""
from __future__ import annotations

import json
from pathlib import Path

from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.export_json import export_state_to_dict
from repairgraph.state.schema import RepairState

DEFAULT_OUTPUT_PATH = "data/extracted/state/accord_projected_state.json"

# Preserved for backward compatibility — ar_cli and tests may import this name.
_build_sample_events = build_accord_demo_events


def run_demo(output_path: str = DEFAULT_OUTPUT_PATH) -> RepairState:
    """Initialize the Accord state, apply sample events, export JSON, and print summary.

    Returns the projected RepairState so callers can inspect it without re-running.
    """
    projected = build_accord_projected_state()
    payload = export_state_to_dict(projected)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Output:                   {out}")
    print(f"Session:                  {projected.session.status} ({projected.session.session_id})")
    print(f"Phases:                   {len(projected.phases)}")
    print(f"Actions:                  {len(projected.actions)}")
    print(f"QA Gates:                 {len(projected.qa_gates)}")
    print(f"Blockers:                 {len(projected.blockers)}")
    print(f"Events applied:           {len(projected.events)}")
    print(f"Next recommended actions: {len(projected.next_recommended_actions)}")

    return projected


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
