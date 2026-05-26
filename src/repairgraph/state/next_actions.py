"""
Next-action utilities for RepairState.

All functions are advisory, deterministic, side-effect-free, and do not mutate state.
"""
from __future__ import annotations

from typing import Any

from repairgraph.state.blockers import get_session_completion_blockers
from repairgraph.state.schema import ActionState, RepairState

_ADVISORY_NOTE = (
    "Next recommended actions are advisory workflow projections. "
    "Verify all steps against OEM procedures before proceeding."
)


def get_next_actions(state: RepairState) -> list[str]:
    """Return the list of next recommended action IDs."""
    return list(state.next_recommended_actions)


def get_next_action_objects(state: RepairState) -> list[ActionState]:
    """Resolve next recommended action IDs to ActionState objects.

    IDs that do not match any action in the state are silently skipped.
    """
    action_map = {a.action_id: a for a in state.actions}
    return [
        action_map[action_id]
        for action_id in state.next_recommended_actions
        if action_id in action_map
    ]


def summarize_next_actions(state: RepairState) -> dict[str, Any]:
    """Return an advisory summary of next recommended actions with blocker context."""
    action_objects = get_next_action_objects(state)
    session_completion_blocked = bool(get_session_completion_blockers(state))

    current_phase: int | None = None
    if action_objects:
        current_phase = action_objects[0].phase

    phase_blocked = False
    if current_phase is not None:
        for phase in state.phases:
            if phase.phase == current_phase and phase.status == "blocked":
                phase_blocked = True
                break

    return {
        "next_action_count": len(action_objects),
        "next_action_ids": [a.action_id for a in action_objects],
        "next_action_targets": [a.target for a in action_objects],
        "current_phase": current_phase,
        "phase_blocked": phase_blocked,
        "session_completion_blocked": session_completion_blocked,
        "advisory": True,
        "advisory_note": _ADVISORY_NOTE,
    }
