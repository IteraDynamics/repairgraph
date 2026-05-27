"""
State replay module for RepairGraph workflow execution.

Provides incremental event-by-event state projection and state diffing utilities
for operational inspection and debugging of repair workflow progression.

All functions are deterministic and side-effect free. The input state is never mutated.

All outputs are advisory workflow intelligence and do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from repairgraph.state.project import project_repair_state
from repairgraph.state.schema import RepairEvent, RepairState


def replay_repair_state(
    initial_state: RepairState,
    events: list[RepairEvent],
) -> list[RepairState]:
    """Project state incrementally, returning one RepairState snapshot per event.

    The initial state is not mutated. Each snapshot is a deep copy representing
    the accumulated state after applying events 0..n. Snapshots are deterministic
    and ordered by event application sequence.

    Returns an empty list if events is empty.
    """
    snapshots: list[RepairState] = []
    current = deepcopy(initial_state)

    for event in events:
        current = project_repair_state(current, [event])
        snapshots.append(deepcopy(current))

    return snapshots


def build_state_diff(
    previous_state: RepairState,
    current_state: RepairState,
) -> dict[str, Any]:
    """Detect changes between two RepairState snapshots.

    Returns a dict of changed entity types. Keys are only present when that
    entity type has at least one change. Returns an empty dict when no changes
    are detected.

    Detects changes in:
    - session status
    - phase statuses
    - action statuses
    - zone statuses
    - QA gate statuses
    - blocker statuses
    - next recommended actions
    """
    diff: dict[str, Any] = {}

    if previous_state.session.status != current_state.session.status:
        diff["session_status"] = {
            "previous": previous_state.session.status,
            "current": current_state.session.status,
        }

    prev_phase_map = {p.name: p for p in previous_state.phases}
    phase_changes: dict[str, Any] = {}
    for curr_phase in current_state.phases:
        prev_phase = prev_phase_map.get(curr_phase.name)
        if prev_phase is not None and prev_phase.status != curr_phase.status:
            phase_changes[curr_phase.name] = {
                "previous_status": prev_phase.status,
                "current_status": curr_phase.status,
            }
    if phase_changes:
        diff["phases"] = phase_changes

    prev_action_map = {a.action_id: a for a in previous_state.actions}
    action_changes: dict[str, Any] = {}
    for curr_action in current_state.actions:
        prev_action = prev_action_map.get(curr_action.action_id)
        if prev_action is not None and prev_action.status != curr_action.status:
            action_changes[curr_action.action_id] = {
                "previous_status": prev_action.status,
                "current_status": curr_action.status,
            }
    if action_changes:
        diff["actions"] = action_changes

    prev_zone_map = {z.zone_id: z for z in previous_state.zones}
    zone_changes: dict[str, Any] = {}
    for curr_zone in current_state.zones:
        prev_zone = prev_zone_map.get(curr_zone.zone_id)
        if prev_zone is not None and prev_zone.status != curr_zone.status:
            zone_changes[curr_zone.zone_id] = {
                "previous_status": prev_zone.status,
                "current_status": curr_zone.status,
            }
    if zone_changes:
        diff["zones"] = zone_changes

    prev_gate_map = {g.gate_id: g for g in previous_state.qa_gates}
    gate_changes: dict[str, Any] = {}
    for curr_gate in current_state.qa_gates:
        prev_gate = prev_gate_map.get(curr_gate.gate_id)
        if prev_gate is not None and prev_gate.status != curr_gate.status:
            gate_changes[curr_gate.gate_id] = {
                "previous_status": prev_gate.status,
                "current_status": curr_gate.status,
            }
    if gate_changes:
        diff["qa_gates"] = gate_changes

    prev_blocker_map = {b.blocker_id: b for b in previous_state.blockers}
    blocker_changes: dict[str, Any] = {}
    for curr_blocker in current_state.blockers:
        prev_blocker = prev_blocker_map.get(curr_blocker.blocker_id)
        if prev_blocker is not None and prev_blocker.status != curr_blocker.status:
            blocker_changes[curr_blocker.blocker_id] = {
                "previous_status": prev_blocker.status,
                "current_status": curr_blocker.status,
            }
    if blocker_changes:
        diff["blockers"] = blocker_changes

    prev_next = list(previous_state.next_recommended_actions)
    curr_next = list(current_state.next_recommended_actions)
    if prev_next != curr_next:
        prev_set = set(prev_next)
        curr_set = set(curr_next)
        diff["next_recommended_actions"] = {
            "previous": prev_next,
            "current": curr_next,
            "added": [a for a in curr_next if a not in prev_set],
            "removed": [a for a in prev_next if a not in curr_set],
        }

    return diff


def summarize_state_diff(diff: dict[str, Any]) -> dict[str, Any]:
    """Produce a human-readable summary of a state diff.

    Returns counts, affected entity types, and a list of change descriptions
    for operational inspection.
    """
    change_labels: list[str] = []

    if "session_status" in diff:
        s = diff["session_status"]
        change_labels.append(f"session: {s['previous']} → {s['current']}")

    for phase_name, change in diff.get("phases", {}).items():
        change_labels.append(
            f"phase {phase_name}: {change['previous_status']} → {change['current_status']}"
        )

    for action_id, change in diff.get("actions", {}).items():
        change_labels.append(
            f"action {action_id}: {change['previous_status']} → {change['current_status']}"
        )

    for zone_id, change in diff.get("zones", {}).items():
        change_labels.append(
            f"zone {zone_id}: {change['previous_status']} → {change['current_status']}"
        )

    for gate_id, change in diff.get("qa_gates", {}).items():
        change_labels.append(
            f"qa_gate {gate_id}: {change['previous_status']} → {change['current_status']}"
        )

    for blocker_id, change in diff.get("blockers", {}).items():
        change_labels.append(
            f"blocker {blocker_id}: {change['previous_status']} → {change['current_status']}"
        )

    if "next_recommended_actions" in diff:
        nra = diff["next_recommended_actions"]
        if nra["added"]:
            change_labels.append(f"next_actions added: {nra['added']}")
        if nra["removed"]:
            change_labels.append(f"next_actions removed: {nra['removed']}")

    return {
        "change_count": len(change_labels),
        "changed_entities": list(diff.keys()),
        "changes": change_labels,
        "has_session_change": "session_status" in diff,
        "has_phase_changes": "phases" in diff,
        "has_action_changes": "actions" in diff,
        "has_zone_changes": "zones" in diff,
        "has_qa_gate_changes": "qa_gates" in diff,
        "has_blocker_changes": "blockers" in diff,
        "has_next_action_changes": "next_recommended_actions" in diff,
    }
