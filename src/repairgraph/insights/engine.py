"""Insight engine: assembles InsightPayload from RepairState and intake manifest."""
from __future__ import annotations

from repairgraph.insights.rules import (
    compliance_findings,
    intake_findings,
    material_findings,
    milestone_findings,
    qa_findings,
    workflow_findings,
)
from repairgraph.insights.schema import InsightFinding, InsightPayload, SEVERITY_ORDER
from repairgraph.state.schema import RepairState


def build_insight_payload(
    state: RepairState,
    manifest_dict: dict | None = None,
) -> InsightPayload:
    """Produce a deterministic InsightPayload from repair state and intake manifest.

    Findings are sorted by severity (critical→informational), then category, then finding_id.
    No AI or inference — purely deterministic rules.
    """
    findings = _collect_findings(state, manifest_dict or {})
    findings = _sort_findings(findings)

    overall_status = _derive_overall_status(findings, state)
    risk_level = _derive_risk_level(findings)
    headline = _build_headline(overall_status, findings, state)
    next_action = _derive_next_action(state)
    counts = _count_by_severity(findings)

    return InsightPayload(
        overall_status=overall_status,
        risk_level=risk_level,
        findings=findings,
        summary_headline=headline,
        next_action=next_action,
        finding_counts=counts,
    )


def _collect_findings(state: RepairState, manifest_dict: dict) -> list[InsightFinding]:
    found: list[InsightFinding] = []

    # QA
    found.extend(qa_findings.critical_qa_open(state))
    found.extend(qa_findings.high_qa_open_by_category(state))
    found.extend(qa_findings.medium_qa_open(state))

    # Workflow
    found.extend(workflow_findings.critical_blockers_open(state))
    found.extend(workflow_findings.repair_cannot_advance(state))
    found.extend(workflow_findings.blocked_phases(state))

    # Material
    found.extend(material_findings.uhss_detected(state))
    found.extend(material_findings.joining_verification_required(state))
    found.extend(material_findings.hss_detected(state))

    # Compliance
    found.extend(compliance_findings.corrosion_protection_blocked(state))
    found.extend(compliance_findings.corrosion_qa_open(state))
    found.extend(compliance_findings.calibration_assessment(state))

    # Intake
    if manifest_dict:
        found.extend(intake_findings.missing_critical_roles(manifest_dict))
        found.extend(intake_findings.intake_readiness_concern(manifest_dict))
        found.extend(intake_findings.missing_important_roles(manifest_dict))
        found.extend(intake_findings.conflicting_oem_metadata(manifest_dict))
        found.extend(intake_findings.low_confidence_classifications(manifest_dict))

    # Milestones (informational — last)
    found.extend(milestone_findings.phases_complete(state))
    found.extend(milestone_findings.completed_actions(state))
    found.extend(milestone_findings.next_recommended_action(state))
    if manifest_dict:
        found.extend(milestone_findings.repair_packet_complete(manifest_dict))

    # Deduplicate by finding_id (first wins — rule order defines precedence)
    seen: set[str] = set()
    deduped = []
    for f in found:
        if f.finding_id not in seen:
            seen.add(f.finding_id)
            deduped.append(f)
    return deduped


def _sort_findings(findings: list[InsightFinding]) -> list[InsightFinding]:
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.category, f.finding_id),
    )


def _derive_overall_status(findings: list[InsightFinding], state: RepairState) -> str:
    severities = {f.severity for f in findings}
    session_status = state.session.status

    if session_status == "complete":
        return "complete"
    if "critical" in severities or session_status == "blocked":
        return "blocked"
    if "high" in severities:
        return "at_risk"
    if session_status in ("in_progress", "not_started"):
        if not severities - {"informational", "low"}:
            return "ready"
    return "at_risk" if severities else "ready"


def _derive_risk_level(findings: list[InsightFinding]) -> str:
    for severity in ("critical", "high", "medium", "low"):
        if any(f.severity == severity for f in findings):
            return severity
    return "none"


def _build_headline(overall_status: str, findings: list[InsightFinding], state: RepairState) -> str:
    oem = state.session.oem
    model = state.session.model
    vehicle = f"{oem} {model}".strip()

    criticals = [f for f in findings if f.severity == "critical"]
    highs = [f for f in findings if f.severity == "high"]

    if overall_status == "complete":
        return f"{vehicle} repair complete — all phases and QA gates closed."
    if overall_status == "blocked":
        if criticals:
            return f"{vehicle} repair blocked — {len(criticals)} critical issue{'s' if len(criticals) > 1 else ''} require immediate attention."
        return f"{vehicle} repair cannot advance — multiple phases are blocked."
    if overall_status == "at_risk":
        if highs:
            return f"{vehicle} repair at risk — {len(highs)} high-priority issue{'s' if len(highs) > 1 else ''} need resolution."
        return f"{vehicle} repair progressing with open risk items."
    return f"{vehicle} repair on track — no critical issues identified."


def _derive_next_action(state: RepairState) -> str:
    if state.next_recommended_actions:
        raw = state.next_recommended_actions[0]
        return raw.replace("_", " ").capitalize()
    blocked = [p for p in state.phases if p.status == "blocked"]
    if blocked:
        return f"Resolve blockers for: {blocked[0].label}"
    in_progress = [p for p in state.phases if p.status == "in_progress"]
    if in_progress:
        return f"Continue: {in_progress[0].label}"
    return "Review repair plan with shop supervisor."


def _count_by_severity(findings: list[InsightFinding]) -> dict[str, int]:
    counts: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts
