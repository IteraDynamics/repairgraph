"""
Blocker inspection utilities for RepairState.

All functions are deterministic, side-effect-free, and do not mutate state.
"""
from __future__ import annotations

from typing import Any

from repairgraph.state.schema import Blocker, RepairState


def get_open_blockers(state: RepairState) -> list[Blocker]:
    """Return all open (unresolved) blockers."""
    return [b for b in state.blockers if b.status == "open"]


def get_blockers_for_phase(state: RepairState, phase_id: str) -> list[Blocker]:
    """Return all open blockers that reference the given phase.

    Accepts phase_id as a bare number ("4"), a prefixed key ("phase:4"),
    or a phase name that matches what blockers use internally.
    """
    phase_block_id = (
        phase_id if phase_id.startswith("phase:") else f"phase:{phase_id}"
    )
    return [
        b
        for b in state.blockers
        if b.status == "open" and phase_block_id in b.blocks
    ]


def get_session_completion_blockers(state: RepairState) -> list[Blocker]:
    """Return all open blockers that block session completion."""
    return [
        b
        for b in state.blockers
        if b.status == "open" and "session_completion" in b.blocks
    ]


def has_session_blockers(state: RepairState) -> bool:
    """Return True if any open blocker blocks session completion."""
    return bool(get_session_completion_blockers(state))


def summarize_blockers(state: RepairState) -> dict[str, Any]:
    """Return a summary dict of blocker state grouped by severity and type."""
    open_blockers = get_open_blockers(state)
    session_blockers = get_session_completion_blockers(state)

    open_by_severity: dict[str, list[str]] = {}
    open_by_type: dict[str, list[str]] = {}

    for blocker in open_blockers:
        open_by_severity.setdefault(blocker.severity, []).append(blocker.blocker_id)
        open_by_type.setdefault(blocker.type, []).append(blocker.blocker_id)

    return {
        "total_blockers": len(state.blockers),
        "open_blockers": len(open_blockers),
        "resolved_blockers": len(state.blockers) - len(open_blockers),
        "session_completion_blocked": has_session_blockers(state),
        "open_by_severity": open_by_severity,
        "open_by_type": open_by_type,
        "open_blocker_ids": [b.blocker_id for b in open_blockers],
        "session_blocker_ids": [b.blocker_id for b in session_blockers],
    }
