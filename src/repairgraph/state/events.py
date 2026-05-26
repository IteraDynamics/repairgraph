from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from repairgraph.state.schema import RepairEvent


EVENT_TARGET_COMPATIBILITY = {
    "session_started": {"session"},
    "session_completed": {"session"},
    "session_cancelled": {"session"},
    "phase_started": {"phase"},
    "phase_completed": {"phase"},
    "action_started": {"action"},
    "action_completed": {"action"},
    "action_blocked": {"action"},
    "action_marked_not_applicable": {"action"},
    "qa_gate_opened": {"qa_gate"},
    "qa_gate_passed": {"qa_gate"},
    "qa_gate_failed": {"qa_gate"},
    "qa_gate_marked_not_applicable": {"qa_gate"},
    "blocker_added": {"blocker"},
    "blocker_resolved": {"blocker"},
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_event_id() -> str:
    return f"evt_{uuid4().hex}"


def validate_event_target(event_type: str, target_type: str) -> None:
    allowed_targets = EVENT_TARGET_COMPATIBILITY.get(event_type)

    if allowed_targets is None:
        raise ValueError(f"Invalid event type: {event_type}")

    if target_type not in allowed_targets:
        allowed = ", ".join(sorted(allowed_targets))
        raise ValueError(
            f"Event type {event_type!r} is not compatible with target type "
            f"{target_type!r}; expected one of: {allowed}"
        )


def make_repair_event(
    *,
    event_type: str,
    actor: str,
    target_type: str,
    target_id: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    validate_event_target(event_type, target_type)

    return RepairEvent(
        event_id=event_id or make_event_id(),
        timestamp=timestamp or utc_now_iso(),
        event_type=event_type,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        notes=notes,
        evidence=evidence,
    )


def session_started_event(
    *,
    session_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="session_started",
        actor=actor,
        target_type="session",
        target_id=session_id,
        notes=notes,
        evidence=evidence,
    )


def session_completed_event(
    *,
    session_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="session_completed",
        actor=actor,
        target_type="session",
        target_id=session_id,
        notes=notes,
        evidence=evidence,
    )


def phase_started_event(
    *,
    phase_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="phase_started",
        actor=actor,
        target_type="phase",
        target_id=phase_id,
        notes=notes,
        evidence=evidence,
    )


def phase_completed_event(
    *,
    phase_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="phase_completed",
        actor=actor,
        target_type="phase",
        target_id=phase_id,
        notes=notes,
        evidence=evidence,
    )


def action_started_event(
    *,
    action_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="action_started",
        actor=actor,
        target_type="action",
        target_id=action_id,
        notes=notes,
        evidence=evidence,
    )


def action_completed_event(
    *,
    action_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="action_completed",
        actor=actor,
        target_type="action",
        target_id=action_id,
        notes=notes,
        evidence=evidence,
    )


def action_blocked_event(
    *,
    action_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="action_blocked",
        actor=actor,
        target_type="action",
        target_id=action_id,
        notes=notes,
        evidence=evidence,
    )


def action_marked_not_applicable_event(
    *,
    action_id: str,
    actor: str,
    reason: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="action_marked_not_applicable",
        actor=actor,
        target_type="action",
        target_id=action_id,
        notes=reason,
        evidence=evidence,
    )


def qa_gate_opened_event(
    *,
    gate_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="qa_gate_opened",
        actor=actor,
        target_type="qa_gate",
        target_id=gate_id,
        notes=notes,
        evidence=evidence,
    )


def qa_gate_passed_event(
    *,
    gate_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="qa_gate_passed",
        actor=actor,
        target_type="qa_gate",
        target_id=gate_id,
        notes=notes,
        evidence=evidence,
    )


def qa_gate_failed_event(
    *,
    gate_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="qa_gate_failed",
        actor=actor,
        target_type="qa_gate",
        target_id=gate_id,
        notes=notes,
        evidence=evidence,
    )


def qa_gate_marked_not_applicable_event(
    *,
    gate_id: str,
    actor: str,
    reason: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="qa_gate_marked_not_applicable",
        actor=actor,
        target_type="qa_gate",
        target_id=gate_id,
        notes=reason,
        evidence=evidence,
    )


def blocker_added_event(
    *,
    blocker_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="blocker_added",
        actor=actor,
        target_type="blocker",
        target_id=blocker_id,
        notes=notes,
        evidence=evidence,
    )


def blocker_resolved_event(
    *,
    blocker_id: str,
    actor: str,
    event_id: str | None = None,
    timestamp: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
) -> RepairEvent:
    return make_repair_event(
        event_id=event_id,
        timestamp=timestamp,
        event_type="blocker_resolved",
        actor=actor,
        target_type="blocker",
        target_id=blocker_id,
        notes=notes,
        evidence=evidence,
    )
