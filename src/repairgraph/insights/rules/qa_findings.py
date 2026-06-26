"""QA gate insight rules."""
from __future__ import annotations

from collections import defaultdict

from repairgraph.insights.schema import InsightFinding
from repairgraph.state.schema import RepairState


def critical_qa_open(state: RepairState) -> list[InsightFinding]:
    findings = []
    for gate in state.qa_gates:
        if gate.priority == "critical" and gate.status in ("open", "in_review"):
            findings.append(InsightFinding(
                finding_id=f"qa_critical_open_{gate.gate_id}",
                severity="critical",
                category="qa",
                title=f"Critical QA gate open: {gate.category}",
                explanation=(
                    f"Gate {gate.gate_id} ({gate.category}) is {gate.status} and blocks repair completion. "
                    f"This check must be resolved before the repair can advance."
                ),
                recommended_action=(
                    f"Resolve QA gate {gate.gate_id}. "
                    + (f"Check: {gate.check}" if gate.check else "Review gate requirements with lead technician.")
                ),
                supporting_evidence=(
                    f"gate_id={gate.gate_id}",
                    f"status={gate.status}",
                    f"category={gate.category}",
                    f"blocks_completion={gate.blocks_completion}",
                ),
                confidence="high",
            ))
    return findings


def high_qa_open_by_category(state: RepairState) -> list[InsightFinding]:
    by_category: dict[str, list] = defaultdict(list)
    for gate in state.qa_gates:
        if gate.priority == "high" and gate.status in ("open", "in_review"):
            by_category[gate.category].append(gate)

    findings = []
    for category, gates in sorted(by_category.items()):
        gate_ids = [g.gate_id for g in gates]
        findings.append(InsightFinding(
            finding_id=f"qa_high_open_{category}",
            severity="high",
            category="qa",
            title=f"{len(gates)} high-priority QA gate{'s' if len(gates) > 1 else ''} open: {category}",
            explanation=(
                f"{len(gates)} gate{'s' if len(gates) > 1 else ''} in the {category} category "
                f"{'are' if len(gates) > 1 else 'is'} open and must pass before this phase can complete."
            ),
            recommended_action=(
                f"Address {category} quality checks: {', '.join(gate_ids)}. "
                "Gather required documentation or measurements before signing off."
            ),
            supporting_evidence=tuple(
                f"{g.gate_id}={g.status}" for g in gates
            ),
            confidence="high",
        ))
    return findings


def medium_qa_open(state: RepairState) -> list[InsightFinding]:
    gates = [g for g in state.qa_gates if g.priority == "medium" and g.status in ("open", "in_review")]
    if not gates:
        return []
    gate_ids = [g.gate_id for g in gates]
    return [InsightFinding(
        finding_id="qa_medium_open_summary",
        severity="medium",
        category="qa",
        title=f"{len(gates)} medium-priority QA gate{'s' if len(gates) > 1 else ''} require attention",
        explanation=(
            f"{len(gates)} medium-priority gate{'s' if len(gates) > 1 else ''} "
            f"{'are' if len(gates) > 1 else 'is'} open. These do not block current progress but should "
            "be resolved before final sign-off."
        ),
        recommended_action="Review and close pending medium-priority QA gates: " + ", ".join(gate_ids),
        supporting_evidence=tuple(f"{g.gate_id}:{g.category}" for g in gates),
        confidence="high",
    )]
