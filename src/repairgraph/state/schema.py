from dataclasses import dataclass, field
from typing import Any

SESSION_STATUSES = {"not_started", "in_progress", "blocked", "ready_for_review", "complete", "cancelled"}
PHASE_STATUSES = {"not_started", "in_progress", "blocked", "ready_for_review", "complete", "not_applicable"}
ACTION_STATUSES = {"pending", "in_progress", "complete", "blocked", "not_applicable", "needs_review"}
QA_GATE_STATUSES = {"open", "in_review", "passed", "failed", "not_applicable"}
ZONE_STATUSES = {"inactive", "pending", "active", "complete", "blocked"}
BLOCKER_STATUSES = {"open", "resolved"}
BLOCKER_SEVERITIES = {"low", "medium", "high", "critical"}
BLOCKER_TYPES = {"qa_gate", "dependency", "material_risk", "corrosion_requirement", "manual_hold", "documentation_required"}
EVENT_TYPES = {"session_started", "phase_started", "phase_completed", "action_started", "action_completed", "action_blocked", "action_marked_not_applicable", "qa_gate_opened", "qa_gate_passed", "qa_gate_failed", "qa_gate_marked_not_applicable", "blocker_added", "blocker_resolved", "session_completed", "session_cancelled"}
TARGET_TYPES = {"session", "phase", "action", "qa_gate", "blocker", "zone"}


def _validate(value: str, allowed: set[str], label: str) -> None:
    if value not in allowed:
        raise ValueError(f"Invalid {label}: {value}")


@dataclass(slots=True)
class RepairSession:
    session_id: str
    oem: str
    year: int
    model: str
    operation: str
    status: str
    current_phase: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        _validate(self.status, SESSION_STATUSES, "session status")


@dataclass(slots=True)
class PhaseState:
    phase: int
    name: str
    label: str
    status: str
    active_zones: list[str] = field(default_factory=list)
    completed_actions: list[str] = field(default_factory=list)
    pending_actions: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate(self.status, PHASE_STATUSES, "phase status")


@dataclass(slots=True)
class ActionState:
    action_id: str
    phase: int
    action_type: str
    target: str
    status: str
    zone_refs: list[str] = field(default_factory=list)
    requires_qa: bool = False
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _validate(self.status, ACTION_STATUSES, "action status")


@dataclass(slots=True)
class QAGateState:
    gate_id: str
    category: str
    priority: str
    status: str
    related_phase: int | None = None
    zone_refs: list[str] = field(default_factory=list)
    check: str | None = None
    blocks_completion: bool = True
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _validate(self.status, QA_GATE_STATUSES, "QA gate status")


@dataclass(slots=True)
class ZoneActivation:
    zone_id: str
    label: str
    status: str
    active_phase: int | None = None
    active_actions: list[str] = field(default_factory=list)
    material_classification: str | None = None
    risk_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate(self.status, ZONE_STATUSES, "zone status")


@dataclass(slots=True)
class Blocker:
    blocker_id: str
    type: str
    severity: str
    status: str
    blocks: list[str] = field(default_factory=list)
    reason: str | None = None
    related_zones: list[str] = field(default_factory=list)
    related_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate(self.type, BLOCKER_TYPES, "blocker type")
        _validate(self.severity, BLOCKER_SEVERITIES, "blocker severity")
        _validate(self.status, BLOCKER_STATUSES, "blocker status")


@dataclass(slots=True)
class RepairEvent:
    event_id: str
    timestamp: str
    event_type: str
    actor: str
    target_type: str
    target_id: str
    notes: str | None = None
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _validate(self.event_type, EVENT_TYPES, "event type")
        _validate(self.target_type, TARGET_TYPES, "target type")


@dataclass(slots=True)
class RepairState:
    session: RepairSession
    phases: list[PhaseState] = field(default_factory=list)
    actions: list[ActionState] = field(default_factory=list)
    qa_gates: list[QAGateState] = field(default_factory=list)
    zones: list[ZoneActivation] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    events: list[RepairEvent] = field(default_factory=list)
    next_recommended_actions: list[str] = field(default_factory=list)
    interpretation_note: str = (
        "Repair state outputs are advisory workflow projections derived "
        "from RepairGraph procedure data and explicit state events."
    )
