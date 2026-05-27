"""
Workflow timeline module for RepairGraph repair state.

Builds ordered, deterministic timeline views of repair workflow events, phases,
and actions from a RepairState snapshot.

All outputs are advisory workflow intelligence and do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

from typing import Any

from repairgraph.state.blockers import get_open_blockers
from repairgraph.state.next_actions import get_next_action_objects
from repairgraph.state.schema import RepairState

_ADVISORY_NOTE = (
    "Timeline outputs are advisory workflow projections derived from RepairGraph "
    "procedure data and explicit state events. They do not certify repair "
    "completion, OEM compliance, or repair quality."
)


def build_event_timeline(state: RepairState) -> list[dict[str, Any]]:
    """Return an ordered list of event timeline entries from the event ledger.

    Entries are ordered by timestamp as recorded in the ledger (append order).
    Each entry includes all event fields plus a positional sequence number.
    """
    entries = []
    for seq, event in enumerate(state.events, start=1):
        entries.append({
            "seq": seq,
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "actor": event.actor,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "notes": event.notes,
            "evidence": event.evidence,
        })
    return entries


def build_phase_timeline(state: RepairState) -> list[dict[str, Any]]:
    """Return an ordered list of phase timeline entries sorted by phase number.

    Each entry reflects the current phase status and includes related actions,
    zones, and blocker references as advisory context.
    """
    phases_sorted = sorted(state.phases, key=lambda p: p.phase)
    entries = []

    for phase in phases_sorted:
        phase_block_id = f"phase:{phase.phase}"
        related_blockers = [
            b.blocker_id for b in state.blockers
            if phase_block_id in b.blocks
        ]
        advisory_notes = [
            b.reason for b in state.blockers
            if phase_block_id in b.blocks and b.reason
        ]

        entries.append({
            "phase": phase.phase,
            "name": phase.name,
            "label": phase.label,
            "status": phase.status,
            "active_zones": list(phase.active_zones),
            "completed_actions": list(phase.completed_actions),
            "pending_actions": list(phase.pending_actions),
            "blocked_by": list(phase.blocked_by),
            "related_blockers": related_blockers,
            "advisory_notes": advisory_notes,
        })

    return entries


def build_action_timeline(state: RepairState) -> list[dict[str, Any]]:
    """Return an ordered list of action timeline entries sorted by phase then action ID.

    Each entry reflects the current action status and includes zone references
    and associated QA gate IDs as advisory context.
    """
    actions_sorted = sorted(state.actions, key=lambda a: (a.phase, a.action_id))

    gate_by_phase: dict[int, list[str]] = {}
    for gate in state.qa_gates:
        if gate.related_phase is not None:
            gate_by_phase.setdefault(gate.related_phase, []).append(gate.gate_id)

    entries = []
    for action in actions_sorted:
        related_gates = gate_by_phase.get(action.phase, []) if action.requires_qa else []

        entries.append({
            "action_id": action.action_id,
            "phase": action.phase,
            "action_type": action.action_type,
            "target": action.target,
            "status": action.status,
            "zone_refs": list(action.zone_refs),
            "requires_qa": action.requires_qa,
            "related_qa_gates": related_gates,
            "evidence": action.evidence,
        })

    return entries


def summarize_timeline(state: RepairState) -> dict[str, Any]:
    """Return a compact advisory summary of the current workflow timeline state.

    Includes event counts, phase and action status breakdowns, open QA gates,
    open blockers, and next recommended actions.
    """
    active_phases = [p for p in state.phases if p.status == "in_progress"]
    completed_phases = [p for p in state.phases if p.status == "complete"]
    blocked_phases = [p for p in state.phases if p.status == "blocked"]

    completed_actions = [a for a in state.actions if a.status == "complete"]
    blocked_actions = [a for a in state.actions if a.status == "blocked"]
    in_progress_actions = [a for a in state.actions if a.status == "in_progress"]
    pending_actions = [a for a in state.actions if a.status == "pending"]

    open_qa_gates = [g for g in state.qa_gates if g.status in {"open", "in_review", "failed"}]
    blocking_qa_gates = [g for g in open_qa_gates if g.blocks_completion]

    open_blockers = get_open_blockers(state)
    critical_blockers = [b for b in open_blockers if b.severity == "critical"]

    next_action_objects = get_next_action_objects(state)

    return {
        "advisory": True,
        "advisory_note": _ADVISORY_NOTE,
        "total_events": len(state.events),
        "session": {
            "session_id": state.session.session_id,
            "status": state.session.status,
            "oem": state.session.oem,
            "year": state.session.year,
            "model": state.session.model,
        },
        "phases": {
            "total": len(state.phases),
            "active": len(active_phases),
            "completed": len(completed_phases),
            "blocked": len(blocked_phases),
            "active_phase_names": [p.name for p in active_phases],
        },
        "actions": {
            "total": len(state.actions),
            "completed": len(completed_actions),
            "in_progress": len(in_progress_actions),
            "blocked": len(blocked_actions),
            "pending": len(pending_actions),
        },
        "open_qa_gates": len(open_qa_gates),
        "blocking_qa_gates": len(blocking_qa_gates),
        "open_blockers": len(open_blockers),
        "critical_blockers": len(critical_blockers),
        "next_actions": [a.action_id for a in next_action_objects],
        "next_action_targets": [a.target for a in next_action_objects],
    }
