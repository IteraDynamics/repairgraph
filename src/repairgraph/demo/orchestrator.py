"""
End-to-end RepairGraph demo orchestrator.

Assembles the complete golden-path demo payload by calling existing modules
in sequence. No business logic is duplicated — this is pure orchestration.

Stages:
  1. OEM intake classification (using synthetic fixture packet)
  2. Topology + workflow intelligence construction
  3. Replay snapshots
  4. Export metadata

All outputs are deterministic and advisory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from repairgraph.intake.classify import classify_intake_packet, summarize_intake_manifest
from repairgraph.state.blockers import summarize_blockers
from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.export_json import ADVISORY_NOTE, export_state_to_dict
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.replay import build_state_diff, replay_repair_state, summarize_state_diff
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
    summarize_timeline,
)

_GENERATED_BY = "repairgraph.demo.orchestrator"

# Fixture packet used for the demo — the Toyota Camry packet is rich enough
# to demonstrate classification without requiring OEM PDFs.
_FIXTURE_PACKET_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "intake" / "toyota_packet"

# Fallback: ford packet if toyota is unavailable
_FALLBACK_PACKET_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "intake" / "ford_packet"


def _demo_packet_dir() -> Path:
    """Return the fixture packet directory to use for the demo."""
    if _FIXTURE_PACKET_DIR.exists():
        return _FIXTURE_PACKET_DIR
    if _FALLBACK_PACKET_DIR.exists():
        return _FALLBACK_PACKET_DIR
    raise FileNotFoundError("No demo fixture packet found. Checked toyota_packet and ford_packet.")


def build_intake_demo_payload() -> dict[str, Any]:
    """Run OEM intake classification on the demo fixture packet.

    Returns a serializable summary of the manifest plus file-level details.
    This is step 1 and 2 of the demo flow.
    """
    packet_dir = _demo_packet_dir()
    paths = sorted(packet_dir.glob("*.txt")) + sorted(packet_dir.glob("*.pdf"))
    manifest = classify_intake_packet(paths)
    summary = summarize_intake_manifest(manifest)

    files_detail = [
        {
            "filename": f.filename,
            "document_role": f.document_role,
            "supporting_roles": f.supporting_roles,
            "confidence": f.confidence,
            "detected_oem": f.detected_oem,
            "detected_model": f.detected_model,
            "detected_year": f.detected_year,
            "warnings": f.warnings,
            "errors": f.errors,
        }
        for f in manifest.files
    ]

    diagnostics = [
        {
            "code": d.code,
            "severity": d.severity,
            "message": d.message,
        }
        for d in manifest.diagnostics
    ]

    return {
        "schema_name": "repairgraph.demo.intake",
        "generated_by": _GENERATED_BY,
        "fixture_packet": packet_dir.name,
        "file_count": len(manifest.files),
        "summary": summary,
        "files": files_detail,
        "diagnostics": diagnostics,
        "detected_packet": {
            "oem": manifest.detected_packet.detected_oem,
            "model": manifest.detected_packet.detected_model,
            "year": manifest.detected_packet.detected_year,
            "operation": manifest.detected_packet.detected_operation,
            "confidence": manifest.detected_packet.oem_confidence,
            "detected_roles": manifest.detected_packet.detected_roles,
        },
        "readiness": manifest.readiness,
        "missing_roles": manifest.missing_roles,
    }


def _serialize_event(e: Any) -> dict:
    return {
        "event_id": e.event_id,
        "timestamp": e.timestamp,
        "event_type": e.event_type,
        "actor": e.actor,
        "target_type": e.target_type,
        "target_id": e.target_id,
        "notes": e.notes,
    }


def build_workflow_demo_payload() -> dict[str, Any]:
    """Build the complete workflow intelligence payload for the Accord demo.

    Delegates entirely to existing state, replay, and timeline modules.
    This is step 3+ of the demo flow.
    """
    initial = build_accord_initial_state()
    events = build_accord_demo_events(initial)
    projected = build_accord_projected_state()

    snapshots = replay_repair_state(initial, events)

    replay_steps = []
    prev = initial
    for i, (event, snap) in enumerate(zip(events, snapshots)):
        diff = build_state_diff(prev, snap)
        diff_summary = summarize_state_diff(diff)
        replay_steps.append({
            "step": i + 1,
            "event": _serialize_event(event),
            "state_summary": {
                "session_status": snap.session.status,
                "completed_action_count": sum(1 for a in snap.actions if a.status == "complete"),
                "open_blocker_count": sum(1 for b in snap.blockers if b.status == "open"),
                "active_phases": [p.name for p in snap.phases if p.status == "in_progress"],
            },
            "diff_summary": diff_summary,
        })
        prev = snap

    timeline_summary = summarize_timeline(projected)
    blocker_summary = summarize_blockers(projected)
    next_actions_summary = summarize_next_actions(projected)

    return {
        "schema_name": "repairgraph.demo.workflow",
        "generated_by": _GENERATED_BY,
        "advisory": True,
        "advisory_note": ADVISORY_NOTE,
        "session": {
            "session_id": projected.session.session_id,
            "oem": projected.session.oem,
            "year": projected.session.year,
            "model": projected.session.model,
            "operation": projected.session.operation,
            "status": projected.session.status,
            "current_phase": projected.session.current_phase,
        },
        "workflow_summary": {
            "phase_count": len(projected.phases),
            "action_count": len(projected.actions),
            "qa_gate_count": len(projected.qa_gates),
            "blocker_count": len(projected.blockers),
            "event_count": len(projected.events),
            "zone_count": len(projected.zones),
            "open_blocker_count": sum(1 for b in projected.blockers if b.status == "open"),
            "complete_action_count": sum(1 for a in projected.actions if a.status == "complete"),
            "next_action_count": len(projected.next_recommended_actions),
        },
        "event_timeline": build_event_timeline(projected),
        "phase_timeline": build_phase_timeline(projected),
        "action_timeline": build_action_timeline(projected),
        "timeline_summary": timeline_summary,
        "replay_steps": replay_steps,
        "replay_event_count": len(events),
        "next_actions": list(projected.next_recommended_actions),
        "next_actions_summary": next_actions_summary,
        "blockers_summary": blocker_summary,
        "phases": [
            {
                "phase": p.phase,
                "name": p.name,
                "label": p.label,
                "status": p.status,
                "pending_action_count": len(p.pending_actions),
                "completed_action_count": len(p.completed_actions),
            }
            for p in projected.phases
        ],
        "open_blockers": [
            {
                "blocker_id": b.blocker_id,
                "type": b.type,
                "severity": b.severity,
                "reason": b.reason,
            }
            for b in projected.blockers if b.status == "open"
        ],
    }


def build_full_demo_payload() -> dict[str, Any]:
    """Assemble the complete demo payload combining intake + workflow.

    This is the single data source for the demo page. All business logic
    is delegated to intake and state modules.
    """
    intake = build_intake_demo_payload()
    workflow = build_workflow_demo_payload()
    return {
        "schema_name": "repairgraph.demo.full",
        "generated_by": _GENERATED_BY,
        "advisory": True,
        "intake": intake,
        "workflow": workflow,
        "export_links": {
            "workflow_report": "/internal/state/accord/report?view=workflow",
            "replay_report": "/internal/state/accord/report?view=replay",
            "intake_page": "/internal/intake",
            "visualization_json": "/internal/state/accord/visualization",
            "topology_viewer": "/internal/state/accord/topology-viewer",
        },
    }
