"""
AR workflow payload builder for RepairGraph repair state.

Produces machine-readable payload contracts for AR technician interfaces,
workflow UIs, and API clients. All outputs are advisory workflow intelligence
and do not certify repair completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import json
from typing import Any

from repairgraph.state.schema import RepairState

SCHEMA_NAME = "repairgraph.ar_workflow_payload"
SCHEMA_VERSION = "0.1"
GENERATED_BY = "repairgraph.state.ar_payload"

SOURCE_SCHEMA_NAME = "repairgraph.repair_state"
SOURCE_SCHEMA_VERSION = "0.1"

ADVISORY_NOTE = (
    "This payload is advisory workflow intelligence derived from RepairGraph "
    "procedure data and explicit state events. It does not certify repair "
    "completion, OEM compliance, or repair quality. All workflow guidance "
    "requires OEM procedure verification and qualified technician review "
    "before acting on any recommendation."
)


def build_zone_overlay_items(state: RepairState) -> list[dict[str, Any]]:
    """Build zone overlay items for AR/workflow display.

    Each item includes zone metadata and an overlay_role that classifies the
    zone's current status for downstream rendering or filtering.

    Overlay role values:
      active_repair_zone    — zone is currently active
      blocked_zone          — zone has an unresolved blocker
      completed_zone        — zone's actions are complete
      inactive_context_zone — zone is inactive or pending
    """
    items = []
    for zone in state.zones:
        if zone.status == "active":
            overlay_role = "active_repair_zone"
        elif zone.status == "blocked":
            overlay_role = "blocked_zone"
        elif zone.status == "complete":
            overlay_role = "completed_zone"
        else:
            overlay_role = "inactive_context_zone"

        items.append({
            "zone_id": zone.zone_id,
            "label": zone.label,
            "status": zone.status,
            "active_phase": zone.active_phase,
            "active_actions": list(zone.active_actions),
            "material_classification": zone.material_classification,
            "risk_flags": list(zone.risk_flags),
            "overlay_role": overlay_role,
        })
    return items


def build_action_guidance_items(state: RepairState) -> list[dict[str, Any]]:
    """Build action guidance items for AR/workflow display.

    Each item includes action metadata and a guidance_role that classifies the
    action's current priority for technician guidance.

    Guidance role precedence (first match wins):
      next_recommended_action — action is in state.next_recommended_actions
      active_action           — status is in_progress
      blocked_action          — status is blocked
      completed_action        — status is complete
      not_applicable_action   — status is not_applicable
      pending_context_action  — all other cases
    """
    next_action_ids = set(state.next_recommended_actions)
    items = []
    for action in state.actions:
        if action.action_id in next_action_ids:
            guidance_role = "next_recommended_action"
        elif action.status == "in_progress":
            guidance_role = "active_action"
        elif action.status == "blocked":
            guidance_role = "blocked_action"
        elif action.status == "complete":
            guidance_role = "completed_action"
        elif action.status == "not_applicable":
            guidance_role = "not_applicable_action"
        else:
            guidance_role = "pending_context_action"

        items.append({
            "action_id": action.action_id,
            "action_type": action.action_type,
            "target": action.target,
            "phase": action.phase,
            "status": action.status,
            "zone_refs": list(action.zone_refs),
            "requires_qa": action.requires_qa,
            "guidance_role": guidance_role,
            "evidence": action.evidence,
        })
    return items


def build_qa_gate_items(state: RepairState) -> list[dict[str, Any]]:
    """Build QA gate items for AR/workflow display.

    Each item includes gate metadata and a guidance_role that classifies
    the gate's current urgency for technician guidance.

    Guidance role values:
      blocking_open_qa_gate  — blocks_completion=True and status is open/in_review/failed
      passed_qa_gate         — status is passed
      not_applicable_qa_gate — status is not_applicable
      context_qa_gate        — all other cases
    """
    items = []
    for gate in state.qa_gates:
        if gate.blocks_completion and gate.status in {"open", "in_review", "failed"}:
            guidance_role = "blocking_open_qa_gate"
        elif gate.status == "passed":
            guidance_role = "passed_qa_gate"
        elif gate.status == "not_applicable":
            guidance_role = "not_applicable_qa_gate"
        else:
            guidance_role = "context_qa_gate"

        items.append({
            "gate_id": gate.gate_id,
            "category": gate.category,
            "priority": gate.priority,
            "status": gate.status,
            "related_phase": gate.related_phase,
            "zone_refs": list(gate.zone_refs),
            "check": gate.check,
            "blocks_completion": gate.blocks_completion,
            "guidance_role": guidance_role,
            "evidence": gate.evidence,
        })
    return items


def build_blocker_items(state: RepairState) -> list[dict[str, Any]]:
    """Build blocker items for AR/workflow display.

    Each item includes blocker metadata and a guidance_role that classifies
    the blocker's urgency for technician attention.

    Guidance role values:
      critical_open_blocker — open blocker with critical severity
      open_blocker          — open blocker with non-critical severity
      resolved_blocker      — blocker has been resolved
    """
    items = []
    for blocker in state.blockers:
        if blocker.status == "open" and blocker.severity == "critical":
            guidance_role = "critical_open_blocker"
        elif blocker.status == "open":
            guidance_role = "open_blocker"
        else:
            guidance_role = "resolved_blocker"

        items.append({
            "blocker_id": blocker.blocker_id,
            "type": blocker.type,
            "severity": blocker.severity,
            "status": blocker.status,
            "blocks": list(blocker.blocks),
            "reason": blocker.reason,
            "related_zones": list(blocker.related_zones),
            "related_actions": list(blocker.related_actions),
            "guidance_role": guidance_role,
        })
    return items


def build_ar_workflow_payload(state: RepairState) -> dict[str, Any]:
    """Build the complete AR workflow payload from a RepairState.

    Returns a JSON-serializable dict suitable for consumption by AR technician
    interfaces, workflow UIs, or API clients.

    This payload is advisory workflow intelligence. It does not certify repair
    completion, OEM compliance, or repair quality.
    """
    zones = build_zone_overlay_items(state)
    actions = build_action_guidance_items(state)
    qa_gates = build_qa_gate_items(state)
    blockers = build_blocker_items(state)

    active_zone_ids = [z["zone_id"] for z in zones if z["overlay_role"] == "active_repair_zone"]
    blocked_zone_ids = [z["zone_id"] for z in zones if z["overlay_role"] == "blocked_zone"]
    active_phase_ids = [p.name for p in state.phases if p.status == "in_progress"]
    blocked_phase_ids = [p.name for p in state.phases if p.status == "blocked"]
    open_blocker_count = sum(1 for b in blockers if b["status"] == "open")

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
            "open_blocker_count": open_blocker_count,
            "event_count": len(state.events),
            "next_action_count": len(state.next_recommended_actions),
        },
        "active_context": {
            "active_phase_ids": active_phase_ids,
            "active_zone_ids": active_zone_ids,
            "blocked_phase_ids": blocked_phase_ids,
            "blocked_zone_ids": blocked_zone_ids,
            "next_action_ids": list(state.next_recommended_actions),
        },
        "overlays": {
            "zones": zones,
            "actions": actions,
            "qa_gates": qa_gates,
            "blockers": blockers,
        },
        "source_state": {
            "schema_name": SOURCE_SCHEMA_NAME,
            "schema_version": SOURCE_SCHEMA_VERSION,
        },
    }
