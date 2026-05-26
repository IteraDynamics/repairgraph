from __future__ import annotations

from copy import deepcopy

from repairgraph.state.schema import (
    ACTION_STATUSES,
    BLOCKER_STATUSES,
    PHASE_STATUSES,
    QA_GATE_STATUSES,
    SESSION_STATUSES,
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairEvent,
    RepairState,
    ZoneActivation,
)


ACTION_STATUS_BY_EVENT = {
    "action_started": "in_progress",
    "action_completed": "complete",
    "action_blocked": "blocked",
    "action_marked_not_applicable": "not_applicable",
}

QA_GATE_STATUS_BY_EVENT = {
    "qa_gate_opened": "open",
    "qa_gate_passed": "passed",
    "qa_gate_failed": "failed",
    "qa_gate_marked_not_applicable": "not_applicable",
}

BLOCKER_STATUS_BY_EVENT = {
    "blocker_added": "open",
    "blocker_resolved": "resolved",
}

SESSION_STATUS_BY_EVENT = {
    "session_started": "in_progress",
    "session_completed": "complete",
    "session_cancelled": "cancelled",
}

PHASE_STATUS_BY_EVENT = {
    "phase_started": "in_progress",
    "phase_completed": "complete",
}


def _phase_key(phase: PhaseState) -> str:
    return f"phase:{phase.phase}"


def _copy_state(state: RepairState) -> RepairState:
    return deepcopy(state)


def _find_action(state: RepairState, action_id: str) -> ActionState | None:
    return next((action for action in state.actions if action.action_id == action_id), None)


def _find_phase(state: RepairState, phase_id: str) -> PhaseState | None:
    for phase in state.phases:
        if phase_id in {_phase_key(phase), str(phase.phase), phase.name}:
            return phase
    return None


def _find_qa_gate(state: RepairState, gate_id: str) -> QAGateState | None:
    return next((gate for gate in state.qa_gates if gate.gate_id == gate_id), None)


def _find_blocker(state: RepairState, blocker_id: str) -> Blocker | None:
    return next((blocker for blocker in state.blockers if blocker.blocker_id == blocker_id), None)


def _zones_for_action(state: RepairState, action: ActionState) -> list[ZoneActivation]:
    zone_ids = set(action.zone_refs)
    return [zone for zone in state.zones if zone.zone_id in zone_ids]


def _set_session_status(state: RepairState, status: str) -> None:
    if status not in SESSION_STATUSES:
        raise ValueError(f"Invalid session status: {status}")
    state.session.status = status


def _set_phase_status(phase: PhaseState, status: str) -> None:
    if status not in PHASE_STATUSES:
        raise ValueError(f"Invalid phase status: {status}")
    phase.status = status


def _set_action_status(action: ActionState, status: str) -> None:
    if status not in ACTION_STATUSES:
        raise ValueError(f"Invalid action status: {status}")
    action.status = status


def _set_qa_gate_status(gate: QAGateState, status: str) -> None:
    if status not in QA_GATE_STATUSES:
        raise ValueError(f"Invalid QA gate status: {status}")
    gate.status = status


def _set_blocker_status(blocker: Blocker, status: str) -> None:
    if status not in BLOCKER_STATUSES:
        raise ValueError(f"Invalid blocker status: {status}")
    blocker.status = status


def _apply_session_event(state: RepairState, event: RepairEvent) -> None:
    status = SESSION_STATUS_BY_EVENT[event.event_type]
    _set_session_status(state, status)


def _apply_phase_event(state: RepairState, event: RepairEvent) -> None:
    phase = _find_phase(state, event.target_id)
    if phase is None:
        raise ValueError(f"Unknown phase target: {event.target_id}")

    status = PHASE_STATUS_BY_EVENT[event.event_type]
    _set_phase_status(phase, status)

    if status == "in_progress":
        _set_session_status(state, "in_progress")


def _apply_action_event(state: RepairState, event: RepairEvent) -> None:
    action = _find_action(state, event.target_id)
    if action is None:
        raise ValueError(f"Unknown action target: {event.target_id}")

    status = ACTION_STATUS_BY_EVENT[event.event_type]
    _set_action_status(action, status)

    phase = _find_phase(state, str(action.phase))
    if phase is not None:
        if status == "in_progress":
            _set_phase_status(phase, "in_progress")
            _set_session_status(state, "in_progress")

        if action.action_id in phase.pending_actions:
            phase.pending_actions.remove(action.action_id)

        if status == "complete" and action.action_id not in phase.completed_actions:
            phase.completed_actions.append(action.action_id)

        if status == "blocked" and action.action_id not in phase.blocked_by:
            phase.blocked_by.append(action.action_id)
            _set_phase_status(phase, "blocked")
            _set_session_status(state, "blocked")

        if status == "not_applicable" and action.action_id not in phase.completed_actions:
            phase.completed_actions.append(action.action_id)

    for zone in _zones_for_action(state, action):
        if status == "in_progress":
            zone.status = "active"
            zone.active_phase = action.phase
            if action.action_id not in zone.active_actions:
                zone.active_actions.append(action.action_id)
        elif status in {"complete", "not_applicable"}:
            if action.action_id in zone.active_actions:
                zone.active_actions.remove(action.action_id)
            if not zone.active_actions:
                zone.status = "complete"
        elif status == "blocked":
            zone.status = "blocked"
            if action.action_id not in zone.active_actions:
                zone.active_actions.append(action.action_id)


def _apply_qa_gate_event(state: RepairState, event: RepairEvent) -> None:
    gate = _find_qa_gate(state, event.target_id)
    if gate is None:
        raise ValueError(f"Unknown QA gate target: {event.target_id}")

    status = QA_GATE_STATUS_BY_EVENT[event.event_type]
    _set_qa_gate_status(gate, status)


def _apply_blocker_event(state: RepairState, event: RepairEvent) -> None:
    blocker = _find_blocker(state, event.target_id)
    if blocker is None:
        raise ValueError(f"Unknown blocker target: {event.target_id}")

    status = BLOCKER_STATUS_BY_EVENT[event.event_type]
    _set_blocker_status(blocker, status)


def _all_phase_actions_finished(state: RepairState, phase: PhaseState) -> bool:
    phase_actions = [action for action in state.actions if action.phase == phase.phase]
    if not phase_actions:
        return False

    return all(action.status in {"complete", "not_applicable"} for action in phase_actions)


def _has_open_blocker_for_phase(state: RepairState, phase: PhaseState) -> bool:
    phase_block_id = f"phase:{phase.phase}"
    return any(
        blocker.status == "open" and phase_block_id in blocker.blocks
        for blocker in state.blockers
    )


def _recompute_phase_completion(state: RepairState) -> None:
    for phase in state.phases:
        if phase.status == "blocked":
            continue
        if _has_open_blocker_for_phase(state, phase):
            phase.status = "blocked"
            continue
        if _all_phase_actions_finished(state, phase):
            phase.status = "complete"


def _has_blocking_open_qa_gate(state: RepairState) -> bool:
    return any(
        gate.blocks_completion and gate.status not in {"passed", "not_applicable"}
        for gate in state.qa_gates
    )


def _has_open_session_blocker(state: RepairState) -> bool:
    return any(
        blocker.status == "open" and "session_completion" in blocker.blocks
        for blocker in state.blockers
    )


def _all_phases_finished(state: RepairState) -> bool:
    return bool(state.phases) and all(
        phase.status in {"complete", "not_applicable"}
        for phase in state.phases
    )


def _recompute_session_status(state: RepairState) -> None:
    if state.session.status == "cancelled":
        return

    if _has_open_session_blocker(state) or _has_blocking_open_qa_gate(state):
        if state.session.status == "complete":
            state.session.status = "blocked"
        return

    if _all_phases_finished(state):
        state.session.status = "ready_for_review"


def _recompute_next_recommended_actions(state: RepairState) -> None:
    recommendations = []

    for phase in state.phases:
        if phase.status in {"complete", "not_applicable"}:
            continue

        for action_id in phase.pending_actions:
            action = _find_action(state, action_id)
            if action and action.status == "pending":
                recommendations.append(action_id)

        if recommendations:
            break

    state.next_recommended_actions = recommendations


def _apply_event(state: RepairState, event: RepairEvent) -> None:
    if event.event_type in SESSION_STATUS_BY_EVENT:
        _apply_session_event(state, event)
    elif event.event_type in PHASE_STATUS_BY_EVENT:
        _apply_phase_event(state, event)
    elif event.event_type in ACTION_STATUS_BY_EVENT:
        _apply_action_event(state, event)
    elif event.event_type in QA_GATE_STATUS_BY_EVENT:
        _apply_qa_gate_event(state, event)
    elif event.event_type in BLOCKER_STATUS_BY_EVENT:
        _apply_blocker_event(state, event)
    else:
        raise ValueError(f"Unsupported event type: {event.event_type}")


def project_repair_state(
    initial_state: RepairState,
    events: list[RepairEvent],
) -> RepairState:
    """
    Apply an append-only event ledger to an initial RepairState.

    The input state is not mutated. Events are applied in the order provided.
    The resulting state remains advisory and deterministic.
    """
    state = _copy_state(initial_state)

    for event in events:
        _apply_event(state, event)
        state.events.append(event)
        _recompute_phase_completion(state)
        _recompute_session_status(state)
        _recompute_next_recommended_actions(state)

    return state
