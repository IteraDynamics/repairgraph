"""
Review Repair payload builder.

Produces a deterministic, JSON-serializable ReviewPayload from an
OperationalModel. All downstream consumers (HTML page, API endpoint)
project from this payload rather than directly from the OperationalModel.

This module is a projection layer — it does not re-derive conclusions
already captured in OperationalModel.insights or .workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repairgraph.core.operational_model import OperationalModel
from repairgraph.review.executive_review import ExecutiveReview, build_executive_review

# ---------------------------------------------------------------------------
# Decision derivation
# ---------------------------------------------------------------------------

_STATUS_TO_DECISION: dict[str, str] = {
    "blocked": "Blocked",
    "at_risk": "Proceed with Caution",
    "ready": "Ready to Proceed",
    "complete": "Ready to Proceed",
    "unknown": "Needs Review",
}

_STATUS_TO_CONFIDENCE: dict[str, str] = {
    "blocked": "Low",
    "at_risk": "Medium",
    "ready": "High",
    "complete": "High",
    "unknown": "Low",
}

_READINESS_TO_DECISION: dict[str, str] = {
    "blocked": "Blocked",
    "in_progress": "Proceed with Caution",
    "complete": "Ready to Proceed",
    "not_started": "Needs Review",
    "unknown": "Needs Review",
}


def _derive_decision(model: OperationalModel) -> str:
    """Derive a plain-language proceed/blocked decision from the model."""
    if model.source_manifest.readiness in ("incomplete", "unprocessable"):
        return "Insufficient Packet"

    if model.insights:
        return _STATUS_TO_DECISION.get(model.insights.overall_status, "Needs Review")

    return _READINESS_TO_DECISION.get(model.workflow.workflow_readiness, "Needs Review")


def _derive_confidence(model: OperationalModel) -> str:
    if model.insights:
        return _STATUS_TO_CONFIDENCE.get(model.insights.overall_status, "Low")
    if model.workflow.workflow_readiness == "complete":
        return "High"
    return "Low"


def _derive_status_label(model: OperationalModel) -> str:
    if model.insights:
        return model.insights.overall_status.replace("_", " ").title()
    return model.workflow.workflow_readiness.replace("_", " ").title()


def _derive_readiness_label(model: OperationalModel) -> str:
    r = model.workflow.workflow_readiness
    labels = {
        "blocked": "Not Ready — Blockers Present",
        "in_progress": "In Progress",
        "complete": "Ready",
        "not_started": "Not Started",
        "unknown": "Unknown",
    }
    return labels.get(r, r.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(model: OperationalModel) -> dict[str, Any]:
    ctx = model.domain_context.context_data
    vehicle = ctx.get("vehicle", {})
    repair = ctx.get("repair", {})

    oem = vehicle.get("oem", model.domain_context.domain)
    year = vehicle.get("year", "")
    vmodel = vehicle.get("model", "")
    operation = repair.get("operation", "")

    label = model.domain_context.display_label or f"{oem} {year} {vmodel}".strip()

    return {
        "repair_label": label,
        "oem": oem,
        "year": year,
        "model": vmodel,
        "operation": operation.replace("_", " ").title() if operation else "",
        "status": _derive_status_label(model),
        "operational_confidence": _derive_confidence(model),
        "readiness": _derive_readiness_label(model),
        "top_recommended_action": (
            model.insights.next_action if model.insights else ""
        ),
        "summary_headline": (
            model.insights.summary_headline if model.insights else ""
        ),
    }


def _build_decision(model: OperationalModel) -> dict[str, Any]:
    decision = _derive_decision(model)

    # Primary blocking reason
    reason = ""
    if model.state:
        open_blockers = [b for b in model.state.blockers if b.status == "open"]
        if open_blockers:
            most_severe = sorted(
                open_blockers,
                key=lambda b: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(b.severity, 4),
            )
            reason = most_severe[0].reason
    if not reason and model.insights and model.insights.findings:
        reason = model.insights.findings[0].explanation

    next_action = model.insights.next_action if model.insights else ""
    if not next_action and model.workflow.next_recommended_actions:
        next_action = model.workflow.next_recommended_actions[0]

    # Top risks (from critical/high findings)
    top_risks: list[str] = []
    if model.insights:
        for f in model.insights.findings:
            if f.severity in ("critical", "high"):
                top_risks.append(f.title)

    return {
        "decision": decision,
        "reason": reason,
        "next_action": next_action,
        "top_risks": top_risks[:5],
        "operational_confidence": _derive_confidence(model),
        "open_blocker_count": model.workflow.open_blocker_count,
        "risk_level": model.insights.risk_level if model.insights else "none",
    }


def _build_top_findings(model: OperationalModel) -> dict[str, Any]:
    all_findings: list[dict[str, Any]] = []
    if model.insights:
        for f in model.insights.findings:
            all_findings.append(f.to_dict())

    return {
        "top_findings": all_findings[:5],
        "all_findings": all_findings,
        "total_count": len(all_findings),
        "finding_counts": model.insights.finding_counts if model.insights else {},
    }


def _build_documentation(model: OperationalModel) -> dict[str, Any]:
    manifest = model.source_manifest
    return {
        "source_count": manifest.source_count,
        "filenames": manifest.filenames,
        "detected_roles": manifest.detected_roles,
        "missing_roles": manifest.missing_roles,
        "readiness": manifest.readiness,
        "extraction_warnings": manifest.extraction_warnings,
        "customer_owned_content_notice": manifest.customer_owned_content_notice,
        "has_missing_roles": len(manifest.missing_roles) > 0,
        "has_warnings": len(manifest.extraction_warnings) > 0,
    }


def _build_workflow_readiness(model: OperationalModel) -> dict[str, Any]:
    state = model.state
    if not state:
        return {
            "current_phase": None,
            "blocked_phases": [],
            "open_blockers": [],
            "next_actions": [],
            "completed_actions": [],
            "qa_gates": {"open": [], "passed": []},
            "workflow_readiness": model.workflow.workflow_readiness,
        }

    current_phase = None
    blocked_phases: list[dict[str, Any]] = []
    for p in state.phases:
        if p.status == "in_progress":
            current_phase = {"name": p.name, "label": p.label}
        elif p.status == "blocked":
            blocked_phases.append({"name": p.name, "label": p.label})

    open_blockers: list[dict[str, Any]] = [
        {
            "blocker_id": b.blocker_id,
            "type": b.type.replace("_", " ").title(),
            "severity": b.severity,
            "reason": b.reason,
            "related_zones": b.related_zones,
        }
        for b in state.blockers
        if b.status == "open"
    ]

    next_actions: list[dict[str, Any]] = []
    for action_id in state.next_recommended_actions:
        action = next((a for a in state.actions if a.action_id == action_id), None)
        if action:
            next_actions.append({
                "action_id": action.action_id,
                "action_type": action.action_type.replace("_", " ").title(),
                "target": action.target,
                "status": action.status,
            })

    completed_actions: list[dict[str, Any]] = [
        {
            "action_id": a.action_id,
            "action_type": a.action_type.replace("_", " ").title(),
            "target": a.target,
        }
        for a in state.actions
        if a.status == "complete"
    ]

    open_qa: list[dict[str, Any]] = [
        {
            "gate_id": g.gate_id,
            "category": g.category.replace("_", " ").title(),
            "priority": g.priority,
            "check": g.check,
            "blocks_completion": g.blocks_completion,
        }
        for g in state.qa_gates
        if g.status == "open"
    ]
    passed_qa: list[dict[str, Any]] = [
        {
            "gate_id": g.gate_id,
            "category": g.category.replace("_", " ").title(),
            "check": g.check,
        }
        for g in state.qa_gates
        if g.status == "passed"
    ]

    return {
        "current_phase": current_phase,
        "blocked_phases": blocked_phases,
        "open_blockers": open_blockers,
        "next_actions": next_actions,
        "completed_actions": completed_actions,
        "qa_gates": {"open": open_qa, "passed": passed_qa},
        "workflow_readiness": model.workflow.workflow_readiness,
        "phase_count": model.workflow.phase_count,
        "action_count": model.workflow.action_count,
        "complete_action_count": model.workflow.complete_action_count,
        "qa_gate_count": model.workflow.qa_gate_count,
    }


def _build_material_risk(model: OperationalModel) -> dict[str, Any]:
    """Project collision domain material/structural risk from OperationalModel."""
    ctx = model.domain_context.context_data
    systems = ctx.get("systems", {})
    repair_ctx = ctx.get("repair", {})

    uhss_zones: list[str] = []
    hss_zones: list[str] = []
    joining_requirements: list[str] = []
    corrosion_requirements: list[str] = []

    if model.state:
        for zone in model.state.zones:
            mc = (zone.material_classification or "").upper()
            if "UHSS" in mc or "ULTRA" in mc:
                uhss_zones.append(zone.label)
            elif "HSS" in mc or "HIGH" in mc:
                hss_zones.append(zone.label)
            for flag in zone.risk_flags:
                flag_lower = flag.lower()
                if "join" in flag_lower or "weld" in flag_lower:
                    if flag not in joining_requirements:
                        joining_requirements.append(flag)
                if "corrosion" in flag_lower or "zinc" in flag_lower:
                    if flag not in corrosion_requirements:
                        corrosion_requirements.append(flag)

    calibration_required = systems.get("calibration_required", False)
    corrosion_protection_required = systems.get("corrosion_protection_required", False)
    structural_involvement = repair_ctx.get("structural_involvement", False)

    # Augment from findings if available
    if model.insights:
        for finding in model.insights.findings:
            cat = finding.category.lower()
            if "material" in cat or "uhss" in cat:
                pass  # zones already captured from state
            if "corrosion" in cat:
                if finding.recommended_action not in corrosion_requirements:
                    corrosion_requirements.append(finding.recommended_action)
            if "calibration" in cat:
                calibration_required = True

    return {
        "uhss_zones": uhss_zones,
        "hss_zones": hss_zones,
        "joining_verification_required": len(joining_requirements) > 0 or len(uhss_zones) > 0,
        "joining_requirements": joining_requirements,
        "corrosion_protection_required": corrosion_protection_required or len(corrosion_requirements) > 0,
        "corrosion_requirements": corrosion_requirements,
        "calibration_check_required": calibration_required,
        "structural_involvement": structural_involvement,
        "has_material_risk": len(uhss_zones) > 0 or len(hss_zones) > 0,
    }


def _build_evidence_trail(model: OperationalModel) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    # Evidence from state actions and QA gates
    for item in model.evidence.evidence_items:
        items.append(item)

    # Supporting evidence from top findings
    finding_evidence: list[dict[str, Any]] = []
    if model.insights:
        for f in model.insights.top_findings:
            if f.supporting_evidence:
                finding_evidence.append({
                    "finding_id": f.finding_id,
                    "title": f.title,
                    "evidence": list(f.supporting_evidence),
                })

    return {
        "evidence_items": items,
        "finding_evidence": finding_evidence,
        "confidence_by_category": model.evidence.confidence_by_category,
        "requires_oem_verification": model.evidence.requires_oem_verification,
        "total_evidence_count": len(items),
        "source_filenames": model.source_manifest.filenames,
    }


def _build_export_links(model: OperationalModel) -> dict[str, str]:
    defaults = {
        "operational_model": "/internal/demo/payload",
        "topology_viewer": "/internal/state/accord/topology-viewer",
        "repair_audit_trail": "/internal/state/accord/report?view=replay",
        "technician_workflow": "/internal/state/accord/report?view=workflow",
        "oem_intake": "/internal/intake",
        "executive_summary": "/internal/state/accord/report?view=executive",
    }
    links = model.exports.links
    # Merge with defaults, preferring model links
    merged = {**defaults, **links}
    return merged


# ---------------------------------------------------------------------------
# Public payload builder
# ---------------------------------------------------------------------------

@dataclass
class ReviewPayload:
    """Serializable projection of an OperationalModel for the Review Repair page."""
    header: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    top_findings: dict[str, Any] = field(default_factory=dict)
    documentation: dict[str, Any] = field(default_factory=dict)
    workflow_readiness: dict[str, Any] = field(default_factory=dict)
    material_risk: dict[str, Any] = field(default_factory=dict)
    evidence_trail: dict[str, Any] = field(default_factory=dict)
    export_links: dict[str, str] = field(default_factory=dict)
    advisory_notice: str = ""
    generated_at: str = ""
    model_id: str = ""
    executive_review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": self.header,
            "decision": self.decision,
            "top_findings": self.top_findings,
            "documentation": self.documentation,
            "workflow_readiness": self.workflow_readiness,
            "material_risk": self.material_risk,
            "evidence_trail": self.evidence_trail,
            "export_links": self.export_links,
            "advisory_notice": self.advisory_notice,
            "generated_at": self.generated_at,
            "model_id": self.model_id,
            "executive_review": self.executive_review,
        }


def build_review_payload(model: OperationalModel) -> ReviewPayload:
    """Project an OperationalModel into a ReviewPayload for the Review Repair page."""
    executive = build_executive_review(model)
    return ReviewPayload(
        header=_build_header(model),
        decision=_build_decision(model),
        top_findings=_build_top_findings(model),
        documentation=_build_documentation(model),
        workflow_readiness=_build_workflow_readiness(model),
        material_risk=_build_material_risk(model),
        evidence_trail=_build_evidence_trail(model),
        export_links=_build_export_links(model),
        advisory_notice=model.advisory.notice,
        generated_at=model.metadata.generated_at,
        model_id=model.metadata.model_id,
        executive_review=executive.to_dict(),
    )
