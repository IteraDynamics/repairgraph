"""
JSON export helpers for RepairState.

Converts RepairState and child dataclasses into plain JSON-serializable
dictionaries with provenance metadata.

All output is advisory workflow intelligence and does not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import json
from typing import Any

from repairgraph.state.schema import RepairState

SCHEMA_NAME = "repairgraph.repair_state"
SCHEMA_VERSION = "0.1"
GENERATED_BY = "repairgraph.state"

ADVISORY_NOTE = (
    "This output is an advisory workflow projection derived from RepairGraph "
    "procedure data and explicit state events. It does not certify repair "
    "completion, OEM compliance, or repair quality. All state projections "
    "require OEM procedure verification and qualified technician review "
    "before acting on any recommendation."
)


def _serialize_session(session: Any) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "oem": session.oem,
        "year": session.year,
        "model": session.model,
        "operation": session.operation,
        "status": session.status,
        "current_phase": session.current_phase,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _serialize_phase(phase: Any) -> dict[str, Any]:
    return {
        "phase": phase.phase,
        "name": phase.name,
        "label": phase.label,
        "status": phase.status,
        "active_zones": list(phase.active_zones),
        "completed_actions": list(phase.completed_actions),
        "pending_actions": list(phase.pending_actions),
        "blocked_by": list(phase.blocked_by),
    }


def _serialize_action(action: Any) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "phase": action.phase,
        "action_type": action.action_type,
        "target": action.target,
        "status": action.status,
        "zone_refs": list(action.zone_refs),
        "requires_qa": action.requires_qa,
        "evidence": action.evidence,
    }


def _serialize_qa_gate(gate: Any) -> dict[str, Any]:
    return {
        "gate_id": gate.gate_id,
        "category": gate.category,
        "priority": gate.priority,
        "status": gate.status,
        "related_phase": gate.related_phase,
        "zone_refs": list(gate.zone_refs),
        "check": gate.check,
        "blocks_completion": gate.blocks_completion,
        "evidence": gate.evidence,
    }


def _serialize_zone(zone: Any) -> dict[str, Any]:
    return {
        "zone_id": zone.zone_id,
        "label": zone.label,
        "status": zone.status,
        "active_phase": zone.active_phase,
        "active_actions": list(zone.active_actions),
        "material_classification": zone.material_classification,
        "risk_flags": list(zone.risk_flags),
    }


def _serialize_blocker(blocker: Any) -> dict[str, Any]:
    return {
        "blocker_id": blocker.blocker_id,
        "type": blocker.type,
        "severity": blocker.severity,
        "status": blocker.status,
        "blocks": list(blocker.blocks),
        "reason": blocker.reason,
        "related_zones": list(blocker.related_zones),
        "related_actions": list(blocker.related_actions),
    }


def _serialize_event(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "actor": event.actor,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "notes": event.notes,
        "evidence": event.evidence,
    }


def export_state_to_dict(state: RepairState) -> dict[str, Any]:
    """Convert RepairState to a JSON-serializable dictionary with provenance metadata."""
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "advisory": True,
        "generated_by": GENERATED_BY,
        "advisory_note": ADVISORY_NOTE,
        "session": _serialize_session(state.session),
        "phases": [_serialize_phase(p) for p in state.phases],
        "actions": [_serialize_action(a) for a in state.actions],
        "qa_gates": [_serialize_qa_gate(g) for g in state.qa_gates],
        "zones": [_serialize_zone(z) for z in state.zones],
        "blockers": [_serialize_blocker(b) for b in state.blockers],
        "events": [_serialize_event(e) for e in state.events],
        "next_recommended_actions": list(state.next_recommended_actions),
        "interpretation_note": state.interpretation_note,
    }


def export_state_to_json(state: RepairState, indent: int = 2) -> str:
    """Convert RepairState to a JSON string."""
    return json.dumps(export_state_to_dict(state), indent=indent)
