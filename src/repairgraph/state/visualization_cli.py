"""
Visualization CLI for RepairGraph workflow.

Generates the projected Honda 2025 Accord repair state, builds the workflow
visualization payload, and exports JSON and Mermaid files to
data/extracted/state/.

Run:
    python -m repairgraph.state.visualization_cli
"""
from __future__ import annotations

import json
from pathlib import Path

from repairgraph.state.demo import build_accord_projected_state
from repairgraph.state.export_mermaid import (
    build_blocker_flow_mermaid,
    build_phase_flow_mermaid,
    build_workflow_timeline_mermaid,
    build_zone_activation_mermaid,
)
from repairgraph.state.visualization_payload import build_workflow_visualization_payload

_DEFAULT_BASE_DIR = Path("data/extracted/state")


def run_visualization_cli(base_dir: Path | str | None = None) -> dict:
    """Build and export the Accord workflow visualization to JSON and Mermaid files.

    Generates the projected state, builds the visualization payload, and writes:
    - accord_workflow_visualization.json
    - accord_timeline.mmd
    - accord_phase_flow.mmd
    - accord_blocker_flow.mmd
    - accord_zone_activation.mmd

    Returns the visualization payload dict so callers can inspect it without
    re-running the build.
    """
    out_dir = Path(base_dir) if base_dir is not None else _DEFAULT_BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    state = build_accord_projected_state()
    payload = build_workflow_visualization_payload(state)

    json_path = out_dir / "accord_workflow_visualization.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    timeline_path = out_dir / "accord_timeline.mmd"
    timeline_path.write_text(build_workflow_timeline_mermaid(state), encoding="utf-8")

    phase_path = out_dir / "accord_phase_flow.mmd"
    phase_path.write_text(build_phase_flow_mermaid(state), encoding="utf-8")

    blocker_path = out_dir / "accord_blocker_flow.mmd"
    blocker_path.write_text(build_blocker_flow_mermaid(state), encoding="utf-8")

    zone_path = out_dir / "accord_zone_activation.mmd"
    zone_path.write_text(build_zone_activation_mermaid(state), encoding="utf-8")

    wf = payload["workflow_summary"]
    ctx = payload["active_context"]

    print(f"Events:         {wf['event_count']}")
    print(f"Open blockers:  {wf['open_blocker_count']}")
    print(f"Active phases:  {ctx['active_phase_ids']}")
    print(f"Next actions:   {ctx['next_action_ids']}")
    print()
    print(f"Output JSON:    {json_path}")
    print(f"Timeline MMD:   {timeline_path}")
    print(f"Phase flow MMD: {phase_path}")
    print(f"Blocker MMD:    {blocker_path}")
    print(f"Zone MMD:       {zone_path}")

    return payload


def main() -> None:
    run_visualization_cli()


if __name__ == "__main__":
    main()
