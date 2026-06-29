"""
Root Cause Analysis Engine.

Identifies the minimum set of root causes responsible for the largest
amount of downstream operational impact, collapsing many symptoms into
a small number of causal explanations.

Algorithm
---------
Rather than reporting N symptoms, this engine:

1. Seeds root causes from the most authoritative origin signals:
   - Open blocking QA gates (highest authority — gates create blockers)
   - Open blockers with no QA-gate origin (material risk, dependencies, holds)
   - Critical/high findings with no corresponding state entry

2. For each root cause, traverses downstream consequences:
   - Blockers created by the root cause
   - Phases blocked as a result
   - Actions blocked or pending due to blocked phases
   - QA gates chained off the same concern group
   - Findings whose category matches the root cause concern

3. Scores impact using documented weights (see _IMPACT_WEIGHTS).

4. Deduplicates: if two potential root causes share >50% of their
   downstream impact set, the lower-scored one is merged into the other.

5. Sorts by impact score descending and returns up to MAX_ROOT_CAUSES.

Impact weights (documented)
---------------------------
Critical QA gate (open, blocks_completion)  +100
High QA gate (open, blocks_completion)       +60
Medium QA gate (open, blocks_completion)     +20
Critical blocker                             +100
High blocker                                 +60
Medium blocker                               +25
Low blocker                                  +10
Blocked phase                                +25  (per phase)
Pending/in-progress action in blocked phase  +5   (per action, capped at 50)
Material safety flag (UHSS/HSS zone)         +40
Calibration requirement                      +20
Critical/high insight finding                +10  (per finding)

Design constraints
------------------
- Deterministic. No LLMs, no randomness, no external dependencies.
- Read-only projection from OperationalModel. Does not mutate any state.
- O(n·m) in practice for typical repair models (n gates, m phases).
- Safe to call multiple times; results are stable for a given model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from repairgraph.core.operational_model import OperationalModel
from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairState,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ROOT_CAUSES = 5

# Impact weights — documented in module docstring
_IMPACT_WEIGHTS = {
    "qa_critical": 100,
    "qa_high": 60,
    "qa_medium": 20,
    "blocker_critical": 100,
    "blocker_high": 60,
    "blocker_medium": 25,
    "blocker_low": 10,
    "blocked_phase": 25,
    "blocked_action": 5,
    "blocked_action_cap": 50,
    "material_safety": 40,
    "calibration": 20,
    "finding_critical_high": 10,
}

# QA category → concern group (mirrors executive_review grouping)
_QA_CONCERN_GROUP: dict[str, str] = {
    "material_compliance": "joining",
    "joining_compliance": "joining",
    "corrosion_protection": "corrosion",
    "component_replacement": "components",
    "dimensional_verification": "dimensions",
    "inspection": "inspection",
    "calibration": "calibration",
    "documentation": "documentation",
}

_QA_CONCERN_DISPLAY: dict[str, str] = {
    "joining": "Joining & Material Compliance",
    "corrosion": "Corrosion Protection",
    "components": "Component Replacement",
    "dimensions": "Dimensional Verification",
    "inspection": "Inspection",
    "calibration": "Calibration",
    "documentation": "Documentation",
}

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}

_ACRONYMS: frozenset[str] = frozenset({"qa", "oem", "uhss", "hss", "mig", "mag", "vin"})


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _format_label(s: str) -> str:
    parts = re.split(r"[_\-]", s)
    out = []
    for p in parts:
        if not p:
            continue
        if p.lower() in _ACRONYMS:
            out.append(p.upper())
        else:
            out.append(p.title())
    return " ".join(out)


def _strip_ids(text: str) -> str:
    text = re.sub(r"\bqa:[a-z_]+:[a-z]+:\d+\b\.?\s*", "", text)
    text = re.sub(r"^QA gate remains open:\s*", "", text)
    text = re.sub(r"^Resolve QA gate [^\s.]+\.\s*(?:Check:\s*)?", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ImpactSummary:
    """Downstream consequences attributable to a single root cause."""
    blocked_phases: list[str] = field(default_factory=list)       # phase labels
    blocked_actions: list[str] = field(default_factory=list)      # action descriptions
    blocked_qa: list[str] = field(default_factory=list)           # QA gate check texts
    contributing_blockers: list[str] = field(default_factory=list) # blocker reasons
    affected_findings: list[str] = field(default_factory=list)    # finding titles
    unblocked_phases: list[str] = field(default_factory=list)     # what resolving opens

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked_phases": self.blocked_phases,
            "blocked_actions": self.blocked_actions,
            "blocked_qa": self.blocked_qa,
            "contributing_blockers": self.contributing_blockers,
            "affected_findings": self.affected_findings,
            "unblocked_phases": self.unblocked_phases,
        }


@dataclass
class RootCause:
    """A single identified root cause with full impact attribution."""
    root_cause_id: str
    concern_group: str                     # joining / corrosion / components / …
    concern_display: str                   # "Joining & Material Compliance"
    title: str                             # short human title
    description: str                       # one-sentence explanation
    recommended_resolution: str            # specific next action
    priority: str                          # critical / high / medium / low
    impact_score: int
    impact: ImpactSummary
    supporting_evidence: list[str] = field(default_factory=list)
    confidence: str = "Medium"             # High / Medium / Low

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause_id": self.root_cause_id,
            "concern_group": self.concern_group,
            "concern_display": self.concern_display,
            "title": self.title,
            "description": self.description,
            "recommended_resolution": self.recommended_resolution,
            "priority": self.priority,
            "impact_score": self.impact_score,
            "impact": self.impact.to_dict(),
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
        }


@dataclass
class RootCauseAnalysis:
    """Complete root cause analysis output for an OperationalModel."""
    root_causes: list[RootCause]
    total_impact_score: int
    summary: str                  # e.g. "Repair blocked by 1 Critical Root Cause"
    summary_detail: str           # e.g. "Resolving the joining issue unblocks 3 phases"
    open_qa_count: int
    open_blocker_count: int
    blocked_phase_count: int
    collapsed_finding_count: int  # how many raw findings were collapsed into root causes

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_causes": [rc.to_dict() for rc in self.root_causes],
            "total_impact_score": self.total_impact_score,
            "summary": self.summary,
            "summary_detail": self.summary_detail,
            "open_qa_count": self.open_qa_count,
            "open_blocker_count": self.open_blocker_count,
            "blocked_phase_count": self.blocked_phase_count,
            "collapsed_finding_count": self.collapsed_finding_count,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _qa_concern(gate_id: str) -> str:
    parts = gate_id.split(":")
    category = parts[1] if len(parts) > 1 else ""
    return _QA_CONCERN_GROUP.get(category, category or "unknown")


def _qa_priority(gate: QAGateState) -> str:
    return gate.priority  # already "critical"/"high"/"medium"


def _phase_for_action(action: ActionState, phases: list[PhaseState]) -> PhaseState | None:
    return next((p for p in phases if p.phase == action.phase), None)


def _is_phase_blocked(phase: PhaseState) -> bool:
    return phase.status == "blocked"


def _actions_in_phase(phase: PhaseState, actions: list[ActionState]) -> list[ActionState]:
    return [a for a in actions if a.phase == phase.phase]


def _blocked_or_pending_actions(actions: list[ActionState]) -> list[ActionState]:
    return [a for a in actions if a.status in ("blocked", "pending", "in_progress")]


# ---------------------------------------------------------------------------
# Step 1: Seed root cause candidates
# ---------------------------------------------------------------------------

def _seed_candidates(model: OperationalModel) -> list[dict[str, Any]]:
    """
    Produce a list of raw candidates, each anchored to a specific causal origin.

    Priority order:
    1. Open critical/high blocking QA gates (highest authority)
    2. Open blockers not traceable to a QA gate
    3. Critical/high insight findings not covered by state
    """
    candidates: list[dict[str, Any]] = []

    if not model.state:
        return candidates

    state = model.state

    # --- QA gates as root cause seeds ---
    # Group by concern; pick the highest-priority gate per concern as the seed.
    concern_best_qa: dict[str, QAGateState] = {}
    for g in state.qa_gates:
        if g.status != "open" or not g.blocks_completion:
            continue
        concern = _qa_concern(g.gate_id)
        existing = concern_best_qa.get(concern)
        if existing is None or (
            _SEVERITY_RANK.get(g.priority, 99) < _SEVERITY_RANK.get(existing.priority, 99)
        ):
            concern_best_qa[concern] = g

    for concern, gate in concern_best_qa.items():
        candidates.append({
            "type": "qa_gate",
            "concern": concern,
            "gate": gate,
            "blocker": None,
        })

    # --- Blockers not sourced from QA gates ---
    qa_blocker_ids = {
        f"blocker:qa:{g.gate_id.split(':')[1]}:{g.gate_id.split(':')[2]}:{g.gate_id.split(':')[3]}"
        for g in state.qa_gates
        if g.status == "open" and len(g.gate_id.split(":")) == 4
    }
    for b in state.blockers:
        if b.status != "open":
            continue
        if b.blocker_id in qa_blocker_ids:
            continue
        if b.type in ("dependency", "material_risk", "manual_hold", "documentation_required"):
            concern = {
                "material_risk": "material_safety",
                "dependency": "dependency",
                "manual_hold": "manual_hold",
                "documentation_required": "documentation",
            }.get(b.type, "other")
            candidates.append({
                "type": "blocker",
                "concern": concern,
                "gate": None,
                "blocker": b,
            })

    # --- High/critical insight findings with no state coverage ---
    covered_concerns = {c["concern"] for c in candidates}
    if model.insights:
        for f in model.insights.findings:
            if f.severity not in ("critical", "high"):
                continue
            cat = f.category.lower().replace(" ", "_")
            concern = _QA_CONCERN_GROUP.get(cat, cat)
            if concern not in covered_concerns:
                candidates.append({
                    "type": "finding",
                    "concern": concern,
                    "gate": None,
                    "blocker": None,
                    "finding": f,
                })
                covered_concerns.add(concern)

    return candidates


# ---------------------------------------------------------------------------
# Step 2: Build impact for each candidate
# ---------------------------------------------------------------------------

def _build_impact(
    candidate: dict[str, Any],
    model: OperationalModel,
) -> tuple[ImpactSummary, int, list[str]]:
    """
    Traverse downstream consequences of a candidate root cause.
    Returns (ImpactSummary, impact_score, supporting_evidence).
    """
    state = model.state
    concern = candidate["concern"]

    blocked_phases: list[str] = []
    blocked_actions: list[str] = []
    blocked_qa: list[str] = []
    contributing_blockers: list[str] = []
    affected_findings: list[str] = []
    supporting_evidence: list[str] = []
    score = 0

    if not state:
        return ImpactSummary(), 0, []

    # All open blocking QA gates in this concern group
    concern_gates = [
        g for g in state.qa_gates
        if g.status == "open" and g.blocks_completion and _qa_concern(g.gate_id) == concern
    ]
    for g in concern_gates:
        check_text = _strip_ids(g.check or "")
        if check_text:
            blocked_qa.append(check_text)
        prio = g.priority
        if prio == "critical":
            score += _IMPACT_WEIGHTS["qa_critical"]
            supporting_evidence.append(f"Critical QA gate: {check_text}")
        elif prio == "high":
            score += _IMPACT_WEIGHTS["qa_high"]
        else:
            score += _IMPACT_WEIGHTS["qa_medium"]

    # Blockers in same concern (qa_gate blockers matching concern, plus direct)
    concern_blockers = [
        b for b in state.blockers
        if b.status == "open" and (
            b.blocker_id.startswith(f"blocker:qa:{_concern_qa_category(concern)}:")
            or (candidate["blocker"] and b.blocker_id == candidate["blocker"].blocker_id)
        )
    ]
    # Also collect all open blockers that reference related zones/actions
    related_zone_ids: set[str] = set()
    for g in concern_gates:
        related_zone_ids.update(g.zone_refs)
    for b in state.blockers:
        if b.status != "open":
            continue
        if b in concern_blockers:
            continue
        if set(b.related_zones) & related_zone_ids:
            concern_blockers.append(b)

    seen_blocker_ids: set[str] = set()
    for b in concern_blockers:
        if b.blocker_id in seen_blocker_ids:
            continue
        seen_blocker_ids.add(b.blocker_id)
        reason = _strip_ids(b.reason or "")
        if reason:
            contributing_blockers.append(reason)
        sev = b.severity
        score += _IMPACT_WEIGHTS.get(f"blocker_{sev}", _IMPACT_WEIGHTS["blocker_low"])
        if sev == "critical":
            supporting_evidence.append(f"Critical blocker: {reason}")

    # Determine affected phases
    # A phase is affected if it is blocked, or if any blocked action in it
    # belongs to a zone referenced by a concern gate.
    affected_phase_nums: set[int] = set()
    for p in state.phases:
        if _is_phase_blocked(p):
            # Check if any QA gate or blocker in this concern references this phase
            for g in concern_gates:
                if g.related_phase == p.phase:
                    affected_phase_nums.add(p.phase)
                    break
            # Also: if phase is blocked and any of its pending actions share zone_refs
            # with a concern gate, count the phase
            phase_actions = _actions_in_phase(p, state.actions)
            for a in phase_actions:
                if set(a.zone_refs) & related_zone_ids:
                    affected_phase_nums.add(p.phase)
                    break

    # If we have no phases yet but the model has blocked phases, attribute them
    # to the highest-priority root cause (this is the seed gate's related_phase)
    if not affected_phase_nums:
        seed_gate = candidate.get("gate")
        if seed_gate and seed_gate.related_phase is not None:
            p = next((p for p in state.phases if p.phase == seed_gate.related_phase), None)
            if p and _is_phase_blocked(p):
                affected_phase_nums.add(p.phase)

    for phase_num in sorted(affected_phase_nums):
        p = next((p for p in state.phases if p.phase == phase_num), None)
        if p:
            blocked_phases.append(p.label)
            score += _IMPACT_WEIGHTS["blocked_phase"]

    # Count blocked/pending actions in affected phases (capped)
    action_score = 0
    for phase_num in affected_phase_nums:
        p = next((p for p in state.phases if p.phase == phase_num), None)
        if not p:
            continue
        actions_here = _blocked_or_pending_actions(_actions_in_phase(p, state.actions))
        for a in actions_here:
            desc = f"{_format_label(a.action_type.split('_')[0])} {_format_label(a.target.replace(':', ' '))}"
            blocked_actions.append(desc)
            action_score += _IMPACT_WEIGHTS["blocked_action"]
            if action_score >= _IMPACT_WEIGHTS["blocked_action_cap"]:
                break
    score += min(action_score, _IMPACT_WEIGHTS["blocked_action_cap"])

    # Material safety bonus
    if concern in ("joining", "material_safety"):
        has_uhss = any(
            "UHSS" in (z.material_classification or "").upper()
            or "ULTRA" in (z.material_classification or "").upper()
            for z in state.zones
        )
        if has_uhss:
            score += _IMPACT_WEIGHTS["material_safety"]
            supporting_evidence.append("Ultra-high-strength steel present in repair area")

    # Calibration bonus
    ctx = model.domain_context.context_data
    if ctx.get("systems", {}).get("calibration_required") and concern == "calibration":
        score += _IMPACT_WEIGHTS["calibration"]

    # Insight findings matching this concern
    if model.insights:
        for f in model.insights.findings:
            cat = f.category.lower().replace(" ", "_")
            f_concern = _QA_CONCERN_GROUP.get(cat, cat)
            if f_concern == concern and f.severity in ("critical", "high"):
                affected_findings.append(f.title)
                score += _IMPACT_WEIGHTS["finding_critical_high"]

    # What becomes unblocked if resolved
    unblocked_phases = list(blocked_phases)

    impact = ImpactSummary(
        blocked_phases=blocked_phases,
        blocked_actions=blocked_actions[:10],  # cap display list
        blocked_qa=blocked_qa,
        contributing_blockers=contributing_blockers,
        affected_findings=affected_findings,
        unblocked_phases=unblocked_phases,
    )
    return impact, score, supporting_evidence


def _concern_qa_category(concern: str) -> str:
    """Map concern group back to primary QA category prefix for blocker ID matching."""
    rev = {v: k for k, v in _QA_CONCERN_GROUP.items()}
    # For "joining" there are two — return the most common one
    return {
        "joining": "material_compliance",
        "corrosion": "corrosion_protection",
        "components": "component_replacement",
        "dimensions": "dimensional_verification",
        "inspection": "inspection",
        "calibration": "calibration",
        "documentation": "documentation",
    }.get(concern, concern)


# ---------------------------------------------------------------------------
# Step 3: Build title / description / resolution from candidate
# ---------------------------------------------------------------------------

def _build_root_cause_text(
    candidate: dict[str, Any],
    impact: ImpactSummary,
    model: OperationalModel,
) -> tuple[str, str, str, str]:
    """Return (concern_display, title, description, recommended_resolution)."""
    concern = candidate["concern"]
    concern_display = _QA_CONCERN_DISPLAY.get(concern, _format_label(concern))

    gate: QAGateState | None = candidate.get("gate")
    blocker: Blocker | None = candidate.get("blocker")

    ctx = model.domain_context.context_data
    vehicle = ctx.get("vehicle", {})
    oem = vehicle.get("oem", "OEM")

    # Title
    if concern == "joining":
        title = f"{oem} Joining Verification Unresolved"
    elif concern == "corrosion":
        title = "Corrosion Protection Requirements Not Cleared"
    elif concern == "components":
        title = "Component Replacement Verification Pending"
    elif concern == "dimensions":
        title = "Dimensional Verification Incomplete"
    elif concern == "calibration":
        title = "Post-Repair Calibration Not Cleared"
    elif concern == "material_safety":
        title = "Material Safety Requirements Unresolved"
    elif concern == "documentation":
        title = "Required Documentation Not Supplied"
    else:
        title = f"{_format_label(concern)} Requirements Unresolved"

    # Description (one sentence)
    qa_count = len(impact.blocked_qa)
    phase_count = len(impact.blocked_phases)

    if gate:
        check = _strip_ids(gate.check or "")
        desc = (
            f"An open {gate.priority}-priority QA gate requires {check.lower() or 'verification'} "
            f"before repair can proceed."
        )
    elif blocker:
        reason = _strip_ids(blocker.reason or "")
        desc = f"{reason or 'An unresolved requirement'} is preventing workflow progress."
    else:
        desc = f"Open {concern_display.lower()} requirements are blocking the repair workflow."

    if qa_count > 1:
        desc += f" {qa_count} related checks remain open."
    if phase_count > 0:
        phase_word = "phase" if phase_count == 1 else "phases"
        desc += f" This blocks {phase_count} repair {phase_word}."

    # Recommended resolution
    if gate:
        check = _strip_ids(gate.check or "")
        resolution = check if check else f"Clear the {concern_display.lower()} QA gate."
    elif blocker:
        reason = _strip_ids(blocker.reason or "")
        resolution = reason if reason else f"Resolve the {concern_display.lower()} requirement."
    else:
        resolution = f"Resolve all open {concern_display.lower()} requirements."

    if phase_count:
        names = ", ".join(impact.blocked_phases[:3])
        resolution = resolution.rstrip(".")
        resolution += f". Resolving this will unblock: {names}."

    return concern_display, title, desc, resolution


# ---------------------------------------------------------------------------
# Step 4: Priority from impact score
# ---------------------------------------------------------------------------

def _score_to_priority(score: int) -> str:
    if score >= 100:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Step 5: Confidence
# ---------------------------------------------------------------------------

def _build_confidence(candidate: dict[str, Any], model: OperationalModel) -> str:
    if candidate["type"] == "qa_gate" and model.state:
        gate = candidate["gate"]
        if gate and gate.priority == "critical":
            return "High"
        return "High"
    if candidate["type"] == "blocker":
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Step 6: Deduplication
# ---------------------------------------------------------------------------

def _jaccard_overlap(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _deduplicate(candidates_with_impact: list[tuple[dict, ImpactSummary, int, list[str]]]) -> list[tuple[dict, ImpactSummary, int, list[str]]]:
    """
    Merge candidates whose downstream impact sets overlap significantly.
    Lower-score candidate is absorbed into the higher-score one.
    """
    if len(candidates_with_impact) <= 1:
        return candidates_with_impact

    # Sort by score descending so we keep the most impactful as the anchor
    sorted_cands = sorted(candidates_with_impact, key=lambda x: x[2], reverse=True)

    kept: list[tuple[dict, ImpactSummary, int, list[str]]] = []
    absorbed: set[int] = set()

    for i, (cand_i, impact_i, score_i, ev_i) in enumerate(sorted_cands):
        if i in absorbed:
            continue
        set_i = set(impact_i.blocked_phases) | set(impact_i.blocked_qa)
        for j, (cand_j, impact_j, score_j, ev_j) in enumerate(sorted_cands):
            if j <= i or j in absorbed:
                continue
            set_j = set(impact_j.blocked_phases) | set(impact_j.blocked_qa)
            if _jaccard_overlap(set_i, set_j) > 0.5:
                absorbed.add(j)
                # Merge evidence and findings into the anchor
                ev_i = list(dict.fromkeys(ev_i + ev_j))
                new_findings = [f for f in impact_j.affected_findings if f not in impact_i.affected_findings]
                impact_i.affected_findings.extend(new_findings)

        kept.append((cand_i, impact_i, score_i, ev_i))

    return kept


# ---------------------------------------------------------------------------
# Step 7: Summary text
# ---------------------------------------------------------------------------

def _build_summary(root_causes: list[RootCause], model: OperationalModel) -> tuple[str, str]:
    if not root_causes:
        return "No root causes identified.", ""

    critical = [rc for rc in root_causes if rc.priority == "critical"]
    high = [rc for rc in root_causes if rc.priority == "high"]

    if critical:
        count = len(critical)
        noun = "Root Cause" if count == 1 else "Root Causes"
        summary = f"Repair blocked by {count} Critical {noun}"
    elif high:
        count = len(high)
        noun = "Root Cause" if count == 1 else "Root Causes"
        summary = f"Repair blocked by {count} High-Priority {noun}"
    else:
        summary = f"Repair has {len(root_causes)} open issue{'s' if len(root_causes) != 1 else ''}"

    # Detail: unblocking leverage
    top = root_causes[0]
    phase_count = len(top.impact.unblocked_phases)
    qa_count = len(top.impact.blocked_qa)
    detail_parts: list[str] = []
    if phase_count:
        detail_parts.append(f"unblocks {phase_count} repair {'phase' if phase_count == 1 else 'phases'}")
    if qa_count:
        detail_parts.append(f"clears {qa_count} open QA {'gate' if qa_count == 1 else 'gates'}")

    detail = (f"Resolving '{top.title}' " + " and ".join(detail_parts) + ".") if detail_parts else ""
    return summary, detail


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_root_cause_analysis(model: OperationalModel) -> RootCauseAnalysis:
    """
    Project an OperationalModel into a RootCauseAnalysis.

    Deterministic, no LLMs, read-only.
    """
    if not model.state:
        return RootCauseAnalysis(
            root_causes=[],
            total_impact_score=0,
            summary="No repair state available for root cause analysis.",
            summary_detail="",
            open_qa_count=0,
            open_blocker_count=0,
            blocked_phase_count=0,
            collapsed_finding_count=0,
        )

    state = model.state

    # Raw counts for summary
    open_qa_count = sum(1 for g in state.qa_gates if g.status == "open" and g.blocks_completion)
    open_blocker_count = sum(1 for b in state.blockers if b.status == "open")
    blocked_phase_count = sum(1 for p in state.phases if p.status == "blocked")

    # Step 1: Seed candidates
    candidates = _seed_candidates(model)

    if not candidates:
        return RootCauseAnalysis(
            root_causes=[],
            total_impact_score=0,
            summary="No blocking root causes identified.",
            summary_detail="",
            open_qa_count=open_qa_count,
            open_blocker_count=open_blocker_count,
            blocked_phase_count=blocked_phase_count,
            collapsed_finding_count=0,
        )

    # Step 2: Build impact for each candidate
    candidates_with_impact: list[tuple[dict, ImpactSummary, int, list[str]]] = []
    for cand in candidates:
        impact, score, ev = _build_impact(cand, model)
        candidates_with_impact.append((cand, impact, score, ev))

    # Step 3: Deduplicate
    deduplicated = _deduplicate(candidates_with_impact)

    # Sort by score descending
    deduplicated.sort(key=lambda x: x[2], reverse=True)

    # Filter out low-signal root causes: need either blocked QA gates or blocked phases
    deduplicated = [
        (cand, impact, score, ev)
        for cand, impact, score, ev in deduplicated
        if score >= 75 or impact.blocked_qa or impact.blocked_phases
    ]

    # Step 4: Build RootCause objects (cap at MAX_ROOT_CAUSES)
    root_causes: list[RootCause] = []
    for idx, (cand, impact, score, ev) in enumerate(deduplicated[:MAX_ROOT_CAUSES]):
        concern_display, title, description, resolution = _build_root_cause_text(cand, impact, model)
        priority = _score_to_priority(score)
        confidence = _build_confidence(cand, model)
        concern = cand["concern"]

        rc = RootCause(
            root_cause_id=f"rc:{concern}:{idx + 1}",
            concern_group=concern,
            concern_display=concern_display,
            title=title,
            description=description,
            recommended_resolution=resolution,
            priority=priority,
            impact_score=score,
            impact=impact,
            supporting_evidence=ev[:5],
            confidence=confidence,
        )
        root_causes.append(rc)

    total_score = sum(rc.impact_score for rc in root_causes)

    # How many raw findings were collapsed into root causes
    all_findings = len(model.insights.findings) if model.insights else 0
    attributed_findings = sum(len(rc.impact.affected_findings) for rc in root_causes)
    collapsed_count = max(0, all_findings - max(0, all_findings - attributed_findings))

    summary, detail = _build_summary(root_causes, model)

    return RootCauseAnalysis(
        root_causes=root_causes,
        total_impact_score=total_score,
        summary=summary,
        summary_detail=detail,
        open_qa_count=open_qa_count,
        open_blocker_count=open_blocker_count,
        blocked_phase_count=blocked_phase_count,
        collapsed_finding_count=all_findings,
    )
