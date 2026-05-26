"""
CLI demo: build an AR workflow payload from the Honda 2025 Accord projected state.

Applies the same deterministic sample event ledger used by the state CLI,
builds the AR workflow payload, and exports to JSON.

Run:
    python -m repairgraph.state.ar_cli
"""
from __future__ import annotations

import json
from pathlib import Path

from repairgraph.state.demo import build_accord_projected_state
from repairgraph.state.ar_payload import build_ar_workflow_payload

DEFAULT_OUTPUT_PATH = "data/extracted/state/accord_ar_workflow_payload.json"


def run_ar_demo(output_path: str = DEFAULT_OUTPUT_PATH) -> dict:
    """Build AR workflow payload from Accord projected state, export JSON, and print summary.

    Returns the AR payload dict so callers can inspect it without re-running.
    Does not require network access.
    """
    projected = build_accord_projected_state()
    payload = build_ar_workflow_payload(projected)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Output:             {out}")
    print(f"Session status:     {payload['session']['status']}")
    print(f"Zone overlays:      {len(payload['overlays']['zones'])}")
    print(f"Action guidance:    {len(payload['overlays']['actions'])}")
    print(f"QA gates:           {len(payload['overlays']['qa_gates'])}")
    print(f"Blockers:           {len(payload['overlays']['blockers'])}")
    print(f"Next actions:       {payload['workflow_summary']['next_action_count']}")

    return payload


def main() -> None:
    run_ar_demo()


if __name__ == "__main__":
    main()
