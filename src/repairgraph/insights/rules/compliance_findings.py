"""Compliance insight rules (corrosion, calibration)."""
from __future__ import annotations

from repairgraph.insights.schema import InsightFinding
from repairgraph.state.schema import RepairState


def corrosion_protection_blocked(state: RepairState) -> list[InsightFinding]:
    blocked = [
        p for p in state.phases
        if "corrosion" in p.name.lower() and p.status == "blocked"
    ]
    if not blocked:
        return []
    phase = blocked[0]
    blocked_by_str = ", ".join(phase.blocked_by) if phase.blocked_by else "upstream dependency"
    return [InsightFinding(
        finding_id="compliance_corrosion_phase_blocked",
        severity="high",
        category="compliance",
        title="Corrosion protection phase is blocked",
        explanation=(
            f"The {phase.label} phase cannot proceed — blocked by {blocked_by_str}. "
            "Skipping or delaying corrosion protection violates OEM procedures and may void warranty."
        ),
        recommended_action=(
            "Clear blockers for the corrosion protection phase before allowing repair to proceed. "
            "Do not apply body panels or topcoat until corrosion protection is documented and verified."
        ),
        supporting_evidence=(
            f"phase={phase.name}",
            f"blocked_by={blocked_by_str}",
        ),
        confidence="high",
    )]


def corrosion_qa_open(state: RepairState) -> list[InsightFinding]:
    gates = [
        g for g in state.qa_gates
        if "corrosion" in g.category.lower() and g.status in ("open", "in_review")
    ]
    if not gates:
        return []
    gate_ids = [g.gate_id for g in gates]
    return [InsightFinding(
        finding_id="compliance_corrosion_qa_open",
        severity="high",
        category="compliance",
        title=f"{len(gates)} corrosion protection QA gate{'s' if len(gates) > 1 else ''} open",
        explanation=(
            f"Corrosion protection check{'s' if len(gates) > 1 else ''} {', '.join(gate_ids)} "
            f"{'are' if len(gates) > 1 else 'is'} not yet verified. "
            "Missing corrosion documentation is a common cause of warranty denial and re-repair."
        ),
        recommended_action=(
            "Complete corrosion protection application per OEM spec and document with photos before closing gates. "
            "Gates to close: " + ", ".join(gate_ids)
        ),
        supporting_evidence=tuple(f"{g.gate_id}:{g.category}" for g in gates),
        confidence="high",
    )]


def calibration_assessment(state: RepairState) -> list[InsightFinding]:
    calibration_actions = [
        a for a in state.actions
        if "calibration" in a.action_type.lower() or "calibration" in a.target.lower()
    ]
    calibration_gates = [
        g for g in state.qa_gates
        if "calibration" in g.category.lower()
    ]
    if calibration_actions or calibration_gates:
        return []
    return [InsightFinding(
        finding_id="compliance_calibration_not_identified",
        severity="medium",
        category="compliance",
        title="No ADAS/sensor calibration identified in repair plan",
        explanation=(
            "No calibration actions or QA gates are present in this repair workflow. "
            "If structural or glass work has been performed, forward-facing cameras, radar, and parking sensors "
            "may require recalibration per OEM procedure."
        ),
        recommended_action=(
            "Confirm with OEM documentation whether any replaced or adjusted components require static or dynamic "
            "ADAS calibration. Add calibration to the workflow if required."
        ),
        supporting_evidence=(
            "calibration_actions=0",
            "calibration_qa_gates=0",
        ),
        confidence="medium",
    )]
