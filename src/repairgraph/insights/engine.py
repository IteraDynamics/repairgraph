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

# Rule modules below are grouped by whether their vocabulary is generic
# (phases/actions/QA-gates/blockers — applies to any domain) or specific to
# a particular domain's concerns (UHSS steel, ADAS calibration, corrosion
# protection — collision-repair concerns with no meaning elsewhere).
#
# Domain-specific rule sets are opt-in per domain so a new domain adapter
# does not inherit collision-repair findings by default. See
# docs/ARCHITECTURE_DERISK.md for why this exists: an aviation task card
# was previously getting a 'no ADAS calibration identified' finding, which
# is meaningless outside collision repair.
DOMAIN_RULE_MODULES: dict[str, tuple] = {
    "collision_repair": (material_findings, compliance_findings),
}


def build_insight_payload(
    state: RepairState,
    manifest_dict: dict | None = None,
    domain: str = "collision_repair",
) -> InsightPayload:
    """Produce a deterministic InsightPayload from repair state and intake manifest.

    Findings are sorted by severity (critical→informational), then category, then finding_id.
    No AI or inference — purely deterministic rules.

    domain selects which domain-specific rule modules run (see
    DOMAIN_RULE_MODULES). Generic rules (QA gates, workflow blockers,
    milestones, intake readiness) always run regardless of domain. Defaults
    to "collision_repair" so existing callers are unaffected; pass the
    compiled model's domain_context.domain to gate correctly for other
    domains.
    """
    findings = _collect_findings(state, manifest_dict or {}, domain)
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


def _collect_findings(state: RepairState, manifest_dict: dict, domain: str) -> list[InsightFinding]:
    found: list[InsightFinding] = []

    # QA — generic vocabulary (open gates by priority), applies to any domain
    found.extend(qa_findings.critical_qa_open(state))
    found.extend(qa_findings.high_qa_open_by_category(state))
    found.extend(qa_findings.medium_qa_open(state))

    # Workflow — generic vocabulary (blockers, blocked phases), any domain
    found.extend(workflow_findings.critical_blockers_open(state))
    found.extend(workflow_findings.repair_cannot_advance(state))
    found.extend(workflow_findings.blocked_phases(state))

    # Domain-specific rule modules (material/compliance concerns) — opt-in
    # per domain so a new domain doesn't inherit collision-repair findings.
    if material_findings in DOMAIN_RULE_MODULES.get(domain, ()):
        found.extend(material_findings.uhss_detected(state))
        found.extend(material_findings.joining_verification_required(state))
        found.extend(material_findings.hss_detected(state))

    if compliance_findings in DOMAIN_RULE_MODULES.get(domain, ()):
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
