"""
Lightweight heuristic classifier for OEM repair packet intake.

Classifies files by document role and detects OEM/vehicle metadata using
keyword heuristics only. No external AI services, no OCR libraries, no ML.

All outputs carry explicit confidence scores and uncertainty signals.
RepairGraph does not guarantee classification accuracy and recommends human
review of all intake manifests before proceeding to normalization.

Advisory: RepairGraph processes OEM repair information supplied by authorized
users. It is not an OEM document distribution platform. Classification
heuristics are subject to error and are not a substitute for qualified review.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from repairgraph.intake.schema import (
    SUPPORTED_EXTENSIONS,
    IntakeDiagnostic,
    IntakeFile,
    IntakeManifest,
    IntakePacket,
    _INTAKE_ADVISORY,
)

# ── OEM keyword patterns ───────────────────────────────────────────────────────

_OEM_PATTERNS: dict[str, list[str]] = {
    "Honda": [r"\bhonda\b", r"\bacura\b"],
    "Toyota": [r"\btoyota\b", r"\blexus\b", r"\bscion\b"],
    "Ford": [r"\bford motor\b", r"\bford\b", r"\blincoln\b"],
    "GM": [r"\bgeneral motors\b", r"\bchevrolet\b", r"\bgmc\b", r"\bbuick\b", r"\bcadillac\b"],
    "Nissan": [r"\bnissan\b", r"\binfiniti\b"],
    "Subaru": [r"\bsubaru\b"],
    "Volkswagen": [r"\bvolkswagen\b", r"\bvw\b", r"\baudi\b", r"\bporsche\b"],
    "BMW": [r"\bbmw\b", r"\bmini cooper\b"],
    "Mercedes": [r"\bmercedes\b", r"\bmercedes-benz\b", r"\bmbz\b"],
    "Stellantis": [r"\bstellantis\b", r"\bchrysler\b", r"\bdodge\b", r"\bjeep\b", r"\bram\b"],
    "Hyundai": [r"\bhyundai\b", r"\bkia\b", r"\bgenesis\b"],
    "Mazda": [r"\bmazda\b"],
    "Mitsubishi": [r"\bmitsubishi\b"],
    "Volvo": [r"\bvolvo\b"],
    "Rivian": [r"\brivian\b"],
    "Tesla": [r"\btesla\b"],
}

_MODEL_PATTERNS: dict[str, list[str]] = {
    "Honda": [
        r"\baccord\b", r"\bcivic\b", r"\bcr-v\b", r"\bcrv\b", r"\bpilot\b",
        r"\bodyssey\b", r"\bridgeline\b", r"\bhr-v\b", r"\bpassport\b", r"\binsight\b",
    ],
    "Toyota": [
        r"\bcamry\b", r"\bcorolla\b", r"\brav4\b", r"\btacoma\b", r"\btundra\b",
        r"\bprius\b", r"\bhighlander\b", r"\b4runner\b", r"\bsienna\b", r"\bvenza\b",
    ],
    "Ford": [
        r"\bf-150\b", r"\bf150\b", r"\bmustang\b", r"\bexplorer\b", r"\bescape\b",
        r"\branger\b", r"\bexpedition\b", r"\bbronco\b", r"\bedge\b", r"\bfusion\b",
    ],
    "GM": [
        r"\bsilverado\b", r"\bcolorado\b", r"\bmalibu\b", r"\bequinox\b",
        r"\btraverse\b", r"\btahoe\b", r"\bsuburban\b", r"\bblazer\b",
    ],
    "Nissan": [
        r"\baltima\b", r"\bsentra\b", r"\brogue\b", r"\bmurano\b",
        r"\bpathfinder\b", r"\bfrontier\b", r"\btitan\b", r"\bmaxima\b",
    ],
    "Subaru": [
        r"\boutback\b", r"\bforester\b", r"\bcrosstrek\b", r"\bimpreza\b",
        r"\blegacy\b", r"\bwrx\b", r"\bascent\b",
    ],
    "Volkswagen": [
        r"\bjetta\b", r"\bpassat\b", r"\btiguan\b", r"\bid\.?4\b", r"\bgolf\b",
        r"\batlas\b", r"\barteon\b",
    ],
    "Hyundai": [
        r"\bsonata\b", r"\belantra\b", r"\btucson\b", r"\bsanta fe\b",
        r"\bpalisade\b", r"\bkona\b", r"\bioniq\b",
    ],
    "BMW": [r"\b3 series\b", r"\b5 series\b", r"\b7 series\b", r"\bx3\b", r"\bx5\b"],
    "Mercedes": [r"\bc-class\b", r"\be-class\b", r"\bs-class\b", r"\bglc\b", r"\bgle\b"],
    "Stellantis": [
        r"\bwrangler\b", r"\bram 1500\b", r"\bram 2500\b",
        r"\bcharger\b", r"\bchallenger\b", r"\bdurango\b",
    ],
}

_OPERATION_PATTERNS: list[tuple[str, str]] = [
    (r"quarter panel replacement", "quarter_panel_replacement"),
    (r"quarter panel", "quarter_panel_replacement"),
    (r"bed side.*panel\b|panel.*bed side", "bed_side_panel_replacement"),
    (r"outer panel replacement", "outer_panel_replacement"),
    (r"roof panel", "roof_panel_replacement"),
    (r"door replacement|door removal", "door_replacement"),
    (r"hood replacement|hood removal", "hood_replacement"),
    (r"fender replacement|fender removal", "fender_replacement"),
    (r"bumper.*replacement|bumper.*removal", "bumper_replacement"),
    (r"floor panel", "floor_panel_replacement"),
    (r"\bsectioning\b", "panel_sectioning"),
    (r"frame repair", "frame_repair"),
    (r"unibody repair", "unibody_repair"),
    (r"rocker panel", "rocker_panel_replacement"),
    (r"pillar replacement|pillar repair", "pillar_replacement"),
]

# ── Document role keyword sets ─────────────────────────────────────────────────

_ROLE_KEYWORD_SETS: dict[str, list[str]] = {
    "repair_procedure": [
        r"\bremoval\b", r"\binstallation\b", r"\breplacement procedure\b",
        r"\brepair procedure\b", r"\bdisassembly\b", r"\breassembly\b",
        r"\bstep \d+\b", r"\bprocedure\b",
    ],
    "sectioning": [
        r"\bsection cut\b", r"\bsectioning\b", r"\bpanel sectioning\b",
        r"\bbutt joint\b", r"\blap joint\b", r"\bcut line\b", r"\boverlap\b",
    ],
    "welding": [
        r"\bweld\b", r"\bwelding\b", r"\bmig\b", r"\bmag\b",
        r"\bspot weld\b", r"\bweld point\b", r"\bweld nugget\b",
        r"\bplug weld\b", r"\bbraz[ei]\b", r"\bresistance spot\b",
    ],
    "corrosion_protection": [
        r"\bcorrosion\b", r"\banti-corrosion\b", r"\brust prevention\b",
        r"\bsealer\b", r"\bprimer\b", r"\bcavity wax\b", r"\bzinc\b",
        r"\bgalvaniz\b",
    ],
    "materials": [
        r"\bmaterial\b", r"\btensile strength\b", r"\buhss\b", r"\bhss\b",
        r"\bhigh strength steel\b", r"\bmpa\b", r"\byield strength\b",
        r"\bmild steel\b", r"\baluminum alloy\b", r"\bbake hardening\b",
    ],
    "dimensions": [
        r"\bdimension\b", r"\bmeasurement\b", r"\btolerance\b",
        r"\bgap\b", r"\bclearance\b", r"\b\d+\.?\d*\s*mm\b",
        r"\bspecification\b", r"\bpanel gap\b",
    ],
    "calibration": [
        r"\bcalibration\b", r"\badas\b", r"\bcamera calibration\b",
        r"\bsensor\b", r"\bradar\b", r"\blidar\b", r"\balignment\b",
        r"\brecalibration\b",
    ],
    "precautions": [
        r"\bprecaution\b", r"\bwarning\b", r"\bcaution\b",
        r"\bdanger\b", r"\bsafety\b", r"\bdo not\b",
        r"\bwear protective\b", r"\bhazard\b",
    ],
}


# ── File reading ───────────────────────────────────────────────────────────────

def _read_file_text(path: Path) -> tuple[str, list[str], list[str]]:
    """Attempt to read file contents as text.

    Returns (text, warnings, errors). Never raises — all failures are captured
    in the returned lists.
    """
    warnings: list[str] = []
    errors: list[str] = []

    ext = path.suffix.lower()

    if ext == ".pdf":
        try:
            raw = path.read_bytes()
            # Extract printable ASCII runs embedded in PDF binary stream
            chunks = re.findall(rb"[\x20-\x7e]{6,}", raw)
            text = " ".join(c.decode("ascii", errors="replace") for c in chunks)
            if len(text.strip()) < 40:
                warnings.append(
                    "PDF text extraction yielded minimal content. "
                    "File may be image-only or scanned. Provide text-format documents for best results."
                )
            else:
                warnings.append(
                    "PDF text extracted via heuristic byte scanning. "
                    "Accuracy is limited compared to text-format documents."
                )
        except OSError as exc:
            errors.append(f"Could not read PDF: {exc}")
            text = ""
        return text, warnings, errors

    # Text-based files: try common encodings
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding), warnings, errors
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            errors.append(f"Could not read file: {exc}")
            return "", warnings, errors

    warnings.append(
        "File could not be decoded as UTF-8, latin-1, or CP1252. "
        "Content may be binary or use an unsupported encoding."
    )
    try:
        text = path.read_bytes().decode("ascii", errors="replace")
    except OSError as exc:
        errors.append(f"Could not read file bytes: {exc}")
        text = ""
    return text, warnings, errors


# ── Role and metadata detection ────────────────────────────────────────────────

def detect_document_role(text: str) -> str:
    """Detect document role from text content using keyword heuristics.

    Returns one of the DOCUMENT_ROLES strings. Returns "unknown" when no
    signal is found. Does not guarantee accuracy — outputs require human review.
    """
    if not text or not text.strip():
        return "unknown"

    lower = text.lower()
    role_scores: dict[str, int] = {}

    for role, patterns in _ROLE_KEYWORD_SETS.items():
        score = 0
        for pat in patterns:
            try:
                score += len(re.findall(pat, lower))
            except re.error:
                score += lower.count(pat)
        if score > 0:
            role_scores[role] = score

    if not role_scores:
        return "unknown"

    return max(role_scores, key=lambda r: role_scores[r])


def detect_oem_metadata(text: str) -> dict[str, Any]:
    """Detect OEM, model, year, and operation from text heuristics.

    Returns a dict with keys: oem, model, year, operation, confidence.
    All values may be None if undetected. confidence is a float in [0.0, 1.0].
    Does not guarantee accuracy.
    """
    if not text or not text.strip():
        return {"oem": None, "model": None, "year": None, "operation": None, "confidence": 0.0}

    lower = text.lower()
    result: dict[str, Any] = {
        "oem": None, "model": None, "year": None, "operation": None, "confidence": 0.0,
    }

    # OEM scoring
    oem_scores: dict[str, int] = {}
    for oem, patterns in _OEM_PATTERNS.items():
        score = 0
        for pat in patterns:
            try:
                score += len(re.findall(pat, lower))
            except re.error:
                score += lower.count(pat)
        if score > 0:
            oem_scores[oem] = score

    if oem_scores:
        result["oem"] = max(oem_scores, key=lambda k: oem_scores[k])
        top = oem_scores[result["oem"]]
        result["confidence"] = min(0.85, 0.30 + top * 0.12)

    # Model scoring — search within detected OEM first, then all
    candidate_oem = result["oem"]
    search_oems = [candidate_oem] if candidate_oem and candidate_oem in _MODEL_PATTERNS else list(_MODEL_PATTERNS.keys())
    model_hits: dict[str, int] = {}
    for oem in search_oems:
        for pat in _MODEL_PATTERNS.get(oem, []):
            try:
                hits = len(re.findall(pat, lower))
            except re.error:
                hits = lower.count(pat)
            if hits > 0:
                model_hits[pat] = model_hits.get(pat, 0) + hits

    if model_hits:
        best_pat = max(model_hits, key=lambda k: model_hits[k])
        # Clean pattern to a readable name
        result["model"] = (
            best_pat
            .replace(r"\b", "").replace("\\b", "")
            .replace(r"\.?", ".").strip()
        )

    # Year detection — plausible range
    years_found = re.findall(r"\b(19[89]\d|20[0-3]\d)\b", text)
    if years_found:
        year_counts = Counter(int(y) for y in years_found)
        result["year"] = max(year_counts, key=lambda y: (year_counts[y], y))

    # Operation detection
    for pat, operation in _OPERATION_PATTERNS:
        try:
            if re.search(pat, lower):
                result["operation"] = operation
                break
        except re.error:
            if pat in lower:
                result["operation"] = operation
                break

    return result


# ── File and packet classification ────────────────────────────────────────────

def _make_file_id(path: Path) -> str:
    """Deterministic short file ID from filename."""
    return "file_" + hashlib.md5(path.name.encode()).hexdigest()[:8]


def classify_intake_file(path: Path) -> IntakeFile:
    """Classify a single file for OEM intake.

    Reads file content, detects document role and OEM/vehicle metadata using
    lightweight heuristics. Returns an IntakeFile with confidence scores,
    warnings, and errors. Never crashes on unreadable files.
    """
    path = Path(path)
    file_id = _make_file_id(path)
    ext = path.suffix.lower()
    warnings: list[str] = []
    errors: list[str] = []

    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0
        errors.append("Could not stat file; size unknown.")

    if size_bytes == 0 and not errors:
        warnings.append("File is empty.")

    if ext not in SUPPORTED_EXTENSIONS:
        warnings.append(
            f"Extension {ext!r} is not a recognized intake format "
            f"(supported: .txt, .pdf, .md, .json, .csv). "
            "Classification confidence will be very low."
        )

    text, read_warnings, read_errors = _read_file_text(path)
    warnings.extend(read_warnings)
    errors.extend(read_errors)

    if read_errors:
        return IntakeFile(
            file_id=file_id,
            filename=path.name,
            extension=ext,
            size_bytes=size_bytes,
            document_role="unknown",
            confidence=0.0,
            warnings=warnings,
            errors=errors,
        )

    role = detect_document_role(text)
    metadata = detect_oem_metadata(text)

    confidence = metadata["confidence"]
    if role == "unknown":
        confidence = max(0.0, confidence - 0.1)
    if not text.strip():
        confidence = 0.0
    if ext == ".pdf":
        confidence = min(confidence, 0.60)
    if ext not in SUPPORTED_EXTENSIONS:
        confidence = min(confidence, 0.20)

    return IntakeFile(
        file_id=file_id,
        filename=path.name,
        extension=ext,
        size_bytes=size_bytes,
        detected_oem=metadata["oem"],
        detected_model=metadata["model"],
        detected_year=metadata["year"],
        detected_operation=metadata["operation"],
        document_role=role,
        confidence=round(confidence, 3),
        warnings=warnings,
        errors=errors,
    )


def _weighted_consensus(values: list[Any], weights: list[float]) -> Any:
    """Return the highest-weight non-None value."""
    scored: dict[Any, float] = {}
    for val, w in zip(values, weights):
        if val is not None:
            scored[val] = scored.get(val, 0.0) + w
    return max(scored, key=lambda k: scored[k]) if scored else None


def classify_intake_packet(paths: list[Path]) -> IntakeManifest:
    """Classify a collection of files as a repair packet.

    Classifies each file, aggregates metadata, identifies detected and missing
    document roles, and assembles a complete IntakeManifest. Handles empty
    lists and unreadable files gracefully.
    """
    intake_id = "intake_" + str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()

    paths = [Path(p) for p in paths]
    files: list[IntakeFile] = []
    diagnostics: list[IntakeDiagnostic] = []

    for path in paths:
        if not path.exists():
            diagnostics.append(IntakeDiagnostic(
                code="FILE_NOT_FOUND",
                severity="error",
                message=f"File not found: {path.name}",
                detail=str(path),
            ))
            continue
        f = classify_intake_file(path)
        files.append(f)
        for w in f.warnings:
            diagnostics.append(IntakeDiagnostic(
                code="FILE_WARNING", severity="warning", message=w, file_id=f.file_id,
            ))
        for e in f.errors:
            diagnostics.append(IntakeDiagnostic(
                code="FILE_ERROR", severity="error", message=e, file_id=f.file_id,
            ))

    readable = [f for f in files if not f.errors]
    detected_roles = sorted({f.document_role for f in readable if f.document_role != "unknown"})
    weights = [f.confidence for f in readable]

    detected_oem = _weighted_consensus([f.detected_oem for f in readable], weights)
    detected_model = _weighted_consensus([f.detected_model for f in readable], weights)
    detected_year = _weighted_consensus([f.detected_year for f in readable], [1.0] * len(readable))
    detected_operation = _weighted_consensus([f.detected_operation for f in readable], weights)
    avg_conf = sum(weights) / len(weights) if weights else 0.0

    detected_packet = IntakePacket(
        detected_oem=detected_oem,
        detected_model=detected_model,
        detected_year=detected_year,
        detected_operation=detected_operation,
        oem_confidence=round(avg_conf, 3),
        detected_roles=detected_roles,
        file_count=len(files),
    )

    _ESSENTIAL = {"repair_procedure"}
    _USEFUL = {"welding", "corrosion_protection", "materials"}
    found_set = set(detected_roles)
    missing_roles = sorted((_ESSENTIAL | _USEFUL) - found_set)

    # Readiness
    if not files:
        readiness = "unprocessable"
    elif all(f.errors for f in files):
        readiness = "unprocessable"
    elif not readable:
        readiness = "unprocessable"
    elif "repair_procedure" in found_set and len(found_set) >= 2:
        readiness = "partial" if any(f.errors for f in files) else "ready"
    elif "repair_procedure" in found_set or found_set:
        readiness = "partial"
    else:
        readiness = "incomplete"

    # Cross-file OEM conflict check
    oem_vals = [f.detected_oem for f in readable if f.detected_oem]
    if len(set(oem_vals)) > 1:
        diagnostics.append(IntakeDiagnostic(
            code="OEM_CONFLICT",
            severity="warning",
            message=(
                f"Conflicting OEM detections across files: {sorted(set(oem_vals))}. "
                "Files may be from different OEMs or repair manuals."
            ),
        ))

    if not detected_oem:
        diagnostics.append(IntakeDiagnostic(
            code="OEM_UNDETECTED",
            severity="warning",
            message="No OEM could be confidently detected from the supplied files.",
        ))

    if "repair_procedure" not in found_set:
        diagnostics.append(IntakeDiagnostic(
            code="MISSING_PROCEDURE",
            severity="warning",
            message=(
                "No repair_procedure document detected. "
                "A procedure document is required for normalization."
            ),
        ))

    return IntakeManifest(
        intake_id=intake_id,
        files=files,
        detected_packet=detected_packet,
        missing_roles=missing_roles,
        diagnostics=diagnostics,
        readiness=readiness,
        created_at=created_at,
    )


def summarize_intake_manifest(manifest: IntakeManifest) -> dict[str, Any]:
    """Return a compact summary dict from an IntakeManifest."""
    error_count = sum(1 for d in manifest.diagnostics if d.severity == "error")
    warning_count = sum(1 for d in manifest.diagnostics if d.severity == "warning")
    readable = [f for f in manifest.files if not f.errors]

    return {
        "intake_id": manifest.intake_id,
        "readiness": manifest.readiness,
        "file_count": len(manifest.files),
        "readable_file_count": len(readable),
        "detected_oem": manifest.detected_packet.detected_oem,
        "detected_model": manifest.detected_packet.detected_model,
        "detected_year": manifest.detected_packet.detected_year,
        "detected_operation": manifest.detected_packet.detected_operation,
        "oem_confidence": manifest.detected_packet.oem_confidence,
        "detected_roles": manifest.detected_packet.detected_roles,
        "missing_roles": manifest.missing_roles,
        "diagnostic_count": len(manifest.diagnostics),
        "error_count": error_count,
        "warning_count": warning_count,
        "advisory": manifest.advisory,
    }
