"""Intake manifest insight rules."""
from __future__ import annotations

from repairgraph.insights.schema import InsightFinding

_CRITICAL_ROLES = {"repair_procedure", "materials", "corrosion_protection"}
_IMPORTANT_ROLES = {"welding", "dimensions", "calibration"}


def _missing_roles(manifest_dict: dict) -> list[str]:
    return manifest_dict.get("missing_roles", [])


def _readiness(manifest_dict: dict) -> str:
    return manifest_dict.get("readiness", "unknown")


def missing_critical_roles(manifest_dict: dict) -> list[InsightFinding]:
    missing = [r for r in _missing_roles(manifest_dict) if r in _CRITICAL_ROLES]
    if not missing:
        return []
    return [InsightFinding(
        finding_id="intake_missing_critical_roles",
        severity="high",
        category="intake",
        title=f"OEM packet missing critical document{'s' if len(missing) > 1 else ''}: {', '.join(missing)}",
        explanation=(
            f"The following document role{'s are' if len(missing) > 1 else ' is'} absent from the repair packet: "
            f"{', '.join(missing)}. Without these, technicians may rely on incorrect or incomplete procedures."
        ),
        recommended_action=(
            "Obtain missing documents from OEM service portal before authorizing repair to proceed. "
            f"Required: {', '.join(missing)}"
        ),
        supporting_evidence=tuple(f"missing_role={r}" for r in missing),
        confidence="high",
    )]


def missing_important_roles(manifest_dict: dict) -> list[InsightFinding]:
    missing = [r for r in _missing_roles(manifest_dict) if r in _IMPORTANT_ROLES]
    if not missing:
        return []
    return [InsightFinding(
        finding_id="intake_missing_important_roles",
        severity="medium",
        category="intake",
        title=f"Repair packet lacks supporting document{'s' if len(missing) > 1 else ''}: {', '.join(missing)}",
        explanation=(
            f"Supporting role{'s' if len(missing) > 1 else ''} not present: {', '.join(missing)}. "
            "These are not required to start but should be obtained before the corresponding repair phase."
        ),
        recommended_action=(
            "Source the missing documents before the relevant phase begins. "
            f"Missing: {', '.join(missing)}"
        ),
        supporting_evidence=tuple(f"missing_role={r}" for r in missing),
        confidence="high",
    )]


def intake_readiness_concern(manifest_dict: dict) -> list[InsightFinding]:
    readiness = _readiness(manifest_dict)
    if readiness in ("ready", "unknown"):
        return []
    severity = "high" if readiness in ("incomplete", "unprocessable") else "medium"
    label_map = {
        "partial": "Partial — some documents missing",
        "incomplete": "Incomplete — critical documents missing",
        "unprocessable": "Unprocessable — packet cannot be read",
    }
    label = label_map.get(readiness, readiness)
    return [InsightFinding(
        finding_id="intake_readiness_concern",
        severity=severity,
        category="intake",
        title=f"OEM intake packet readiness: {label}",
        explanation=(
            f"The repair packet has readiness status '{readiness}'. "
            "Proceeding without a complete packet increases the risk of non-compliant repairs."
        ),
        recommended_action=(
            "Review the intake diagnostics and source the missing documents before authorizing work."
            if readiness != "unprocessable"
            else "Re-upload the packet files in a supported format (PDF, text). Contact OEM for document access."
        ),
        supporting_evidence=(f"readiness={readiness}",),
        confidence="high",
    )]


def low_confidence_classifications(manifest_dict: dict) -> list[InsightFinding]:
    files = manifest_dict.get("files", [])
    low = [f for f in files if isinstance(f.get("confidence"), (int, float)) and f["confidence"] < 0.5]
    if not low:
        return []
    names = [f.get("filename", "unknown") for f in low]
    return [InsightFinding(
        finding_id="intake_low_confidence_files",
        severity="low",
        category="intake",
        title=f"{len(low)} file{'s' if len(low) > 1 else ''} classified with low confidence",
        explanation=(
            f"Classification confidence is below 50% for: {', '.join(names)}. "
            "These files may have been assigned incorrect document roles."
        ),
        recommended_action="Verify document roles for low-confidence files and re-upload if necessary.",
        supporting_evidence=tuple(
            f"{f.get('filename', 'unknown')}={f.get('confidence', 0):.0%}" for f in low
        ),
        confidence="low",
    )]


def conflicting_oem_metadata(manifest_dict: dict) -> list[InsightFinding]:
    files = manifest_dict.get("files", [])
    oems = {f.get("detected_oem") for f in files if f.get("detected_oem")}
    if len(oems) <= 1:
        return []
    return [InsightFinding(
        finding_id="intake_conflicting_oem",
        severity="medium",
        category="intake",
        title=f"Multiple OEM identifiers detected in repair packet ({len(oems)} OEMs)",
        explanation=(
            f"Files in this packet reference {len(oems)} different OEMs: {', '.join(sorted(oems))}. "
            "Mixed-OEM packets may indicate document mix-up or incorrect file inclusion."
        ),
        recommended_action=(
            "Verify that all documents belong to the same vehicle OEM. Remove any documents from other OEMs."
        ),
        supporting_evidence=tuple(f"oem={oem}" for oem in sorted(oems)),
        confidence="medium",
    )]
