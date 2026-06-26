"""Workflow / phase blocker insight rules."""
from __future__ import annotations

from repairgraph.insights.schema import InsightFinding
from repairgraph.state.schema import RepairState


def blocked_phases(state: RepairState) -> list[InsightFinding]:
    findings = []
    for phase in state.phases:
        if phase.status == "blocked":
            blocked_by_str = ", ".join(phase.blocked_by) if phase.blocked_by else "unknown dependency"
            findings.append(InsightFinding(
                finding_id=f"workflow_phase_blocked_{phase.name}",
                severity="high",
                category="workflow",
                title=f"Phase blocked: {phase.label}",
                explanation=(
                    f"Phase {phase.phase} ({phase.label}) cannot proceed. "
                    f"Blocked by: {blocked_by_str}."
                ),
                recommended_action=(
                    f"Resolve blockers for {phase.label} before assigning technician time. "
                    "Check open QA gates and material holds for this phase."
                ),
                supporting_evidence=(
                    f"phase={phase.name}",
                    f"blocked_by={blocked_by_str}",
                    f"pending_actions={len(phase.pending_actions)}",
                ),
                confidence="high",
            ))
    return findings


def critical_blockers_open(state: RepairState) -> list[InsightFinding]:
    findings = []
    for blocker in state.blockers:
        if blocker.severity == "critical" and blocker.status == "open":
            blocks_str = ", ".join(blocker.blocks) if blocker.blocks else "repair completion"
            findings.append(InsightFinding(
                finding_id=f"workflow_critical_blocker_{blocker.blocker_id}",
                severity="critical",
                category="workflow",
                title=f"Critical blocker active: {blocker.type.replace('_', ' ')}",
                explanation=(
                    f"A critical {blocker.type.replace('_', ' ')} blocker is preventing progress on: {blocks_str}. "
                    + (blocker.reason or "")
                ),
                recommended_action=(
                    "Escalate immediately. This blocker must be resolved before the repair can continue. "
                    + (blocker.reason or "Contact shop supervisor.")
                ),
                supporting_evidence=(
                    f"blocker_id={blocker.blocker_id}",
                    f"type={blocker.type}",
                    f"blocks={blocks_str}",
                    *[f"zone={z}" for z in blocker.related_zones],
                ),
                confidence="high",
            ))
    return findings


def repair_cannot_advance(state: RepairState) -> list[InsightFinding]:
    blocked = [p for p in state.phases if p.status == "blocked"]
    if len(blocked) < 2:
        return []
    phase_names = [p.label for p in blocked]
    return [InsightFinding(
        finding_id="workflow_repair_cannot_advance",
        severity="critical",
        category="workflow",
        title=f"Repair stalled — {len(blocked)} phases blocked simultaneously",
        explanation=(
            f"{len(blocked)} phases are blocked at the same time: {', '.join(phase_names)}. "
            "The repair cannot meaningfully advance until these blocks are cleared."
        ),
        recommended_action=(
            "Convene a shop review to triage all open blockers. Prioritize clearing the earliest blocked phase first "
            "to unblock downstream phases."
        ),
        supporting_evidence=tuple(
            f"blocked_phase={p.name}" for p in blocked
        ),
        confidence="high",
    )]
