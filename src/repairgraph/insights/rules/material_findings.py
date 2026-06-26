"""Material classification insight rules (UHSS, HSS, joining verification)."""
from __future__ import annotations

from repairgraph.insights.schema import InsightFinding
from repairgraph.state.schema import RepairState

_UHSS_VALUES = {"UHSS", "BORON"}


def _is_uhss(zone) -> bool:
    mc = zone.material_classification
    return bool(mc and mc.strip().upper() in _UHSS_VALUES)


def _is_hss(zone) -> bool:
    mc = zone.material_classification
    return bool(mc and mc.strip().upper() == "HSS")


def uhss_detected(state: RepairState) -> list[InsightFinding]:
    uhss_zones = [z for z in state.zones if _is_uhss(z)]
    if not uhss_zones:
        return []
    zone_labels = [z.label for z in uhss_zones]
    return [InsightFinding(
        finding_id="material_uhss_detected",
        severity="high",
        category="material",
        title=f"Ultra-High Strength Steel detected in {len(uhss_zones)} zone{'s' if len(uhss_zones) > 1 else ''}",
        explanation=(
            f"UHSS/boron steel is present in: {', '.join(zone_labels)}. "
            "This steel cannot be heat-straightened and requires OEM-specific repair procedures. "
            "Incorrect repair methods will compromise structural integrity."
        ),
        recommended_action=(
            "Verify OEM repair procedure allows sectioning or replacement (not straightening) for UHSS zones. "
            "Confirm approved joining methods and document compliance."
        ),
        supporting_evidence=tuple(
            f"{z.zone_id}={z.material_classification}" for z in uhss_zones
        ),
        confidence="high",
    )]


def hss_detected(state: RepairState) -> list[InsightFinding]:
    hss_zones = [z for z in state.zones if _is_hss(z)]
    if not hss_zones:
        return []
    zone_labels = [z.label for z in hss_zones]
    return [InsightFinding(
        finding_id="material_hss_detected",
        severity="medium",
        category="material",
        title=f"High Strength Steel present in {len(hss_zones)} zone{'s' if len(hss_zones) > 1 else ''}",
        explanation=(
            f"HSS zones identified: {', '.join(zone_labels)}. "
            "These require controlled heat application and specific welding parameters to avoid weakening the steel."
        ),
        recommended_action=(
            "Follow OEM heat limits for HSS repair. Verify MIG/MAG welding parameters and cool-down procedures. "
            "Document heat application per zone."
        ),
        supporting_evidence=tuple(
            f"{z.zone_id}=HSS" for z in hss_zones
        ),
        confidence="high",
    )]


def joining_verification_required(state: RepairState) -> list[InsightFinding]:
    uhss_zones = [z for z in state.zones if _is_uhss(z)]
    if not uhss_zones:
        return []
    joining_gates = [
        g for g in state.qa_gates
        if "joining" in g.category.lower() and g.status in ("open", "in_review")
    ]
    if not joining_gates:
        return []
    gate_ids = [g.gate_id for g in joining_gates]
    return [InsightFinding(
        finding_id="material_joining_verification_required",
        severity="high",
        category="material",
        title="Joining method verification required for UHSS zones",
        explanation=(
            f"{len(joining_gates)} joining compliance QA gate{'s' if len(joining_gates) > 1 else ''} "
            f"{'are' if len(joining_gates) > 1 else 'is'} open alongside UHSS-classified zones. "
            "UHSS joining must be verified against OEM-approved methods — improper joining is a structural safety risk."
        ),
        recommended_action=(
            "Confirm OEM joining specification (resistance spot weld count, rivet spec, or approved adhesive) "
            "for each UHSS zone. Close gates: " + ", ".join(gate_ids)
        ),
        supporting_evidence=(
            *[f"uhss_zone={z.zone_id}" for z in uhss_zones],
            *[f"open_gate={g.gate_id}" for g in joining_gates],
        ),
        confidence="high",
    )]
