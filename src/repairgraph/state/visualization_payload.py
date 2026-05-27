"""
Workflow visualization payload builder for RepairGraph repair state.

Produces a combined introspection and debug payload with timelines, Mermaid
visualizations, replay metadata, and active workflow context.

This is NOT a UI payload. It is an introspection/debug/demo payload intended
for operational inspection, tooling, and demos.

All outputs are advisory workflow intelligence and do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

from typing import Any

from repairgraph.state.blockers import get_open_blockers, summarize_blockers
from repairgraph.state.export_mermaid import (
    build_blocker_flow_mermaid,
    build_phase_flow_mermaid,
    build_workflow_timeline_mermaid,
    build_zone_activation_mermaid,
)
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.schema import RepairState
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
    summarize_timeline,
)

SCHEMA_NAME = "repairgraph.workflow_visualization"
SCHEMA_VERSION = "0.1"
GENERATED_BY = "repairgraph.state.visualization_payload"

ADVISORY_NOTE = (
    "This payload is advisory workflow intelligence derived from RepairGraph "
    "procedure data and explicit state events. It does not certify repair "
    "completion, OEM compliance, or repair quality. All workflow guidance "
    "requires OEM procedure verification and qualified technician review "
    "before acting on any recommendation."
)


def build_workflow_visualization_payload(state: RepairState) -> dict[str, Any]:
    """Build a combined introspection/debug visualization payload from a RepairState.

    Combines timelines, Mermaid visualizations, replay metadata, active context,
    blocker summaries, and next action guidance into a single JSON-serializable dict.

    This payload is intended for internal tooling, operational inspection, and demos.
    It is not a UI payload and requires no browser rendering.
    """
    open_blockers = get_open_blockers(state)

    active_phase_ids = [p.name for p in state.phases if p.status == "in_progress"]
    blocked_phase_ids = [p.name for p in state.phases if p.status == "blocked"]
    active_zone_ids = [z.zone_id for z in state.zones if z.status == "active"]
    blocked_zone_ids = [z.zone_id for z in state.zones if z.status == "blocked"]

    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "advisory": True,
        "generated_by": GENERATED_BY,
        "advisory_note": ADVISORY_NOTE,
        "session": {
            "session_id": state.session.session_id,
            "oem": state.session.oem,
            "year": state.session.year,
            "model": state.session.model,
            "operation": state.session.operation,
            "status": state.session.status,
            "current_phase": state.session.current_phase,
        },
        "workflow_summary": {
            "phase_count": len(state.phases),
            "action_count": len(state.actions),
            "qa_gate_count": len(state.qa_gates),
            "blocker_count": len(state.blockers),
            "open_blocker_count": len(open_blockers),
            "event_count": len(state.events),
            "next_action_count": len(state.next_recommended_actions),
        },
        "timelines": {
            "summary": summarize_timeline(state),
            "events": build_event_timeline(state),
            "phases": build_phase_timeline(state),
            "actions": build_action_timeline(state),
        },
        "replay_metadata": {
            "event_count": len(state.events),
            "snapshot_count": len(state.events),
            "event_ids": [e.event_id for e in state.events],
            "event_types": [e.event_type for e in state.events],
            "event_timestamps": [e.timestamp for e in state.events],
            "note": (
                "Full replay snapshots and per-event diffs are available "
                "via /internal/state/accord/replay"
            ),
        },
        "visualization": {
            "sections": [
                "workflow_timeline",
                "phase_flow",
                "blocker_flow",
                "zone_activation",
            ],
            "mermaid": {
                "workflow_timeline": build_workflow_timeline_mermaid(state),
                "phase_flow": build_phase_flow_mermaid(state),
                "blocker_flow": build_blocker_flow_mermaid(state),
                "zone_activation": build_zone_activation_mermaid(state),
            },
        },
        "active_context": {
            "active_phase_ids": active_phase_ids,
            "blocked_phase_ids": blocked_phase_ids,
            "active_zone_ids": active_zone_ids,
            "blocked_zone_ids": blocked_zone_ids,
            "next_action_ids": list(state.next_recommended_actions),
        },
        "blockers": summarize_blockers(state),
        "next_actions": summarize_next_actions(state),
    }
