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

import re
from dataclasses import dataclass
from typing import Any

from repairgraph.core.operational_model import OperationalModel

# ---------------------------------------------------------------------------
# Decision constants
# ---------------------------------------------------------------------------

DECISION_BLOCKED = "BLOCKED"
DECISION_CAUTION = "PROCEED WITH CAUTION"
DECISION_READY = "READY"
DECISION_INSUFFICIENT = "INSUFFICIENT INFORMATION"
DECISION_NEEDS_REVIEW = "NEEDS REVIEW"

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}

# QA category → broad concern group (for deduplication and messaging)
_QA_CONCERN_GROUP: dict[str, str] = {
    "material_compliance": "joining",
    "joining_compliance": "joining",
    "corrosion_protection": "corrosion",
    "component_replacement": "components",
    "dimensional_verification": "dimensions",
    "inspection": "inspection",
}

_QA_CONCERN_DISPLAY: dict[str, str] = {
    "joining": "Joining",
    "corrosion": "Corrosion Protection",
    "components": "Component Replacement",
    "dimensions": "Dimensional Verification",
    "inspection": "Inspection",
}

# Acronyms that should not be title-cased
_ACRONYMS: frozenset[str] = frozenset({"qa", "oem", "uhss", "hss", "mig", "mag", "vin"})


# ---------------------------------------------------------------------------
# Label formatting
# ---------------------------------------------------------------------------

def _format_label(s: str) -> str:
    """Format internal identifiers for display (underscores, acronyms)."""
    parts = re.split(r"[_\-]", s)
    formatted = []
    for p in parts:
        if not p:
            continue
        if p.lower() in _ACRONYMS:
            formatted.append(p.upper())
        else:
            formatted.append(p.title())
    return " ".join(formatted)


def _strip_internal_ids(text: str) -> str:
    """Remove internal gate/action IDs from user-facing text."""
    # Remove patterns like qa:category:priority:N
    text = re.sub(r"\bqa:[a-z_]+:[a-z]+:\d+\b\.?\s*", "", text)
    # Strip "QA gate remains open: " prefix
    text = re.sub(r"^QA gate remains open:\s*", "", text)
    # Strip "Resolve QA gate <id>. Check: " prefix
    text = re.sub(r"^Resolve QA gate [^\s.]+\.\s*(?:Check:\s*)?", "", text)
    return text.strip()


def _normalize_for_dedup(text: str) -> str:
    """Normalize action text for semantic deduplication (case/punctuation insensitive)."""
    t = _strip_internal_ids(text).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _qa_concern_from_gate_id(gate_id: str) -> str:
    """Extract concern group from a QA gate ID like 'qa:material_compliance:critical:2'."""
    parts = gate_id.split(":")
    category = parts[1] if len(parts) > 1 else ""
    return _QA_CONCERN_GROUP.get(category, category)


def _qa_category_display(gate_id: str) -> str:
    """Human-readable display name for the QA gate category."""
    parts = gate_id.split(":")
    category = parts[1] if len(parts) > 1 else ""
    concern = _QA_CONCERN_GROUP.get(category, category)
    return _QA_CONCERN_DISPLAY.get(concern, _format_label(category))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceExplanation:
    evidence_confidence: str          # High / Medium / Low
    evidence_confidence_reason: str
    decision_confidence: str          # High / Medium / Low
    decision_confidence_reason: str

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
    overall_decision: str
    hero_label: str
    primary_problem: str
    executive_summary: str
    immediate_actions: list[str]
    deferred_actions: list[str]
    business_risks: list[str]
    technician_message: str
    manager_message: str
    confidence: ConfidenceExplanation
    decision_rationale: list[dict[str, Any]]
    decision_rationale_extra: list[dict[str, Any]]

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
# Context check
# ---------------------------------------------------------------------------

def _has_usable_repair_context(model: OperationalModel) -> bool:
    """True if the model contains enough repair context to make a meaningful decision."""
    if model.state and (model.state.phases or model.state.blockers or model.state.qa_gates):
        return True
    if model.insights and model.insights.findings:
        return True
    if model.workflow.action_count > 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Decision derivation — corrected hierarchy
# ---------------------------------------------------------------------------

def _derive_overall_decision(model: OperationalModel) -> str:
    """
    Decision hierarchy:
      1. No usable repair context at all          → INSUFFICIENT INFORMATION
      2. Critical state blocker                   → BLOCKED
      3. Blocking critical QA gate                → BLOCKED
      4. High-severity blocker or blocked phase   → BLOCKED
      5. Insights: blocked                        → BLOCKED
      6. Packet incomplete, but workflow usable   → NEEDS REVIEW
      7. Medium findings / at-risk insights       → PROCEED WITH CAUTION
      8. No blockers, no high/critical findings   → READY
    """
    # 1. Truly no context — nothing usable in the model
    if not _has_usable_repair_context(model):
        return DECISION_INSUFFICIENT

    if model.state:
        open_blockers = [b for b in model.state.blockers if b.status == "open"]

        # 2. Critical state blockers
        if any(b.severity == "critical" for b in open_blockers):
            return DECISION_BLOCKED

        # 3. Blocking critical QA gates
        blocking_critical_qa = [
            g for g in model.state.qa_gates
            if g.status == "open" and g.blocks_completion and g.priority == "critical"
        ]
        if blocking_critical_qa:
            return DECISION_BLOCKED

        # 4a. High-severity blockers
        if any(b.severity == "high" for b in open_blockers):
            return DECISION_BLOCKED

        # 4b. Blocked phases
        if any(p.status == "blocked" for p in model.state.phases):
            return DECISION_BLOCKED

    # 5. Insights engine says blocked
    if model.insights and model.insights.overall_status == "blocked":
        return DECISION_BLOCKED

    # 6. Workflow is usable but packet docs are incomplete
    if model.source_manifest.readiness in ("incomplete", "unprocessable"):
        return DECISION_NEEDS_REVIEW

    # 7. Medium/at-risk
    if model.state:
        if any(b.severity == "medium" for b in model.state.blockers if b.status == "open"):
            return DECISION_CAUTION

    if model.insights and model.insights.overall_status == "at_risk":
        return DECISION_CAUTION

    # 8. Ready
    if model.insights and model.insights.overall_status in ("ready", "complete"):
        return DECISION_READY

    wf = model.workflow.workflow_readiness
    if wf == "complete":
        return DECISION_READY
    if wf in ("in_progress", "not_started"):
        return DECISION_CAUTION

    return DECISION_CAUTION


# ---------------------------------------------------------------------------
# Primary problem
# ---------------------------------------------------------------------------

def _derive_primary_problem(model: OperationalModel, decision: str) -> str:
    """One sentence: the most important issue right now."""
    if decision == DECISION_INSUFFICIENT:
        return "There is not enough repair context to assess this job."

    if decision == DECISION_NEEDS_REVIEW:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = " and ".join(_format_label(r) for r in missing[:2])
            return f"The repair packet is missing {roles} documentation."
        return "The repair packet is incomplete. Workflow is active but documentation requires attention."

    # Most severe open blocker — strip internal IDs from reason
    if model.state:
        open_blockers = sorted(
            [b for b in model.state.blockers if b.status == "open"],
            key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
        )
        if open_blockers:
            return _strip_internal_ids(open_blockers[0].reason)

    if model.insights and model.insights.findings:
        return model.insights.findings[0].explanation

    if decision == DECISION_READY:
        return "All required checks have passed and no critical issues remain."

    return "Open items require resolution before this job can be released."


# ---------------------------------------------------------------------------
# Immediate actions — concern-group deduplication, max 3
# ---------------------------------------------------------------------------

def _build_immediate_actions(model: OperationalModel, decision: str) -> list[str]:
    """
    Derive at most 3 distinct immediate actions.

    Groups QA gates by concern (joining, corrosion, etc.) so that multiple
    gate checks for the same underlying issue produce a single action.
    Strips internal IDs from all displayed text.
    """
    # Collect one action per QA concern group (highest priority within group)
    concern_best: dict[str, tuple[int, str]] = {}  # concern → (priority, clean_check)

    if model.state:
        for g in model.state.qa_gates:
            if g.status != "open" or not g.blocks_completion:
                continue
            concern = _qa_concern_from_gate_id(g.gate_id)
            prio = {"critical": 0, "high": 1, "medium": 2}.get(g.priority, 3)
            if concern not in concern_best or prio < concern_best[concern][0]:
                concern_best[concern] = (prio, _strip_internal_ids(g.check))

    # Sort concerns by priority
    concern_actions: list[tuple[int, str]] = sorted(
        concern_best.values(), key=lambda x: x[0]
    )

    # Build action list: up to 2 distinct QA concerns, then 1 workflow action
    result: list[str] = []
    seen_norm: set[str] = set()

    for _prio, check in concern_actions:
        n = _normalize_for_dedup(check)
        if n and n not in seen_norm:
            seen_norm.add(n)
            result.append(check)
        if len(result) >= 2:
            break

    # Add a workflow "resume after clearing" action as slot 3
    resume_action = _derive_resume_action(model)
    if resume_action:
        n = _normalize_for_dedup(resume_action)
        if n not in seen_norm:
            result.append(resume_action)

    # Fallback: if we have nothing from QA, use insight next_action or workflow
    if not result:
        if model.insights and model.insights.next_action:
            result.append(_strip_internal_ids(model.insights.next_action))
        for action in model.workflow.next_recommended_actions:
            if len(result) >= 3:
                break
            n = _normalize_for_dedup(action)
            if n not in seen_norm:
                seen_norm.add(n)
                result.append(_strip_internal_ids(action))

    return result[:3]


def _derive_resume_action(model: OperationalModel) -> str:
    """Construct a 'resume after clearing' action from the pending workflow."""
    if not model.state:
        return ""

    # Find first pending action in a non-blocked phase
    pending = [
        a for a in model.state.actions
        if a.status in ("pending", "in_progress")
    ]
    if pending:
        a = pending[0]
        target = _format_label(a.target.replace(":", " "))
        verb = _format_label(a.action_type.split("_")[0])
        return (
            f"{verb} {target} only after all blocking QA gates are resolved."
        )

    if model.workflow.next_recommended_actions:
        return (
            _strip_internal_ids(model.workflow.next_recommended_actions[0])
            + " (only after blocking QA gates are resolved)"
        )

    return "Resume remaining workflow steps only after blocking QA gates have been cleared."


# ---------------------------------------------------------------------------
# Deferred actions
# ---------------------------------------------------------------------------

def _build_deferred_actions(model: OperationalModel, immediate_actions: list[str]) -> list[str]:
    """Remaining workflow items that are not immediate priorities."""
    immediate_norm = {_normalize_for_dedup(a) for a in immediate_actions}
    deferred: list[str] = []

    if model.state:
        for action in model.state.actions:
            if action.status in ("pending", "in_progress"):
                target = _format_label(action.target.replace(":", " "))
                verb = _format_label(action.action_type.split("_")[0])
                desc = f"{verb} {target}"
                if _normalize_for_dedup(desc) not in immediate_norm:
                    deferred.append(desc)

    for action in model.workflow.next_recommended_actions:
        cleaned = _strip_internal_ids(action)
        if _normalize_for_dedup(cleaned) not in immediate_norm and cleaned not in deferred:
            deferred.append(cleaned)

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
            risks.append("Ultra-high-strength steel is present — OEM joining method must be verified")

    return risks[:5]


# ---------------------------------------------------------------------------
# Technician and manager messages — specific, actionable
# ---------------------------------------------------------------------------

def _build_technician_message(
    model: OperationalModel, decision: str, immediate_actions: list[str]
) -> str:
    """Direct, specific message to the technician: exactly what to do next."""
    if decision == DECISION_INSUFFICIENT:
        return (
            "There is not enough information to issue a work instruction. "
            "Contact your estimator or supervisor before continuing."
        )

    if decision == DECISION_NEEDS_REVIEW:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = " and ".join(_format_label(r) for r in missing[:2])
            return (
                f"Supply the missing {roles} documentation to your estimator. "
                f"Workflow steps are active but documentation must be complete before the job is released."
            )
        return (
            "Workflow is active. Ensure all documentation is filed before the job is released."
        )

    if decision == DECISION_BLOCKED:
        primary_action = immediate_actions[0] if immediate_actions else None
        # Find the primary QA category name
        qa_cat = _primary_blocking_qa_category(model)
        if primary_action and qa_cat:
            return (
                f"{primary_action} "
                f"Do not proceed with this phase until the {qa_cat} QA gate is cleared."
            )
        if primary_action:
            return (
                f"{primary_action} "
                f"Do not proceed until all blocking QA gates are resolved."
            )
        return "Stop work on this phase and resolve all open blocking issues before continuing."

    if decision == DECISION_CAUTION:
        if immediate_actions:
            return (
                f"You may continue work, but address this first: {immediate_actions[0]}"
            )
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


def _primary_blocking_qa_category(model: OperationalModel) -> str:
    """Return the display name of the highest-priority blocking QA category."""
    if not model.state:
        return ""
    for g in sorted(
        [g for g in model.state.qa_gates if g.status == "open" and g.blocks_completion],
        key=lambda g: {"critical": 0, "high": 1, "medium": 2}.get(g.priority, 3),
    ):
        return _qa_category_display(g.gate_id)
    return ""


def _build_manager_message(model: OperationalModel, decision: str) -> str:
    """Short message to the manager: what to verify before releasing the job."""
    if decision == DECISION_INSUFFICIENT:
        return (
            "This job cannot be assessed or released. "
            "Ensure the repair context is fully configured before assigning work."
        )

    if decision == DECISION_NEEDS_REVIEW:
        missing = model.source_manifest.missing_roles
        if missing:
            roles = ", ".join(_format_label(r) for r in missing[:3])
            return (
                f"Do not release this job. Verify that {roles} documentation "
                f"has been received, reviewed, and filed."
            )
        return "Review the repair packet for completeness before releasing this job."

    if decision == DECISION_BLOCKED:
        # Collect distinct QA concern areas from blocking gates
        concern_display_names = _distinct_blocking_qa_concerns(model)
        if concern_display_names:
            concerns = concern_display_names[:3]
            if len(concerns) >= 3:
                concern_str = f"{concerns[0]}, {concerns[1]}, and {concerns[2]}"
            elif len(concerns) == 2:
                concern_str = f"{concerns[0]} and {concerns[1]}"
            else:
                concern_str = concerns[0]
            return (
                f"Confirm {concern_str.lower()} documentation and QA gate sign-off "
                f"before releasing structural work."
            )
        # Fallback to critical blocker reason
        if model.state:
            open_blockers = sorted(
                [b for b in model.state.blockers if b.status == "open"],
                key=lambda b: _SEVERITY_RANK.get(b.severity, 99),
            )
            if open_blockers:
                reason = _strip_internal_ids(open_blockers[0].reason)
                return (
                    f"This job is not releasable. Verify all blocking issues are resolved, "
                    f"especially: {reason}"
                )
        return "Do not release this job. Confirm all blocking QA gates are resolved and signed off."

    if decision == DECISION_CAUTION:
        concern_names = _distinct_blocking_qa_concerns(model)
        if concern_names:
            concern_str = " and ".join(c.lower() for c in concern_names[:2])
            return f"Before releasing, verify {concern_str} QA gate sign-off."
        return "Review open items before releasing. Confirm QA gates have been signed off."

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


def _distinct_blocking_qa_concerns(model: OperationalModel) -> list[str]:
    """Return display names of distinct blocking QA concern groups, sorted by priority."""
    if not model.state:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for g in sorted(
        [g for g in model.state.qa_gates if g.status == "open" and g.blocks_completion],
        key=lambda g: {"critical": 0, "high": 1, "medium": 2}.get(g.priority, 3),
    ):
        concern = _qa_concern_from_gate_id(g.gate_id)
        if concern not in seen:
            seen.add(concern)
            result.append(_QA_CONCERN_DISPLAY.get(concern, _format_label(concern)))
    return result


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def _build_confidence(model: OperationalModel) -> ConfidenceExplanation:
    """Derive evidence confidence and decision confidence independently."""
    ev_conf = model.evidence.confidence_by_category

    if ev_conf:
        avg = sum(ev_conf.values()) / len(ev_conf)
        if avg >= 0.75:
            evidence_confidence = "High"
            evidence_reason = "Multiple source documents were parsed with high extraction confidence."
        elif avg >= 0.50:
            evidence_confidence = "Medium"
            evidence_reason = "Source documents were partially extracted. Some fields may be incomplete."
        else:
            evidence_confidence = "Low"
            evidence_reason = "Extraction confidence is low. Manual review of source documents is recommended."
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
            decision_reason = "Insufficient information for a high-confidence recommendation."
    else:
        decision_confidence = "Low"
        decision_reason = "No insights engine output is available. Decision is based on workflow state only."

    return ConfidenceExplanation(
        evidence_confidence=evidence_confidence,
        evidence_confidence_reason=evidence_reason,
        decision_confidence=decision_confidence,
        decision_confidence_reason=decision_reason,
    )


# ---------------------------------------------------------------------------
# Decision rationale
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
# Executive summary
# ---------------------------------------------------------------------------

def _generate_executive_summary(
    model: OperationalModel,
    decision: str,
    primary_problem: str,
    immediate_actions: list[str],
) -> str:
    """Generate a 60–120 word deterministic executive narrative. No LLMs."""
    ctx = model.domain_context.context_data
    repair_ctx = ctx.get("repair", {})
    structural = repair_ctx.get("structural_involvement", False)

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
            sentences.append(f"The first priority is to {first.lower()}.")
        if structural:
            sentences.append(
                "Structural safety requirements apply and OEM verification is mandatory before proceeding."
            )
        if model.insights and model.insights.risk_level in ("critical", "high"):
            sentences.append(
                "Once blocking issues are resolved, the remaining workflow can be assessed."
            )

    elif decision == DECISION_INSUFFICIENT:
        sentences.append("There is not enough repair context to make a proceed decision.")
        sentences.append(
            "No workflow, findings, or state information is available for assessment."
        )
        sentences.append(
            "Ensure the repair configuration is complete and recompile before reviewing."
        )

    elif decision == DECISION_NEEDS_REVIEW:
        sentences.append(
            "The workflow and repair state are active, but the repair packet is incomplete."
        )
        missing = model.source_manifest.missing_roles
        if missing:
            roles = ", ".join(_format_label(r) for r in missing[:3])
            sentences.append(f"Missing documentation: {roles}.")
        sentences.append(
            "Once documentation is filed, a full proceed decision can be issued."
        )
        done = model.workflow.complete_action_count
        total = model.workflow.action_count
        if total:
            pct = int(done / total * 100)
            sentences.append(f"The repair is {pct}% complete by workflow action count.")

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
            sentences.append(f"Priority attention should be given to: {first.lower()}.")

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
    if len(summary.split()) > 120:
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
