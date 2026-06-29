"""
Executive Review engine.

Projects an OperationalModel into a concise ExecutiveReview — deterministic,
no LLMs, no external dependencies.

The ExecutiveReview answers within ten seconds:
  • Can work continue?
  • Why or why not?
  • What to do next?
  • What can wait?
  • What should a technician do first?
  • What should a manager verify before releasing the job?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repairgraph.core.operational_model import OperationalModel

# ---------------------------------------------------------------------------
# Decision constants
# ---------------------------------------------------------------------------

DECISION_BLOCKED = "BLOCKED"
DECISION_CAUTION = "PROCEED WITH CAUTION"
DECISION_READY = "READY"
DECISION_INSUFFICIENT = "INSUFFICIENT INFORMATION"

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceExplanation:
    evidence_confidence: str          # High / Medium / Low
    evidence_confidence_reason: str   # Why we trust (or don't) the extracted data
    decision_confidence: str          # High / Medium / Low
    decision_confidence_reason: str   # Why we trust (or don't) the recommendation

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_confidence": self.evidence_confidence,
            "evidence_confidence_reason": self.evidence_confidence_reason,
            "decision_confidence": self.decision_confidence,
            "decision_confidence_reason": self.decision_confidence_reason,
        }


@dataclass
class ExecutiveReview:
    """Concise executive projection of an OperationalModel."""
    overall_decision: str                      # BLOCKED / PROCEED WITH CAUTION / READY / INSUFFICIENT INFORMATION
    hero_label: str                            # Same as overall_decision, used for large visual display
    primary_problem: str                       # One sentence: the most important issue right now
    executive_summary: str                     # 60–120 word narrative
    immediate_actions: list[str]               # At most 3, ranked by operational impact
    deferred_actions: list[str]                # Remaining workflow items (can wait)
    business_risks: list[str]                  # Key business and structural safety risks
    technician_message: str                    # "What should I do next?"
    manager_message: str                       # "What should I verify before releasing this job?"
    confidence: ConfidenceExplanation
    decision_rationale: list[dict[str, Any]]   # Why this decision was made (max 5 findings)
    decision_rationale_extra: list[dict[str, Any]]  # Additional observations (collapsed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_decision": self.overall_decision,
            "hero_label": self.hero_label,
            "primary_problem": self.primary_problem,
            "executive_summary": self.executive_summary,
            "immediate_actions": self.immediate_actions,
            "deferred_actions": self.deferred_actions,
            "business_risks": self.business_risks,
            "technician_message": self.technician_message,
            "manager_message": self.manager_message,
            "confidence": self.confidence.to_dict(),
            "decision_rationale": self.decision_rationale,
            "decision_rationale_extra": self.decision_rationale_extra,
        }


# ---------------------------------------------------------------------------
# Decision derivation — deterministic hierarchy
# ---------------------------------------------------------------------------

def _derive_overall_decision(model: OperationalModel) -> str:
    """
    Apply decision hierarchy:
      1. Packet incomplete           → INSUFFICIENT INFORMATION
      2. Critical state blocker      → BLOCKED
      3. Critical QA gate (blocking) → BLOCKED
      4. High-severity blocker       → BLOCKED
      5. Insights: blocked/at_risk   → BLOCKED / PROCEED WITH CAUTION
      6. Medium blocker              → PROCEED WITH CAUTION
      7. Workflow readiness fallback → mapping
      8. Default                     → PROCEED WITH CAUTION
    """
    # 1. Packet completeness
    if model.source_manifest.readiness in ("incomplete", "unprocessable"):
        return DECISION_INSUFFICIENT

    if model.state:
        open_blockers = [b for b in model.state.blockers if b.status == "open"]
        by_severity = sorted(open_blockers, key=lambda b: _SEVERITY_RANK.get(b.severity, 99))

        # 2. Critical state blockers
        if any(b.severity == "critical" for b in open_blockers):
            return DECISION_BLOCKED

        # 3. Critical QA gates that block completion
        blocking_qa = [
            g for g in model.state.qa_gates
            if g.status == "open" and g.blocks_completion and g.priority == "critical"
        ]
        if blocking_qa:
            return DECISION_BLOCKED

        # 4. High-severity blockers
        if any(b.severity == "high" for b in open_blockers):
            return DECISION_BLOCKED

        # 6. Medium blockers — caution
        if any(b.severity == "medium" for b in open_blockers):
            return DECISION_CAUTION

    # 5. Insights engine
    if model.insights:
        status = model.insights.overall_status
        if status == "blocked":
            return DECISION_BLOCKED
        if status == "at_risk":
            return DECISION_CAUTION
        if status in ("ready", "complete"):
            return DECISION_READY

    # 7. Workflow readiness fallback
    wf = model.workflow.workflow_readiness
    if wf == "blocked":
        return DECISION_BLOCKED
    if wf in ("in_progress", "not_started"):
        return DECISION_CAUTION
    if wf == "complete":
        return DECISION_READY

    return DECISION_CAUTION


# ---------------------------------------------------------------------------
# Primary problem
# ---------------------------------------------------------------------------

def _derive_primary_problem(model: OperationalModel, decision: str) -> str:
    """One sentence describing the most important issue right now."""
    if decision == DECISION_INSUFFICIENT:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = " and ".join(r.replace("_", " ") for r in missing[:2])
            return f"The repair packet is missing required {roles} documentation."
        return "The repair packet is incomplete and cannot be fully assessed."

    # Most severe open blocker from state
    if model.state:
        open_blockers = sorted(
            [b for b in model.state.blockers if b.status == "open"],
            key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
        )
        if open_blockers:
            return open_blockers[0].reason

    # Top insight finding
    if model.insights and model.insights.findings:
        return model.insights.findings[0].explanation

    if decision == DECISION_READY:
        return "All required checks have passed and no critical issues remain."

    return "Open items require resolution before this job can be released."


# ---------------------------------------------------------------------------
# Immediate actions (max 3)
# ---------------------------------------------------------------------------

def _build_immediate_actions(model: OperationalModel, decision: str) -> list[str]:
    """Derive at most 3 immediate actions, ranked by operational impact."""
    candidates: list[tuple[int, str]] = []

    if model.state:
        # Open blockers, most severe first
        open_blockers = sorted(
            [b for b in model.state.blockers if b.status == "open"],
            key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
        )
        for b in open_blockers[:3]:
            candidates.append((_SEVERITY_RANK.get(b.severity, 4), b.reason))

        # Blocking QA gates
        blocking_qa = sorted(
            [g for g in model.state.qa_gates if g.status == "open" and g.blocks_completion],
            key=lambda g: {"critical": 0, "high": 1, "medium": 2}.get(g.priority, 3),
        )
        for g in blocking_qa[:2]:
            priority = {"critical": 0, "high": 1, "medium": 2}.get(g.priority, 3)
            candidates.append((priority, g.check))

    # Critical/high insight findings
    if model.insights:
        for f in model.insights.findings:
            if f.severity in ("critical", "high") and f.recommended_action:
                candidates.append((_SEVERITY_RANK.get(f.severity, 4), f.recommended_action))

    # Workflow recommended actions
    if model.insights and model.insights.next_action:
        candidates.append((5, model.insights.next_action))
    for action in model.workflow.next_recommended_actions:
        candidates.append((6, action))

    # Sort, deduplicate, cap at 3
    seen: set[str] = set()
    result: list[str] = []
    for _priority, action in sorted(candidates, key=lambda x: x[0]):
        if action and action not in seen:
            seen.add(action)
            result.append(action)
        if len(result) >= 3:
            break

    return result


# ---------------------------------------------------------------------------
# Deferred actions
# ---------------------------------------------------------------------------

def _build_deferred_actions(model: OperationalModel, immediate_actions: list[str]) -> list[str]:
    """Remaining workflow items that are not immediate priorities."""
    immediate_set = set(immediate_actions)
    deferred: list[str] = []

    if model.state:
        for action in model.state.actions:
            if action.status in ("pending", "in_progress"):
                desc = f"{action.action_type.replace('_', ' ').title()} — {action.target}"
                if action.target not in immediate_set and desc not in immediate_set:
                    deferred.append(desc)

    for action in model.workflow.next_recommended_actions:
        if action not in immediate_set and action not in deferred:
            deferred.append(action)

    return deferred[:10]


# ---------------------------------------------------------------------------
# Business risks
# ---------------------------------------------------------------------------

def _build_business_risks(model: OperationalModel) -> list[str]:
    """Key business and structural safety risks."""
    risks: list[str] = []

    if model.insights:
        for f in model.insights.findings:
            if f.severity in ("critical", "high"):
                risks.append(f.title)

    ctx = model.domain_context.context_data
    systems = ctx.get("systems", {})
    if systems.get("calibration_required"):
        risks.append("Post-repair calibration required — vehicle is not safe to release without it")

    if model.state:
        uhss_zones = [
            z.label for z in model.state.zones
            if "UHSS" in (z.material_classification or "").upper()
            or "ULTRA" in (z.material_classification or "").upper()
        ]
        if uhss_zones:
            risks.append("Ultra-high-strength steel is present — joining method must be OEM-verified")

    return risks[:5]


# ---------------------------------------------------------------------------
# Technician and manager messages
# ---------------------------------------------------------------------------

def _build_technician_message(
    model: OperationalModel, decision: str, immediate_actions: list[str]
) -> str:
    """Short, direct message to the technician: what to do next."""
    if decision == DECISION_INSUFFICIENT:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = " and ".join(r.replace("_", " ") for r in missing[:2])
            return (
                f"Do not proceed. Supply the missing {roles} documentation to your "
                f"estimator before continuing work."
            )
        return "Do not proceed until the repair packet is complete. Contact your estimator."

    if decision == DECISION_BLOCKED:
        if model.state:
            open_blockers = sorted(
                [b for b in model.state.blockers if b.status == "open"],
                key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
            )
            if open_blockers:
                return f"Stop work and resolve: {open_blockers[0].reason}"
        if immediate_actions:
            return f"Stop work and address: {immediate_actions[0]}"
        return "Do not proceed. Contact your supervisor to resolve open blockers."

    if decision == DECISION_CAUTION:
        if immediate_actions:
            return f"You may continue work, but address this first: {immediate_actions[0]}"
        return (
            "Continue work while monitoring open items. "
            "Resolve outstanding checks before the job is released."
        )

    # READY
    if model.workflow.next_recommended_actions:
        return model.workflow.next_recommended_actions[0]
    if immediate_actions:
        return immediate_actions[0]
    return "All checks clear. Proceed with the repair following OEM procedures."


def _build_manager_message(model: OperationalModel, decision: str) -> str:
    """Short message to the manager: what to verify before releasing the job."""
    if decision == DECISION_INSUFFICIENT:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = ", ".join(r.replace("_", " ") for r in missing[:3])
            return (
                f"Do not release this job. Verify that {roles} documentation "
                f"has been received, reviewed, and filed."
            )
        return "Do not release this job until the repair packet is complete and reviewed."

    if decision == DECISION_BLOCKED:
        if model.state:
            open_blockers = sorted(
                [b for b in model.state.blockers if b.status == "open"],
                key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
            )
            critical = [b for b in open_blockers if b.severity == "critical"]
            if critical:
                return (
                    f"This job is not releasable. Verify all critical issues are resolved, "
                    f"especially: {critical[0].reason}"
                )
            open_qa = [
                g for g in model.state.qa_gates
                if g.status == "open" and g.blocks_completion
            ]
            if open_qa:
                return f"Do not release until this QA check is cleared: {open_qa[0].check}"
        return "Do not release this job. Confirm all blockers have been resolved and signed off."

    if decision == DECISION_CAUTION:
        checks: list[str] = []
        if model.state:
            open_qa = [g for g in model.state.qa_gates if g.status == "open"]
            if open_qa:
                checks.append(f"QA sign-off: {open_qa[0].check}")
        if model.insights:
            for f in model.insights.findings:
                cat = f.category.lower()
                if cat in ("material_safety", "joining", "corrosion") and f.severity in ("critical", "high"):
                    checks.append(f.recommended_action)
                    break
        if checks:
            return f"Before releasing, verify: {'; '.join(checks[:2])}."
        return (
            "Review all open items before releasing. "
            "Confirm that QA gates have been signed off."
        )

    # READY
    if model.evidence.requires_oem_verification:
        return (
            "Verify that OEM procedure compliance has been confirmed and documented "
            "before releasing this job."
        )
    return (
        "Review the completed action list and confirm that post-repair verification "
        "has been documented."
    )


# ---------------------------------------------------------------------------
# Confidence (two independent concepts)
# ---------------------------------------------------------------------------

def _build_confidence(model: OperationalModel) -> ConfidenceExplanation:
    """Derive evidence confidence and decision confidence independently."""
    ev_conf = model.evidence.confidence_by_category

    if ev_conf:
        avg = sum(ev_conf.values()) / len(ev_conf)
        if avg >= 0.75:
            evidence_confidence = "High"
            evidence_reason = (
                "Multiple source documents were parsed with high extraction confidence."
            )
        elif avg >= 0.50:
            evidence_confidence = "Medium"
            evidence_reason = (
                "Source documents were partially extracted. Some fields may be incomplete."
            )
        else:
            evidence_confidence = "Low"
            evidence_reason = (
                "Extraction confidence is low. Manual review of source documents is recommended."
            )
    elif model.source_manifest.source_count > 0:
        evidence_confidence = "Medium"
        evidence_reason = (
            "Documents were supplied but confidence data is limited. "
            "Verify completeness against OEM requirements."
        )
    else:
        evidence_confidence = "Low"
        evidence_reason = (
            "No source documents were supplied. "
            "All information is inferred from repair configuration."
        )

    # Decision confidence
    if model.insights:
        status = model.insights.overall_status
        if status in ("blocked", "complete"):
            decision_confidence = "High"
            decision_reason = (
                "The decision is based on deterministic rules applied to a well-defined repair state."
            )
        elif status == "at_risk":
            decision_confidence = "Medium"
            decision_reason = (
                "The caution recommendation reflects unresolved open items. "
                "Confidence will increase once those items are addressed."
            )
        elif status == "ready":
            decision_confidence = "High"
            decision_reason = (
                "All checks passed and no blockers remain. "
                "The ready recommendation is well-supported by the repair state."
            )
        else:
            decision_confidence = "Low"
            decision_reason = (
                "Insufficient information to make a high-confidence recommendation. "
                "Manual review is advised."
            )
    else:
        decision_confidence = "Low"
        decision_reason = (
            "No insights engine output is available. "
            "Decision is based on workflow state only."
        )

    return ConfidenceExplanation(
        evidence_confidence=evidence_confidence,
        evidence_confidence_reason=evidence_reason,
        decision_confidence=decision_confidence,
        decision_confidence_reason=decision_reason,
    )


# ---------------------------------------------------------------------------
# Decision rationale (findings)
# ---------------------------------------------------------------------------

def _build_decision_rationale(
    model: OperationalModel,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (top_5_findings, remaining_findings) sorted by severity."""
    all_findings: list[dict[str, Any]] = []
    if model.insights:
        sev_keys = ["critical", "high", "medium", "low", "informational"]
        sorted_findings = sorted(
            model.insights.findings,
            key=lambda f: sev_keys.index(f.severity) if f.severity in sev_keys else 99,
        )
        all_findings = [f.to_dict() for f in sorted_findings]

    return all_findings[:5], all_findings[5:]


# ---------------------------------------------------------------------------
# Executive summary (deterministic narrative, 60–120 words)
# ---------------------------------------------------------------------------

def _generate_executive_summary(
    model: OperationalModel,
    decision: str,
    primary_problem: str,
    immediate_actions: list[str],
) -> str:
    """Generate a 60–120 word deterministic executive narrative. No LLMs."""
    ctx = model.domain_context.context_data
    vehicle = ctx.get("vehicle", {})
    repair_ctx = ctx.get("repair", {})

    oem = vehicle.get("oem", "")
    vmodel = vehicle.get("model", "")
    operation = repair_ctx.get("operation", "").replace("_", " ")
    structural = repair_ctx.get("structural_involvement", False)

    vehicle_str = f"{oem} {vmodel}".strip() or "this vehicle"
    operation_str = operation or "this repair"

    sentences: list[str] = []

    if decision == DECISION_BLOCKED:
        sentences.append("This repair cannot safely proceed.")
        if primary_problem and primary_problem != sentences[0]:
            sentences.append(primary_problem)
        if model.state:
            open_blockers = [b for b in model.state.blockers if b.status == "open"]
            if len(open_blockers) > 1:
                sentences.append(
                    f"There are {len(open_blockers)} open issues that must be resolved "
                    f"before work can continue."
                )
        if immediate_actions:
            first = immediate_actions[0].rstrip(".")
            sentences.append(
                f"The first priority is to {first.lower()}."
            )
        if structural:
            sentences.append(
                "Structural safety requirements apply and OEM verification is mandatory before proceeding."
            )
        if model.insights and model.insights.risk_level in ("critical", "high"):
            sentences.append(
                "Once the blocking issues are resolved, the remaining workflow can be assessed."
            )

    elif decision == DECISION_INSUFFICIENT:
        sentences.append(
            "A proceed decision cannot be made because the repair packet is incomplete."
        )
        missing = model.source_manifest.missing_roles
        if missing:
            roles = ", ".join(r.replace("_", " ") for r in missing[:3])
            sentences.append(f"Missing documentation includes: {roles}.")
        sentences.append(
            "Once all required documents are supplied, a full assessment can be completed "
            "and a proceed decision issued."
        )

    elif decision == DECISION_CAUTION:
        sentences.append(
            "Work can continue on this repair, though open items require attention "
            "before the job is released."
        )
        if primary_problem:
            sentences.append(primary_problem)
        done = model.workflow.complete_action_count
        total = model.workflow.action_count
        if total:
            pct = int(done / total * 100)
            sentences.append(f"The repair is {pct}% complete by workflow action count.")
        if immediate_actions:
            first = immediate_actions[0].rstrip(".")
            sentences.append(
                f"Priority attention should be given to: {first.lower()}."
            )

    else:  # READY
        sentences.append("This repair is ready to proceed.")
        if model.source_manifest.readiness == "ready":
            sentences.append(
                "All required documentation is present and the repair packet is complete."
            )
        done = model.workflow.complete_action_count
        total = model.workflow.action_count
        if total and done:
            sentences.append(f"{done} of {total} workflow actions are complete.")
        if immediate_actions:
            first = immediate_actions[0].rstrip(".")
            sentences.append(f"The next step is to {first.lower()}.")
        sentences.append("No critical blockers or unresolved safety flags remain.")

    summary = " ".join(sentences)

    # Trim to ≤120 words at a sentence boundary
    words = summary.split()
    if len(words) > 120:
        trimmed: list[str] = []
        count = 0
        for s in sentences:
            wc = len(s.split())
            if count + wc > 120:
                break
            trimmed.append(s)
            count += wc
        summary = " ".join(trimmed)

    return summary


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_executive_review(model: OperationalModel) -> ExecutiveReview:
    """Project an OperationalModel into a concise ExecutiveReview."""
    decision = _derive_overall_decision(model)
    primary_problem = _derive_primary_problem(model, decision)
    immediate_actions = _build_immediate_actions(model, decision)
    deferred_actions = _build_deferred_actions(model, immediate_actions)
    business_risks = _build_business_risks(model)
    technician_message = _build_technician_message(model, decision, immediate_actions)
    manager_message = _build_manager_message(model, decision)
    confidence = _build_confidence(model)
    rationale, rationale_extra = _build_decision_rationale(model)
    executive_summary = _generate_executive_summary(
        model, decision, primary_problem, immediate_actions
    )

    return ExecutiveReview(
        overall_decision=decision,
        hero_label=decision,
        primary_problem=primary_problem,
        executive_summary=executive_summary,
        immediate_actions=immediate_actions,
        deferred_actions=deferred_actions,
        business_risks=business_risks,
        technician_message=technician_message,
        manager_message=manager_message,
        confidence=confidence,
        decision_rationale=rationale,
        decision_rationale_extra=rationale_extra,
    )
