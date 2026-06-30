"""
Operational Planner v0.

Consumes an OperationalModel (and optionally a RootCauseAnalysis) and
produces a single deterministic OperationalPlan that answers:

    What is the highest-leverage action the shop should take next?

The planner is advisory. All outputs require verification by a qualified
technician against OEM procedures.

Algorithm
---------
1. Build PlannerCandidates from open QA gates, blockers, blocked phases,
   root causes, workflow recommendations, and missing evidence.
2. Score each candidate using documented deterministic weights.
3. Select the single highest-scoring candidate as next_best_action.
4. Compute expected unlocks, critical path, and action queue from that
   selection.

Scoring weights (documented)
----------------------------
Critical QA gate cleared             +100
High-priority QA gate cleared         +60
Medium-priority QA gate cleared        +20
Blocked phase unblocked               +50 each
Blocked action unblocked              +10 each
Downstream QA gates enabled            +8 each
Material / safety risk reduced         +40
Compliance risk reduced                +30
Evidence gap resolved                  +20
Workflow moves to next phase           +25
Already completed / redundant action  -100
Action still blocked                   -80
Requires unavailable evidence          -50
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from repairgraph.core.operational_model import OperationalModel
from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
)

# ---------------------------------------------------------------------------
# Scoring weights — documented here and tested
# ---------------------------------------------------------------------------

_W_CRITICAL_QA = 100
_W_HIGH_QA = 60
_W_MEDIUM_QA = 20
_W_PHASE_UNBLOCKED = 50
_W_ACTION_UNBLOCKED = 10
_W_DOWNSTREAM_QA = 8
_W_MATERIAL_SAFETY = 40
_W_COMPLIANCE = 30
_W_EVIDENCE_GAP = 20
_W_NEXT_PHASE = 25
_W_ALREADY_COMPLETE = -100
_W_STILL_BLOCKED = -80
_W_MISSING_EVIDENCE = -50

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_FALLBACK_ACTION = "Review repair packet completeness before proceeding."
_ADVISORY_NOTICE = (
    "Operational Planner outputs are advisory workflow intelligence. "
    "They do not certify repair completion, OEM compliance, or repair quality. "
    "All outputs require verification by a qualified technician against OEM procedures."
)


# ---------------------------------------------------------------------------
# Internal candidate objects
# ---------------------------------------------------------------------------

@dataclass
class PlannerCandidate:
    """A normalised action candidate considered by the planner."""
    candidate_id: str
    candidate_type: str          # qa_gate | blocker | phase | workflow | evidence | root_cause
    display_label: str
    source_entities: list[str] = field(default_factory=list)
    related_phase_ids: list[int] = field(default_factory=list)
    related_action_ids: list[str] = field(default_factory=list)
    related_qa_gate_ids: list[str] = field(default_factory=list)
    related_blocker_ids: list[str] = field(default_factory=list)
    related_findings: list[str] = field(default_factory=list)
    domain_context: str = ""
    advisory: str = ""
    # Resolved after scoring
    severity: str = "medium"
    earliest_phase: int = 999


@dataclass
class PlannerScore:
    """Computed leverage score for a single candidate."""
    candidate_id: str
    leverage_score: int
    severity: str
    earliest_phase: int
    downstream_unlock_count: int
    confidence: str


@dataclass
class PlannerUnlock:
    """Something that becomes available when the next best action is completed."""
    unlock_type: str      # phase | qa_gate | action | risk | finding
    label: str
    unlock_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "unlock_type": self.unlock_type,
            "label": self.label,
            "unlock_id": self.unlock_id,
        }


# ---------------------------------------------------------------------------
# Output objects
# ---------------------------------------------------------------------------

@dataclass
class NextBestAction:
    """The single highest-leverage action the shop should take next."""
    action_id: str
    display_label: str
    action_type: str
    domain_context: str = ""
    why_now: str = ""
    expected_unlocks: list[PlannerUnlock] = field(default_factory=list)
    risk_reduction: str = ""
    required_evidence: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    confidence: str = "medium"
    advisory_notice: str = _ADVISORY_NOTICE

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "display_label": self.display_label,
            "action_type": self.action_type,
            "domain_context": self.domain_context,
            "why_now": self.why_now,
            "expected_unlocks": [u.to_dict() for u in self.expected_unlocks],
            "risk_reduction": self.risk_reduction,
            "required_evidence": self.required_evidence,
            "blocked_by": self.blocked_by,
            "confidence": self.confidence,
            "advisory_notice": self.advisory_notice,
        }


@dataclass
class OperationalPlan:
    """Deterministic operational plan produced by the planner."""
    plan_id: str
    model_id: str
    generated_at: str
    overall_status: str
    next_best_action: NextBestAction
    action_queue: dict[str, list[str]]    # {"today": [...], "next": [...], "deferred": [...]}
    critical_path: list[str]
    expected_unlocks: list[PlannerUnlock]
    blocked_by: list[str]
    deferred_work: list[str]
    risk_reduction: str
    confidence: str
    supporting_evidence: list[str]
    advisory: str = _ADVISORY_NOTICE

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_id": self.model_id,
            "generated_at": self.generated_at,
            "overall_status": self.overall_status,
            "next_best_action": self.next_best_action.to_dict(),
            "action_queue": self.action_queue,
            "critical_path": self.critical_path,
            "expected_unlocks": [u.to_dict() for u in self.expected_unlocks],
            "blocked_by": self.blocked_by,
            "deferred_work": self.deferred_work,
            "risk_reduction": self.risk_reduction,
            "confidence": self.confidence,
            "supporting_evidence": self.supporting_evidence,
            "advisory": self.advisory,
        }


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _format_qa_label(gate: QAGateState) -> str:
    check = gate.check or gate.gate_id
    check = check.strip().rstrip(".")
    if not check.endswith("?") and not check.endswith(")"):
        check = check.rstrip(".") + "."
    return f"Clear QA gate: {check}"


def _format_blocker_label(blocker: Blocker) -> str:
    reason = blocker.reason or blocker.type.replace("_", " ").title()
    return f"Resolve: {reason.rstrip('.')}."


def _format_phase_label(phase: PhaseState) -> str:
    return f"Unblock phase: {phase.label}."


def _collect_open_qa_gates(state) -> list[tuple[QAGateState, PlannerCandidate]]:
    results = []
    for gate in state.qa_gates:
        if gate.status not in ("open", "in_review"):
            continue
        candidate = PlannerCandidate(
            candidate_id=f"qa:{gate.gate_id}",
            candidate_type="qa_gate",
            display_label=_format_qa_label(gate),
            source_entities=[gate.gate_id],
            related_phase_ids=[gate.related_phase] if gate.related_phase is not None else [],
            related_qa_gate_ids=[gate.gate_id],
            domain_context=gate.category.replace("_", " ").title(),
            severity=gate.priority,
            earliest_phase=gate.related_phase if gate.related_phase is not None else 999,
        )
        results.append((gate, candidate))
    return results


def _collect_open_blockers(state) -> list[tuple[Blocker, PlannerCandidate]]:
    results = []
    for blocker in state.blockers:
        if blocker.status != "open":
            continue
        # Derive earliest phase from related actions
        phase_ids: list[int] = []
        for action_id in blocker.related_actions:
            action = next((a for a in state.actions if a.action_id == action_id), None)
            if action:
                phase_ids.append(action.phase)
        candidate = PlannerCandidate(
            candidate_id=f"blocker:{blocker.blocker_id}",
            candidate_type="blocker",
            display_label=_format_blocker_label(blocker),
            source_entities=[blocker.blocker_id],
            related_action_ids=list(blocker.related_actions),
            related_blocker_ids=[blocker.blocker_id],
            domain_context=blocker.type.replace("_", " ").title(),
            severity=blocker.severity,
            earliest_phase=min(phase_ids) if phase_ids else 999,
        )
        results.append((blocker, candidate))
    return results


def _collect_blocked_phases(state) -> list[tuple[PhaseState, PlannerCandidate]]:
    results = []
    for phase in state.phases:
        if phase.status != "blocked":
            continue
        candidate = PlannerCandidate(
            candidate_id=f"phase:{phase.name}",
            candidate_type="phase",
            display_label=_format_phase_label(phase),
            source_entities=[phase.name],
            related_phase_ids=[phase.phase],
            domain_context=phase.label,
            severity="high",
            earliest_phase=phase.phase,
        )
        results.append((phase, candidate))
    return results


def _collect_workflow_recommendations(model: OperationalModel) -> list[PlannerCandidate]:
    results = []
    state = model.state
    if not state:
        return results
    for action_id in state.next_recommended_actions:
        action = next((a for a in state.actions if a.action_id == action_id), None)
        if not action:
            continue
        if action.status == "complete":
            continue
        label = f"{action.action_type.replace('_', ' ').title()}: {action.target}."
        candidate = PlannerCandidate(
            candidate_id=f"workflow:{action_id}",
            candidate_type="workflow",
            display_label=label,
            source_entities=[action_id],
            related_phase_ids=[action.phase],
            related_action_ids=[action_id],
            severity="medium",
            earliest_phase=action.phase,
        )
        results.append(candidate)
    return results


def _collect_evidence_gaps(model: OperationalModel) -> list[PlannerCandidate]:
    results = []
    missing = model.source_manifest.missing_roles
    for role in missing:
        candidate = PlannerCandidate(
            candidate_id=f"evidence:{role}",
            candidate_type="evidence",
            display_label=f"Obtain missing document: {role.replace('_', ' ').title()}.",
            source_entities=[role],
            severity="medium",
            earliest_phase=0,
        )
        results.append(candidate)
    return results


def _build_candidates(model: OperationalModel, rca=None) -> list[PlannerCandidate]:
    """Build the full list of planner candidates from all sources."""
    candidates: list[PlannerCandidate] = []
    state = model.state
    if not state:
        return candidates

    # Open QA gates (critical first, then high)
    for _gate, c in _collect_open_qa_gates(state):
        candidates.append(c)

    # Open blockers
    for _blocker, c in _collect_open_blockers(state):
        candidates.append(c)

    # Blocked phases
    for _phase, c in _collect_blocked_phases(state):
        candidates.append(c)

    # Workflow next actions
    candidates.extend(_collect_workflow_recommendations(model))

    # Evidence gaps
    candidates.extend(_collect_evidence_gaps(model))

    # Root causes (if provided) — add only if not already covered by QA/blocker
    if rca and hasattr(rca, "root_causes"):
        existing_ids = {c.candidate_id for c in candidates}
        for rc in rca.root_causes:
            cid = f"root_cause:{rc.root_cause_id}"
            if cid in existing_ids:
                continue
            label = rc.recommended_resolution or rc.title
            if not label.endswith("."):
                label = label + "."
            candidate = PlannerCandidate(
                candidate_id=cid,
                candidate_type="root_cause",
                display_label=label,
                source_entities=[rc.root_cause_id],
                related_findings=list(rc.impact.affected_findings),
                domain_context=rc.concern_display,
                severity=rc.priority,
                earliest_phase=0,
            )
            candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_candidate(candidate: PlannerCandidate, model: OperationalModel) -> PlannerScore:
    state = model.state
    score = 0
    downstream_unlocks = 0

    if candidate.candidate_type == "qa_gate":
        # Score based on gate priority
        gate_id = candidate.source_entities[0] if candidate.source_entities else ""
        gate = next((g for g in state.qa_gates if g.gate_id == gate_id), None) if state else None
        if gate:
            if gate.status == "passed":
                score += _W_ALREADY_COMPLETE
                return PlannerScore(
                    candidate_id=candidate.candidate_id,
                    leverage_score=score,
                    severity=candidate.severity,
                    earliest_phase=candidate.earliest_phase,
                    downstream_unlock_count=0,
                    confidence="low",
                )
            elif gate.priority == "critical":
                score += _W_CRITICAL_QA
            elif gate.priority == "high":
                score += _W_HIGH_QA
            else:
                score += _W_MEDIUM_QA

            # Count phases that become unblocked
            if state:
                for phase in state.phases:
                    if phase.status == "blocked" and (
                        gate.related_phase == phase.phase
                        or gate_id in phase.blocked_by
                    ):
                        score += _W_PHASE_UNBLOCKED
                        downstream_unlocks += 1

                # Count downstream QA gates in same phase
                if gate.related_phase is not None:
                    downstream_qa = [
                        g for g in state.qa_gates
                        if g.related_phase == gate.related_phase
                        and g.gate_id != gate_id
                        and g.status == "open"
                    ]
                    score += len(downstream_qa) * _W_DOWNSTREAM_QA
                    downstream_unlocks += len(downstream_qa)

            # Material/safety bonus
            cat = gate.category.lower()
            if "material" in cat or "joining" in cat or "structural" in cat:
                score += _W_MATERIAL_SAFETY
            if "compliance" in cat or "corrosion" in cat or "calibration" in cat:
                score += _W_COMPLIANCE

    elif candidate.candidate_type == "blocker":
        blocker_id = candidate.source_entities[0] if candidate.source_entities else ""
        blocker = next((b for b in state.blockers if b.blocker_id == blocker_id), None) if state else None
        if blocker:
            if blocker.status == "resolved":
                score += _W_ALREADY_COMPLETE
                return PlannerScore(
                    candidate_id=candidate.candidate_id,
                    leverage_score=score,
                    severity=candidate.severity,
                    earliest_phase=candidate.earliest_phase,
                    downstream_unlock_count=0,
                    confidence="low",
                )
            else:
                sev = blocker.severity
                if sev == "critical":
                    score += _W_CRITICAL_QA
                elif sev == "high":
                    score += _W_HIGH_QA
                else:
                    score += _W_MEDIUM_QA

                # Phases unblocked
                blocked_phase_set = {p for b_id in blocker.blocks for p_obj in state.phases if p_obj.name == b_id and p_obj.status == "blocked" for p in [p_obj.phase]}
                score += len(blocked_phase_set) * _W_PHASE_UNBLOCKED
                downstream_unlocks += len(blocked_phase_set)

                # Actions unblocked
                blocked_actions = [a for a in state.actions if a.action_id in blocker.related_actions and a.status == "blocked"]
                score += len(blocked_actions) * _W_ACTION_UNBLOCKED
                downstream_unlocks += len(blocked_actions)

                btype = blocker.type.lower()
                if "material" in btype:
                    score += _W_MATERIAL_SAFETY
                if "corrosion" in btype or "compliance" in btype:
                    score += _W_COMPLIANCE

    elif candidate.candidate_type == "phase":
        phase_name = candidate.source_entities[0] if candidate.source_entities else ""
        phase = next((p for p in state.phases if p.name == phase_name), None) if state else None
        if phase:
            if phase.status not in ("blocked",):
                score += _W_ALREADY_COMPLETE
            else:
                score += _W_NEXT_PHASE
                # Count actions in this phase that would unblock
                actions_in_phase = [a for a in state.actions if a.phase == phase.phase]
                score += min(len(actions_in_phase) * _W_ACTION_UNBLOCKED, 50)
                downstream_unlocks += len(actions_in_phase)

                # Check if resolving this phase would itself be blocked
                if phase.blocked_by:
                    score += _W_STILL_BLOCKED

    elif candidate.candidate_type == "workflow":
        action_id = candidate.source_entities[0] if candidate.source_entities else ""
        action = next((a for a in state.actions if a.action_id == action_id), None) if state else None
        if action:
            if action.status == "complete":
                score += _W_ALREADY_COMPLETE
                return PlannerScore(
                    candidate_id=candidate.candidate_id,
                    leverage_score=score,
                    severity=candidate.severity,
                    earliest_phase=candidate.earliest_phase,
                    downstream_unlock_count=0,
                    confidence="low",
                )
            elif action.status == "blocked":
                score += _W_STILL_BLOCKED
            else:
                score += _W_NEXT_PHASE  # workflow recommendation bonus

    elif candidate.candidate_type == "evidence":
        score += _W_EVIDENCE_GAP
        # Penalty if missing evidence blocks completion
        if model.source_manifest.readiness in ("incomplete", "unprocessable"):
            score += _W_COMPLIANCE  # resolution is meaningful

    elif candidate.candidate_type == "root_cause":
        # Root cause contributes through its findings
        score += _W_COMPLIANCE
        score += len(candidate.related_findings) * 5

    # Confidence level
    confidence = "high" if score >= 100 else "medium" if score >= 50 else "low"

    return PlannerScore(
        candidate_id=candidate.candidate_id,
        leverage_score=score,
        severity=candidate.severity,
        earliest_phase=candidate.earliest_phase,
        downstream_unlock_count=downstream_unlocks,
        confidence=confidence,
    )


def _sort_key(pair: tuple[PlannerCandidate, PlannerScore]) -> tuple:
    c, s = pair
    sev_rank = _PRIORITY_ORDER.get(s.severity, 3)
    conf_rank = {"high": 0, "medium": 1, "low": 2}.get(s.confidence, 2)
    return (-s.leverage_score, sev_rank, s.earliest_phase, -s.downstream_unlock_count, conf_rank)


# ---------------------------------------------------------------------------
# Expected unlocks
# ---------------------------------------------------------------------------

def _compute_unlocks(candidate: PlannerCandidate, model: OperationalModel) -> list[PlannerUnlock]:
    unlocks: list[PlannerUnlock] = []
    state = model.state
    if not state:
        return unlocks

    if candidate.candidate_type == "qa_gate":
        gate_id = candidate.source_entities[0] if candidate.source_entities else ""
        gate = next((g for g in state.qa_gates if g.gate_id == gate_id), None)
        if gate and gate.related_phase is not None:
            phase = next((p for p in state.phases if p.phase == gate.related_phase), None)
            if phase and phase.status == "blocked":
                unlocks.append(PlannerUnlock("phase", phase.label, phase.name))

            downstream_qa = [
                g for g in state.qa_gates
                if g.related_phase == gate.related_phase
                and g.gate_id != gate_id
                and g.status == "open"
            ]
            for dq in downstream_qa:
                label = dq.check or dq.gate_id
                unlocks.append(PlannerUnlock("qa_gate", label, dq.gate_id))

    elif candidate.candidate_type == "blocker":
        blocker_id = candidate.source_entities[0] if candidate.source_entities else ""
        blocker = next((b for b in state.blockers if b.blocker_id == blocker_id), None)
        if blocker:
            for block_target in blocker.blocks:
                phase = next((p for p in state.phases if p.name == block_target), None)
                if phase:
                    unlocks.append(PlannerUnlock("phase", phase.label, phase.name))
                action = next((a for a in state.actions if a.action_id == block_target), None)
                if action:
                    label = f"{action.action_type.replace('_', ' ').title()}: {action.target}"
                    unlocks.append(PlannerUnlock("action", label, action.action_id))

            for action_id in blocker.related_actions:
                action = next((a for a in state.actions if a.action_id == action_id), None)
                if action and action.status == "blocked":
                    label = f"{action.action_type.replace('_', ' ').title()}: {action.target}"
                    u = PlannerUnlock("action", label, action.action_id)
                    if u.label not in {x.label for x in unlocks}:
                        unlocks.append(u)

    elif candidate.candidate_type == "phase":
        phase_name = candidate.source_entities[0] if candidate.source_entities else ""
        phase = next((p for p in state.phases if p.name == phase_name), None)
        if phase:
            actions_in_phase = [a for a in state.actions if a.phase == phase.phase]
            for a in actions_in_phase:
                label = f"{a.action_type.replace('_', ' ').title()}: {a.target}"
                unlocks.append(PlannerUnlock("action", label, a.action_id))

    elif candidate.candidate_type == "evidence":
        unlocks.append(PlannerUnlock("finding", "Repair packet completeness", ""))

    return unlocks


# ---------------------------------------------------------------------------
# Critical path
# ---------------------------------------------------------------------------

def _build_critical_path(
    best: PlannerCandidate,
    candidates: list[PlannerCandidate],
    scores: dict[str, PlannerScore],
    model: OperationalModel,
) -> list[str]:
    """Return an ordered list of human-readable steps forming the critical path."""
    path: list[str] = []
    state = model.state
    if not state:
        return [best.display_label]

    # Start with next best action
    path.append(best.display_label)

    # Add downstream steps in phase order
    sorted_phases = sorted(state.phases, key=lambda p: p.phase)
    for phase in sorted_phases:
        if phase.status == "blocked":
            entry = f"Unblock and resume: {phase.label}."
            if entry not in path:
                path.append(entry)
        elif phase.status in ("not_started", "in_progress"):
            # Next recommended actions in this phase
            for action_id in state.next_recommended_actions:
                action = next((a for a in state.actions if a.action_id == action_id and a.phase == phase.phase), None)
                if action and action.status not in ("complete", "not_applicable"):
                    entry = f"{action.action_type.replace('_', ' ').title()}: {action.target}."
                    if entry not in path:
                        path.append(entry)

    # Add open high-priority QA gates not yet in path
    for gate in sorted(state.qa_gates, key=lambda g: (_PRIORITY_ORDER.get(g.priority, 3), g.related_phase or 999)):
        if gate.status in ("open", "in_review") and gate.blocks_completion:
            label = f"Clear QA gate: {gate.check or gate.gate_id}."
            if label not in path:
                path.append(label)

    return path[:8]  # Keep it short and actionable


# ---------------------------------------------------------------------------
# Action queue
# ---------------------------------------------------------------------------

def _build_action_queue(
    best: PlannerCandidate,
    candidates: list[PlannerCandidate],
    scores: dict[str, PlannerScore],
    model: OperationalModel,
) -> dict[str, list[str]]:
    today: list[str] = [best.display_label]
    next_up: list[str] = []
    deferred: list[str] = []

    state = model.state
    if not state:
        return {"today": today, "next": next_up, "deferred": deferred}

    # Add up to 2 more for "today" from top scored candidates
    top_candidates = [
        c for c in candidates
        if c.candidate_id != best.candidate_id
        and scores.get(c.candidate_id, PlannerScore(c.candidate_id, -999, "low", 999, 0, "low")).leverage_score > 0
    ]
    top_candidates.sort(key=lambda c: _sort_key((c, scores.get(c.candidate_id, PlannerScore(c.candidate_id, 0, "low", 999, 0, "low")))))

    for c in top_candidates[:2]:
        today.append(c.display_label)

    for c in top_candidates[2:5]:
        next_up.append(c.display_label)

    # Completed actions are deferred (nothing to do)
    for action in state.actions:
        if action.status == "complete":
            label = f"{action.action_type.replace('_', ' ').title()}: {action.target} (complete)."
            deferred.append(label)

    return {"today": today, "next": next_up, "deferred": deferred[:5]}


# ---------------------------------------------------------------------------
# Why now / risk reduction copy
# ---------------------------------------------------------------------------

def _build_why_now(candidate: PlannerCandidate, model: OperationalModel, score: PlannerScore) -> str:
    state = model.state
    if not state:
        return "This is the highest-leverage unresolved item."

    reasons: list[str] = []

    if candidate.candidate_type == "qa_gate":
        gate_id = candidate.source_entities[0] if candidate.source_entities else ""
        gate = next((g for g in state.qa_gates if g.gate_id == gate_id), None)
        if gate:
            if gate.priority == "critical":
                reasons.append("This is the highest-priority blocking QA gate.")
            elif gate.priority == "high":
                reasons.append("This is a high-priority blocking QA gate.")
            if gate.related_phase is not None:
                phase = next((p for p in state.phases if p.phase == gate.related_phase), None)
                if phase and phase.status == "blocked":
                    reasons.append(f"Clearing it unblocks the '{phase.label}' phase.")
            downstream_count = len([
                g for g in state.qa_gates
                if g.related_phase == gate.related_phase
                and g.gate_id != gate_id
                and g.status == "open"
            ])
            if downstream_count > 0:
                reasons.append(f"It enables {downstream_count} downstream QA gate{'s' if downstream_count != 1 else ''} to proceed.")

    elif candidate.candidate_type == "blocker":
        blocker_id = candidate.source_entities[0] if candidate.source_entities else ""
        blocker = next((b for b in state.blockers if b.blocker_id == blocker_id), None)
        if blocker:
            reasons.append(f"This {blocker.severity}-severity blocker is preventing forward progress.")
            if blocker.blocks:
                count = len(blocker.blocks)
                reasons.append(f"Resolving it unblocks {count} downstream item{'s' if count != 1 else ''}.")

    elif candidate.candidate_type == "phase":
        reasons.append("This phase is blocked and is holding up downstream work.")

    elif candidate.candidate_type == "workflow":
        reasons.append("This is the next recommended workflow action.")

    elif candidate.candidate_type == "evidence":
        reasons.append("Missing documentation is limiting the review's confidence.")

    if score.downstream_unlock_count > 0:
        reasons.append(
            f"Completing this action unlocks {score.downstream_unlock_count} "
            f"downstream item{'s' if score.downstream_unlock_count != 1 else ''}."
        )

    return " ".join(reasons) if reasons else "This is the highest-leverage unresolved item."


def _build_risk_reduction(candidate: PlannerCandidate, model: OperationalModel) -> str:
    risks: list[str] = []
    ctx = model.domain_context.context_data
    repair = ctx.get("repair", {})
    systems = ctx.get("systems", {})

    if candidate.candidate_type in ("qa_gate", "blocker"):
        cat = candidate.domain_context.lower()
        if "material" in cat or "join" in cat or "structural" in cat:
            risks.append("structural non-compliance risk")
        if "corrosion" in cat:
            risks.append("corrosion warranty risk")
        if "calibration" in cat:
            risks.append("calibration certification risk")
        if "compliance" in cat:
            risks.append("compliance documentation risk")
    elif candidate.candidate_type == "evidence":
        risks.append("documentation gap risk")
        risks.append("downstream rework risk")

    if not risks:
        risks.append("operational delay risk")

    return "Reduces: " + ", ".join(risks) + "."


def _derive_overall_status(model: OperationalModel) -> str:
    if model.insights:
        return model.insights.overall_status
    if model.state:
        open_blockers = [b for b in model.state.blockers if b.status == "open"]
        if open_blockers:
            return "blocked"
        blocked_phases = [p for p in model.state.phases if p.status == "blocked"]
        if blocked_phases:
            return "at_risk"
    return model.workflow.workflow_readiness


def _derive_confidence(score: int, candidate_type: str) -> str:
    if score >= 100:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _collect_supporting_evidence(model: OperationalModel) -> list[str]:
    items: list[str] = []
    for ev in model.evidence.evidence_items[:5]:
        if isinstance(ev, dict):
            label = ev.get("label") or ev.get("description") or str(ev)
            items.append(str(label))
    return items


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_operational_plan(model: OperationalModel, rca=None) -> OperationalPlan:
    """Produce a deterministic OperationalPlan from an OperationalModel.

    Args:
        model: The compiled OperationalModel.
        rca:   Optional RootCauseAnalysis. If provided, root causes are used
               as additional candidate sources.

    Returns:
        An OperationalPlan with next_best_action, critical path, and action queue.
    """
    plan_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()
    overall_status = _derive_overall_status(model)

    # Step 1: build candidates
    candidates = _build_candidates(model, rca)

    # Step 2: score candidates
    scores: dict[str, PlannerScore] = {}
    for c in candidates:
        scores[c.candidate_id] = _score_candidate(c, model)

    # Step 3: sort and select
    scored_pairs = [(c, scores[c.candidate_id]) for c in candidates]
    scored_pairs.sort(key=_sort_key)

    if scored_pairs and scored_pairs[0][1].leverage_score > 0:
        best_candidate, best_score = scored_pairs[0]
    else:
        # Fallback
        best_candidate = PlannerCandidate(
            candidate_id="fallback",
            candidate_type="workflow",
            display_label=_FALLBACK_ACTION,
            severity="low",
            earliest_phase=999,
        )
        best_score = PlannerScore(
            candidate_id="fallback",
            leverage_score=0,
            severity="low",
            earliest_phase=999,
            downstream_unlock_count=0,
            confidence="low",
        )

    # Step 4: compute unlocks, critical path, queue
    unlocks = _compute_unlocks(best_candidate, model)
    critical_path = _build_critical_path(best_candidate, candidates, scores, model)
    action_queue = _build_action_queue(best_candidate, candidates, scores, model)
    why_now = _build_why_now(best_candidate, model, best_score)
    risk_reduction = _build_risk_reduction(best_candidate, model)
    confidence = _derive_confidence(best_score.leverage_score, best_candidate.candidate_type)

    # Collect overall blocked_by
    blocked_by: list[str] = []
    if model.state:
        for b in model.state.blockers:
            if b.status == "open" and b.reason:
                blocked_by.append(b.reason)

    # Deferred work = completed actions + deferred queue items
    deferred_work = action_queue.get("deferred", [])

    next_best = NextBestAction(
        action_id=best_candidate.candidate_id,
        display_label=best_candidate.display_label,
        action_type=best_candidate.candidate_type,
        domain_context=best_candidate.domain_context,
        why_now=why_now,
        expected_unlocks=unlocks,
        risk_reduction=risk_reduction,
        blocked_by=best_candidate.related_blocker_ids,
        confidence=confidence,
    )

    return OperationalPlan(
        plan_id=plan_id,
        model_id=model.metadata.model_id,
        generated_at=generated_at,
        overall_status=overall_status,
        next_best_action=next_best,
        action_queue=action_queue,
        critical_path=critical_path,
        expected_unlocks=unlocks,
        blocked_by=blocked_by,
        deferred_work=deferred_work,
        risk_reduction=risk_reduction,
        confidence=confidence,
        supporting_evidence=_collect_supporting_evidence(model),
        advisory=_ADVISORY_NOTICE,
    )
