"""
Lightweight heuristic classifier for OEM repair packet intake.

Classifies files by document role and detects OEM/vehicle metadata using
keyword heuristics only. No external AI services, no OCR libraries, no ML.

Metadata detection uses two evidence channels:
  - Filename evidence (high-signal): OEM/model/year/operation from filename tokens
  - Text evidence (lower-signal): OEM/model/year from extracted file content

Filename evidence takes priority when present. Isolated OEM mentions in long
noisy text receive a confidence penalty. Packet-level metadata is chosen by
weighted voting across all files, using filename evidence when available.

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
        r"\bodyssey\b", r"\bodysseu\b", r"\bridgeline\b", r"\bhr-v\b",
        r"\bpassport\b", r"\binsight\b",
    ],
    "Toyota": [
        r"\bcamry\b", r"\bcorolla\b", r"\brav4\b", r"\btacoma\b", r"\btundra\b",
        r"\bprius\b", r"\bhighlander\b", r"\b4runner\b", r"\bsienna\b", r"\bvenza\b",
    ],
    "Ford": [
        r"\bf-150\b", r"\bf150\b", r"\bmustang\b", r"\bexplorer\b", r"\bescape\b",
        r"\branger\b", r"\bexpedition\b", r"\bbronco\b", r"\bedge\b", r"\bfusion\b",
        r"\bsuperduty\b", r"\bsuper duty\b",
    ],
    "GM": [
        r"\bsilverado\b", r"\bcolorado\b", r"\bmalibu\b", r"\bequinox\b",
        r"\btraverse\b", r"\btahoe\b", r"\bsuburban\b", r"\bblazer\b",
        r"\bterrain\b", r"\benclave\b",
    ],
    "Nissan": [
        r"\baltima\b", r"\bsentra\b", r"\brogue\b", r"\bmurano\b",
        r"\bpathfinder\b", r"\bfrontier\b", r"\btitan\b", r"\bmaxima\b",
        r"\bversa\b", r"\bkicks\b",
    ],
    "Subaru": [
        r"\boutback\b", r"\bforester\b", r"\bcrosstrek\b", r"\bimpreza\b",
        r"\blegacy\b", r"\bwrx\b", r"\bascent\b", r"\bbaja\b",
    ],
    "Volkswagen": [
        r"\bjetta\b", r"\bpassat\b", r"\btiguan\b", r"\bid\.?4\b", r"\bgolf\b",
        r"\batlas\b", r"\barteon\b", r"\btaos\b",
    ],
    "Hyundai": [
        r"\bsonata\b", r"\belantra\b", r"\btucson\b", r"\bsanta fe\b",
        r"\bpalisade\b", r"\bkona\b", r"\bioniq\b", r"\bveloster\b",
    ],
    "BMW": [
        r"\b3 series\b", r"\b5 series\b", r"\b7 series\b", r"\bx3\b", r"\bx5\b",
        r"\bx1\b", r"\bx7\b", r"\bi4\b", r"\bix\b",
    ],
    "Mercedes": [
        r"\bc-class\b", r"\be-class\b", r"\bs-class\b", r"\bglc\b", r"\bgle\b",
        r"\bcla\b", r"\bgla\b", r"\bglb\b",
    ],
    "Stellantis": [
        r"\bwrangler\b", r"\bram 1500\b", r"\bram 2500\b",
        r"\bcharger\b", r"\bchallenger\b", r"\bdurango\b",
        r"\bpacifica\b", r"\bgrand cherokee\b",
    ],
    "Mazda": [
        r"\bcx-5\b", r"\bcx-9\b", r"\bcx-30\b", r"\bmazda3\b",
        r"\bmazda6\b", r"\bmx-5\b", r"\bmiata\b",
    ],
    "Mitsubishi": [
        r"\boutlander\b", r"\beclipse cross\b", r"\bgalant\b",
        r"\blancer\b", r"\bmirage\b",
    ],
    "Volvo": [
        r"\bxc60\b", r"\bxc90\b", r"\bs60\b", r"\bv60\b",
        r"\bxc40\b", r"\bc40\b",
    ],
    "Rivian": [r"\br1t\b", r"\br1s\b"],
    "Tesla": [
        r"\bmodel 3\b", r"\bmodel s\b", r"\bmodel x\b", r"\bmodel y\b",
        r"\bcybertruck\b",
    ],
}

# Canonical model names: {oem: {pattern: display_name}}
# Patterns must exactly match those in _MODEL_PATTERNS.
_MODEL_CANONICAL: dict[str, dict[str, str]] = {
    "Honda": {
        r"\baccord\b": "Accord", r"\bcivic\b": "Civic", r"\bcr-v\b": "CR-V",
        r"\bcrv\b": "CR-V", r"\bpilot\b": "Pilot", r"\bodyssey\b": "Odyssey",
        r"\bodysseu\b": "Odyssey", r"\bridgeline\b": "Ridgeline",
        r"\bhr-v\b": "HR-V", r"\bpassport\b": "Passport", r"\binsight\b": "Insight",
    },
    "Toyota": {
        r"\bcamry\b": "Camry", r"\bcorolla\b": "Corolla", r"\brav4\b": "RAV4",
        r"\btacoma\b": "Tacoma", r"\btundra\b": "Tundra", r"\bprius\b": "Prius",
        r"\bhighlander\b": "Highlander", r"\b4runner\b": "4Runner",
        r"\bsienna\b": "Sienna", r"\bvenza\b": "Venza",
    },
    "Ford": {
        r"\bf-150\b": "F-150", r"\bf150\b": "F-150", r"\bmustang\b": "Mustang",
        r"\bexplorer\b": "Explorer", r"\bescape\b": "Escape",
        r"\branger\b": "Ranger", r"\bexpedition\b": "Expedition",
        r"\bbronco\b": "Bronco", r"\bedge\b": "Edge", r"\bfusion\b": "Fusion",
        r"\bsuperduty\b": "Super Duty", r"\bsuper duty\b": "Super Duty",
    },
    "GM": {
        r"\bsilverado\b": "Silverado", r"\bcolorado\b": "Colorado",
        r"\bmalibu\b": "Malibu", r"\bequinox\b": "Equinox",
        r"\btraverse\b": "Traverse", r"\btahoe\b": "Tahoe",
        r"\bsuburban\b": "Suburban", r"\bblazer\b": "Blazer",
        r"\bterrain\b": "Terrain", r"\benclave\b": "Enclave",
    },
    "Nissan": {
        r"\baltima\b": "Altima", r"\bsentra\b": "Sentra", r"\brogue\b": "Rogue",
        r"\bmurano\b": "Murano", r"\bpathfinder\b": "Pathfinder",
        r"\bfrontier\b": "Frontier", r"\btitan\b": "Titan",
        r"\bmaxima\b": "Maxima", r"\bversa\b": "Versa", r"\bkicks\b": "Kicks",
    },
    "Subaru": {
        r"\boutback\b": "Outback", r"\bforester\b": "Forester",
        r"\bcrosstrek\b": "Crosstrek", r"\bimpreza\b": "Impreza",
        r"\blegacy\b": "Legacy", r"\bwrx\b": "WRX",
        r"\bascent\b": "Ascent", r"\bbaja\b": "Baja",
    },
    "Volkswagen": {
        r"\bjetta\b": "Jetta", r"\bpassat\b": "Passat", r"\btiguan\b": "Tiguan",
        r"\bid\.?4\b": "ID.4", r"\bgolf\b": "Golf",
        r"\batlas\b": "Atlas", r"\barteon\b": "Arteon", r"\btaos\b": "Taos",
    },
    "Hyundai": {
        r"\bsonata\b": "Sonata", r"\belantra\b": "Elantra", r"\btucson\b": "Tucson",
        r"\bsanta fe\b": "Santa Fe", r"\bpalisade\b": "Palisade",
        r"\bkona\b": "Kona", r"\bioniq\b": "Ioniq", r"\bveloster\b": "Veloster",
    },
    "BMW": {
        r"\b3 series\b": "3 Series", r"\b5 series\b": "5 Series",
        r"\b7 series\b": "7 Series", r"\bx3\b": "X3", r"\bx5\b": "X5",
        r"\bx1\b": "X1", r"\bx7\b": "X7", r"\bi4\b": "i4", r"\bix\b": "iX",
    },
    "Mercedes": {
        r"\bc-class\b": "C-Class", r"\be-class\b": "E-Class",
        r"\bs-class\b": "S-Class", r"\bglc\b": "GLC", r"\bgle\b": "GLE",
        r"\bcla\b": "CLA", r"\bgla\b": "GLA", r"\bglb\b": "GLB",
    },
    "Stellantis": {
        r"\bwrangler\b": "Wrangler", r"\bram 1500\b": "Ram 1500",
        r"\bram 2500\b": "Ram 2500", r"\bcharger\b": "Charger",
        r"\bchallenger\b": "Challenger", r"\bdurango\b": "Durango",
        r"\bpacifica\b": "Pacifica", r"\bgrand cherokee\b": "Grand Cherokee",
    },
    "Mazda": {
        r"\bcx-5\b": "CX-5", r"\bcx-9\b": "CX-9", r"\bcx-30\b": "CX-30",
        r"\bmazda3\b": "Mazda3", r"\bmazda6\b": "Mazda6",
        r"\bmx-5\b": "MX-5", r"\bmiata\b": "MX-5 Miata",
    },
    "Mitsubishi": {
        r"\boutlander\b": "Outlander", r"\beclipse cross\b": "Eclipse Cross",
        r"\bgalant\b": "Galant", r"\blancer\b": "Lancer", r"\bmirage\b": "Mirage",
    },
    "Volvo": {
        r"\bxc60\b": "XC60", r"\bxc90\b": "XC90", r"\bs60\b": "S60",
        r"\bv60\b": "V60", r"\bxc40\b": "XC40", r"\bc40\b": "C40",
    },
    "Rivian": {r"\br1t\b": "R1T", r"\br1s\b": "R1S"},
    "Tesla": {
        r"\bmodel 3\b": "Model 3", r"\bmodel s\b": "Model S",
        r"\bmodel x\b": "Model X", r"\bmodel y\b": "Model Y",
        r"\bcybertruck\b": "Cybertruck",
    },
}

# Reverse lookup: canonical model name → OEM.
# Used for model-to-OEM inference when a filename or text identifies the model
# but not the OEM (e.g. filename "2023 Elantra quarter panel.pdf" has no "Hyundai").
# Must NOT be used inside _extract_filename_metadata — that function must return
# oem=None for model-only filenames so that existing tests remain valid.
_MODEL_TO_OEM: dict[str, str] = {
    canonical: oem
    for oem, canon_map in _MODEL_CANONICAL.items()
    for canonical in canon_map.values()
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

# Fallback: infer document role from detected operation when text extraction is
# too sparse to yield role signals.  Only fires when role == "unknown".
# Panel operations → repair_procedure; sectioning → sectioning.
_OPERATION_TO_ROLE: dict[str, str] = {
    "quarter_panel_replacement": "repair_procedure",
    "bed_side_panel_replacement": "repair_procedure",
    "outer_panel_replacement": "repair_procedure",
    "roof_panel_replacement": "repair_procedure",
    "door_replacement": "repair_procedure",
    "hood_replacement": "repair_procedure",
    "fender_replacement": "repair_procedure",
    "bumper_replacement": "repair_procedure",
    "floor_panel_replacement": "repair_procedure",
    "panel_sectioning": "sectioning",
    "frame_repair": "repair_procedure",
    "unibody_repair": "repair_procedure",
    "rocker_panel_replacement": "repair_procedure",
    "pillar_replacement": "repair_procedure",
}

# ── Document role keyword sets ─────────────────────────────────────────────────

_ROLE_KEYWORD_SETS: dict[str, list[str]] = {
    "repair_procedure": [
        r"\bremoval\b", r"\binstallation\b", r"\breplacement procedure\b",
        r"\brepair procedure\b", r"\bdisassembly\b", r"\breassembly\b",
        r"\bstep \d+\b", r"\bprocedure\b",
        r"\bremove and install\b", r"\bremove and replace\b",
        r"\bremoval and replacement\b", r"\bremoval and installation\b",
        r"\bservice and repair\b", r"\bdrilling\b", r"\bdisconnect\b",
        r"\breinstall\b", r"\btorque spec\b",
    ],
    "sectioning": [
        r"\bsection cut\b", r"\bsectioning\b", r"\bpanel sectioning\b",
        r"\bbutt joint\b", r"\blap joint\b", r"\bcut line\b", r"\boverlap\b",
        r"\bsection location\b", r"\bno cut zone\b", r"\bsplice\b",
        r"\btransition area\b", r"\bpartial replacement\b",
    ],
    "welding": [
        r"\bweld\b", r"\bwelding\b", r"\bmig\b", r"\bmag\b",
        r"\bspot weld\b", r"\bweld point\b", r"\bweld nugget\b",
        r"\bplug weld\b", r"\bbraz[ei]\b", r"\bresistance spot\b",
        r"\bweld diagram\b", r"\bweld schedule\b", r"\bweld flange\b",
        r"\bsrsw\b", r"\bnumber of weld\b", r"\bheat affected zone\b",
    ],
    "corrosion_protection": [
        r"\bcorrosion\b", r"\banti-corrosion\b", r"\brust prevention\b",
        r"\bsealer\b", r"\bprimer\b", r"\bcavity wax\b", r"\bzinc\b",
        r"\bgalvaniz\b",
        r"\brust preventative\b", r"\bbody sealant\b", r"\bunderbody\b",
        r"\bseam sealer\b", r"\belectrocoat\b", r"\bcorrosion protection\b",
    ],
    "materials": [
        r"\bmaterial\b", r"\btensile strength\b", r"\buhss\b", r"\bhss\b",
        r"\bhigh strength steel\b", r"\bmpa\b", r"\byield strength\b",
        r"\bmild steel\b", r"\baluminum alloy\b", r"\bbake hardening\b",
        r"\bsteel grade\b", r"\bahss\b", r"\bdual.phase\b",
        r"\bboron steel\b", r"\bmaterial specification\b",
        r"\bultra.high.strength\b",
    ],
    "dimensions": [
        r"\bdimension\b", r"\bmeasurement\b", r"\btolerance\b",
        r"\bgap\b", r"\bclearance\b", r"\b\d+\.?\d*\s*mm\b",
        r"\bspecification\b", r"\bpanel gap\b",
        r"\bbody line\b", r"\bflush\b", r"\breference point\b", r"\bdatum\b",
    ],
    "calibration": [
        r"\bcalibration\b", r"\badas\b", r"\bcamera calibration\b",
        r"\bsensor\b", r"\bradar\b", r"\blidar\b", r"\balignment\b",
        r"\brecalibration\b",
        r"\btarget alignment\b", r"\bstatic calibration\b",
        r"\bdynamic calibration\b", r"\blane keep\b", r"\blane departure\b",
        r"\bblind spot\b",
    ],
    "precautions": [
        r"\bprecaution\b", r"\bwarning\b", r"\bcaution\b",
        r"\bdanger\b", r"\bsafety\b", r"\bdo not\b",
        r"\bwear protective\b", r"\bhazard\b",
        r"\bsrs\b", r"\bairbag\b", r"\bhigh voltage\b",
        r"\bbattery disconnect\b", r"\binjury\b",
    ],
}

# ── Role ontology phrases (3× keyword weight) ─────────────────────────────────

_ROLE_ONTOLOGY_PHRASES: dict[str, list[str]] = {
    "repair_procedure": [
        "removal and installation",
        "removal and replacement",
        "remove and install",
        "service and repair",
        "repair procedure",
        "removal procedure",
        "installation procedure",
        "replacement procedure",
        "service procedure",
    ],
    "sectioning": [
        "section cut",
        "section location",
        "sectioning location",
        "no cut zone",
        "cut location",
        "partial replacement",
        "replacement section",
        "splice location",
        "butt weld joint",
    ],
    "welding": [
        "weld points",
        "weld diagram",
        "spot weld",
        "plug weld",
        "mig welding",
        "mag welding",
        "resistance spot welding",
        "heat affected zone",
        "weld flange",
        "number of weld",
    ],
    "corrosion_protection": [
        "corrosion protection",
        "rust preventative",
        "body sealant",
        "anti-corrosion",
        "cavity wax",
        "underbody coating",
        "seam sealer",
        "rust treatment",
        "electrocoat primer",
    ],
    "materials": [
        "tensile strength",
        "material specification",
        "steel grade",
        "high strength steel",
        "ultra high strength steel",
        "yield strength",
        "advanced high strength",
        "dual phase steel",
        "boron steel",
    ],
    "dimensions": [
        "panel gap",
        "gap specification",
        "body dimensions",
        "gap and flush",
        "reference point",
        "measurement specification",
        "tolerance specification",
    ],
    "calibration": [
        "adas calibration",
        "radar calibration",
        "camera calibration",
        "sensor calibration",
        "static calibration",
        "dynamic calibration",
        "lane departure",
        "blind spot monitor",
        "adaptive cruise",
        "forward collision",
    ],
    "precautions": [
        "safety precautions",
        "airbag precaution",
        "srs system",
        "high voltage battery",
        "battery disconnect",
        "personal protection",
        "hazardous material",
        "injury risk",
    ],
}

# ── Breadcrumb navigation parsing ─────────────────────────────────────────────

_BREADCRUMB_SEPARATOR_RE = re.compile(r"\s*(?:>|»|→|/|::)\s*")

_BREADCRUMB_ROLE_MAP: dict[str, str] = {
    "removal and replacement": "repair_procedure",
    "removal and installation": "repair_procedure",
    "remove and install": "repair_procedure",
    "r&i": "repair_procedure",
    # "service and repair" intentionally omitted — it is a category folder
    # in ALLDATA navigation, not a specific document type. Specific document
    # types (weld points, removal and replacement, etc.) are more reliable signals.
    "repair procedure": "repair_procedure",
    "replacement procedure": "repair_procedure",
    "removal procedure": "repair_procedure",
    "weld points": "welding",
    "weld diagram": "welding",
    "welding procedure": "welding",
    "mig welding": "welding",
    "resistance spot welding": "welding",
    "sectioning": "sectioning",
    "section location": "sectioning",
    "sectioning procedure": "sectioning",
    "cut location": "sectioning",
    "corrosion protection": "corrosion_protection",
    "anti-corrosion": "corrosion_protection",
    "rust preventative": "corrosion_protection",
    "body sealant": "corrosion_protection",
    "seam sealer": "corrosion_protection",
    "material specification": "materials",
    "construction materials": "materials",
    "structural materials": "materials",
    "steel grade": "materials",
    "tensile strength": "materials",
    "panel gap": "dimensions",
    "body dimensions": "dimensions",
    "calibration": "calibration",
    "adas calibration": "calibration",
    "sensor calibration": "calibration",
    "precaution": "precautions",
    "safety precautions": "precautions",
}

# ── Filename parsing helpers ───────────────────────────────────────────────────

# Normalize filename separators: spaces, underscores, parens, brackets, dots.
# Hyphens are intentionally preserved — they appear in model names (F-150, CR-V, HR-V).
_FILENAME_SEPARATOR_RE = re.compile(r"[\s_\(\)\[\]\.]+")


def _pattern_to_name(pattern: str) -> str:
    """Fallback: convert a regex pattern to a readable name for display."""
    name = re.sub(r"\\b", "", pattern)
    name = re.sub(r"\\", "", name)
    name = name.replace("?", "").strip()
    if name.islower():
        return name.title()
    return name


def _score_oem(lower_text: str, text_len: int) -> dict[str, float]:
    """Score each OEM in the given lowercased text.

    Applies an isolation penalty when an OEM has only 1-2 raw hits in a long
    document (>1000 chars) — isolated mentions are likely noise or boilerplate.
    Returns {oem: score}. Score > 0 only for detected OEMs.
    """
    scores: dict[str, float] = {}
    for oem, patterns in _OEM_PATTERNS.items():
        raw_count = 0
        for pat in patterns:
            try:
                raw_count += len(re.findall(pat, lower_text))
            except re.error:
                raw_count += lower_text.count(pat)
        if raw_count == 0:
            continue
        # Isolation penalty: 1-2 hits in a long document = weak evidence
        if raw_count <= 2 and text_len > 1000:
            score = raw_count * 0.4
        else:
            score = float(raw_count)
        scores[oem] = score
    return scores


def _score_model(lower_text: str, candidate_oem: str | None) -> tuple[str | None, str | None]:
    """Score models in the given lowercased text.

    Searches within candidate_oem's models first, then all OEMs.
    Returns (canonical_model_name, matched_oem) or (None, None).
    """
    search_oems = (
        [candidate_oem] if candidate_oem and candidate_oem in _MODEL_PATTERNS
        else list(_MODEL_PATTERNS.keys())
    )
    model_hits: dict[tuple[str, str], int] = {}  # (oem, pattern) -> hits
    for oem in search_oems:
        for pat in _MODEL_PATTERNS.get(oem, []):
            try:
                hits = len(re.findall(pat, lower_text))
            except re.error:
                hits = 0
            if hits > 0:
                model_hits[(oem, pat)] = model_hits.get((oem, pat), 0) + hits
    if not model_hits:
        return None, None
    best_oem, best_pat = max(model_hits, key=lambda k: model_hits[k])
    canonical = _MODEL_CANONICAL.get(best_oem, {}).get(best_pat) or _pattern_to_name(best_pat)
    return canonical, best_oem


def _extract_filename_metadata(stem: str) -> dict[str, Any]:
    """Extract OEM, model, year, and operation hints from a filename stem.

    Normalizes separators (spaces, underscores, hyphens, brackets) and applies
    the same OEM/model/year/operation keyword patterns used for text detection.
    Filename tokens are treated as high-signal metadata — they typically name
    the vehicle directly and are not subject to the noisy-text isolation penalty.

    Returns a dict with keys: oem, model, year, operation (all may be None).
    """
    normalized = _FILENAME_SEPARATOR_RE.sub(" ", stem).strip()
    lower = normalized.lower()

    result: dict[str, Any] = {"oem": None, "model": None, "year": None, "operation": None}

    # Year detection from filename tokens
    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-3]\d)\b", normalized)]
    if years:
        year_counts: Counter = Counter(years)
        result["year"] = max(year_counts, key=lambda y: (year_counts[y], y))

    # OEM detection from filename — no isolation penalty (filenames are short)
    fn_oem_scores: dict[str, int] = {}
    for oem, patterns in _OEM_PATTERNS.items():
        score = 0
        for pat in patterns:
            try:
                score += len(re.findall(pat, lower))
            except re.error:
                pass
        if score > 0:
            fn_oem_scores[oem] = score
    if fn_oem_scores:
        result["oem"] = max(fn_oem_scores, key=lambda k: fn_oem_scores[k])

    # Model detection from filename
    model_name, _ = _score_model(lower, result["oem"])
    result["model"] = model_name

    # Operation detection from filename
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
        text = ""
        try:
            # Prefer pdftotext (poppler-utils) — extracts the real text layer
            # rather than raw byte scanning, which picks up binary noise.
            import subprocess  # noqa: PLC0415
            proc = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if proc.returncode == 0 and len(proc.stdout.strip()) >= 40:
                warnings.append(
                    "PDF text extracted via pdftotext. "
                    "Accuracy may be limited for scanned or image-based documents."
                )
                return proc.stdout, warnings, errors
        except FileNotFoundError:
            pass  # pdftotext not installed; fall through to heuristic scanner
        except Exception:  # noqa: BLE001
            pass
        try:
            raw = path.read_bytes()
            # Fallback: extract printable ASCII runs from the PDF binary stream.
            # Less accurate than pdftotext — misses text in complex encodings
            # and can pick up noise from binary object data.
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

def detect_breadcrumbs(text: str) -> list[str]:
    """Extract breadcrumb navigation segments from document text.

    Breadcrumbs are navigation paths such as:
    "Elantra > Body and Frame > Quarter Panel > Service and Repair > Removal and Replacement"

    Only lines with 3 or more separator-joined segments are treated as breadcrumbs.
    Returns a flat list of unique lowercased segments in first-occurrence order.
    """
    seen: dict[str, None] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = _BREADCRUMB_SEPARATOR_RE.split(stripped)
        if len(parts) >= 3:
            for p in parts:
                seg = p.strip().lower()
                if seg:
                    seen[seg] = None
    return list(seen.keys())


def detect_document_roles(text: str) -> dict[str, Any]:
    """Multi-role document classification using keyword, ontology, and breadcrumb signals.

    Scores each role using:
      1. Keyword patterns from _ROLE_KEYWORD_SETS (1× per hit)
      2. Ontology phrases from _ROLE_ONTOLOGY_PHRASES (3× each)
      3. Breadcrumb navigation segments matched via _BREADCRUMB_ROLE_MAP (5× each)

    Returns a dict with:
      primary_role (str): highest-scoring role, or "unknown"
      supporting_roles (list[str]): other roles scoring ≥30% of the top score
      role_scores (dict[str, float]): scores normalised to [0.0, 1.0]
      role_evidence (list[str]): top phrases that triggered the classification

    Does not guarantee accuracy. Outputs are heuristic estimates.
    """
    if not text or not text.strip():
        return {
            "primary_role": "unknown",
            "supporting_roles": [],
            "role_scores": {},
            "role_evidence": [],
        }

    lower = text.lower()
    raw_scores: dict[str, float] = {}
    evidence_by_role: dict[str, list[str]] = {r: [] for r in _ROLE_KEYWORD_SETS}

    # 1. Keyword pattern scoring (1× per hit)
    for role, patterns in _ROLE_KEYWORD_SETS.items():
        score = 0.0
        for pat in patterns:
            try:
                hits = len(re.findall(pat, lower))
            except re.error:
                hits = lower.count(pat)
            score += hits
        if score > 0:
            raw_scores[role] = score

    # 2. Ontology phrase scoring (3× per matched phrase)
    for role, phrases in _ROLE_ONTOLOGY_PHRASES.items():
        for phrase in phrases:
            if phrase in lower:
                raw_scores[role] = raw_scores.get(role, 0.0) + 3.0
                evidence_by_role[role].append(phrase)

    # 3. Breadcrumb evidence (5× per matched segment)
    breadcrumbs = detect_breadcrumbs(text)
    for seg in breadcrumbs:
        for key, role in _BREADCRUMB_ROLE_MAP.items():
            if key in seg:
                raw_scores[role] = raw_scores.get(role, 0.0) + 5.0
                ev_label = f"[bc] {seg}"
                if ev_label not in evidence_by_role[role]:
                    evidence_by_role[role].append(ev_label)
                break

    if not raw_scores:
        return {
            "primary_role": "unknown",
            "supporting_roles": [],
            "role_scores": {},
            "role_evidence": [],
        }

    max_score = max(raw_scores.values())
    normalized: dict[str, float] = {
        role: round(score / max_score, 3)
        for role, score in raw_scores.items()
    }

    primary_role = max(raw_scores, key=lambda r: raw_scores[r])
    threshold = max_score * 0.30
    supporting_roles = [
        r for r, s in sorted(raw_scores.items(), key=lambda x: -x[1])
        if r != primary_role and s >= threshold
    ]

    # Breadcrumb-dominant rule: a breadcrumb segment is ALLDATA's explicit
    # document-type label — "Removal and Replacement", "Weld Points", etc.
    # When a breadcrumb maps to a role, that role wins over keyword accumulation
    # (e.g. a repair-procedure document that mentions welding heavily should not
    # be reclassified as welding just because weld keywords dominate the body).
    bc_evidenced_roles = {
        role for role in raw_scores
        if any(ev.startswith("[bc]") for ev in evidence_by_role.get(role, []))
    }
    if bc_evidenced_roles:
        bc_primary = max(bc_evidenced_roles, key=lambda r: raw_scores.get(r, 0))
        if bc_primary != primary_role:
            primary_role = bc_primary
            supporting_roles = [
                r for r, s in sorted(raw_scores.items(), key=lambda x: -x[1])
                if r != primary_role and s >= threshold
            ]

    all_detected = [primary_role] + supporting_roles
    evidence: list[str] = []
    # Breadcrumb evidence first (highest-signal, 5× weight) so it always appears
    for role in all_detected:
        for item in evidence_by_role.get(role, []):
            if item.startswith("[bc]") and item not in evidence:
                evidence.append(item)
    # Ontology phrase evidence next (3× weight), up to 3 per role
    for role in all_detected:
        phrase_count = 0
        for item in evidence_by_role.get(role, []):
            if not item.startswith("[bc]") and item not in evidence and phrase_count < 3:
                evidence.append(item)
                phrase_count += 1
    evidence = evidence[:8]

    return {
        "primary_role": primary_role,
        "supporting_roles": supporting_roles,
        "role_scores": normalized,
        "role_evidence": evidence,
    }


def detect_document_role(text: str) -> str:
    """Detect primary document role from text content using keyword heuristics.

    Returns one of the DOCUMENT_ROLES strings. Returns "unknown" when no
    signal is found. Delegates to detect_document_roles() internally.
    Does not guarantee accuracy — outputs require human review.
    """
    return detect_document_roles(text)["primary_role"]


def detect_oem_metadata(text: str) -> dict[str, Any]:
    """Detect OEM, model, year, and operation from text heuristics.

    Returns a dict with keys: oem, model, year, operation, confidence.
    All values may be None if undetected. confidence is a float in [0.0, 1.0].

    Applies an isolation penalty for OEM mentions that appear only 1-2 times
    in documents longer than 1000 characters — these are likely noise or
    boilerplate, not strong identity evidence. Short texts and repeated mentions
    are not penalized.

    Does not consider filenames — call _extract_filename_metadata() separately
    and merge results in classify_intake_file() for the full signal picture.
    Does not guarantee accuracy.
    """
    if not text or not text.strip():
        return {"oem": None, "model": None, "year": None, "operation": None, "confidence": 0.0}

    lower = text.lower()
    text_len = len(lower)
    result: dict[str, Any] = {
        "oem": None, "model": None, "year": None, "operation": None, "confidence": 0.0,
    }

    # OEM scoring with isolation penalty
    oem_scores = _score_oem(lower, text_len)
    oem_raw: dict[str, int] = {}
    for oem, patterns in _OEM_PATTERNS.items():
        cnt = 0
        for pat in patterns:
            try:
                cnt += len(re.findall(pat, lower))
            except re.error:
                cnt += lower.count(pat)
        if cnt > 0:
            oem_raw[oem] = cnt

    if oem_scores:
        result["oem"] = max(oem_scores, key=lambda k: oem_scores[k])
        raw = oem_raw.get(result["oem"], 0)
        base_conf = min(0.85, 0.30 + raw * 0.12)
        # Penalize confidence when detection is based on isolated weak signal
        if raw <= 2 and text_len > 1000:
            base_conf = base_conf * 0.5
        result["confidence"] = base_conf

    # Model scoring — search within detected OEM first, then all
    model_name, _ = _score_model(lower, result["oem"])
    result["model"] = model_name

    # Year detection — plausible range 1980-2039
    years_found = re.findall(r"\b(19[89]\d|20[0-3]\d)\b", text)
    if years_found:
        year_counts: Counter = Counter(int(y) for y in years_found)
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
    lightweight heuristics. Merges filename-based evidence (high-signal) with
    text-based evidence. When filename and text OEM disagree, filename takes
    priority and a warning is recorded.

    Returns an IntakeFile with confidence scores, warnings, and errors.
    Never crashes on unreadable files.
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

    # Extract filename metadata (high-signal, no isolation penalty)
    filename_meta = _extract_filename_metadata(path.stem)

    text, read_warnings, read_errors = _read_file_text(path)
    warnings.extend(read_warnings)
    errors.extend(read_errors)

    if read_errors:
        return IntakeFile(
            file_id=file_id,
            filename=path.name,
            extension=ext,
            size_bytes=size_bytes,
            detected_oem=filename_meta["oem"],
            detected_model=filename_meta["model"],
            detected_year=filename_meta["year"],
            detected_operation=filename_meta["operation"],
            document_role="unknown",
            confidence=0.0,
            warnings=warnings,
            errors=errors,
        )

    role_result = detect_document_roles(text) if text.strip() else {
        "primary_role": "unknown",
        "supporting_roles": [],
        "role_scores": {},
        "role_evidence": [],
    }
    role = role_result["primary_role"]
    text_meta = detect_oem_metadata(text) if text.strip() else {
        "oem": None, "model": None, "year": None, "operation": None, "confidence": 0.0,
    }

    fn_oem = filename_meta["oem"]
    txt_oem = text_meta["oem"]
    txt_conf = text_meta["confidence"]

    # ── OEM resolution: filename takes priority over isolated text evidence ──
    if fn_oem and txt_oem and fn_oem != txt_oem:
        # Filename and text disagree — filename wins, record conflict
        warnings.append(
            f"METADATA_CONFLICT: Filename OEM={fn_oem!r}; "
            f"text OEM={txt_oem!r}. Filename evidence applied."
        )
        detected_oem = fn_oem
        # Medium confidence: conflict reduces certainty even when filename wins
        oem_confidence = min(0.65, max(txt_conf * 0.5 + 0.20, 0.35))
    elif fn_oem and txt_oem and fn_oem == txt_oem:
        # Both agree — strong evidence
        detected_oem = fn_oem
        oem_confidence = min(0.85, txt_conf + 0.15)
    elif fn_oem:
        # Filename has OEM, text does not (or text gave up with 0.0)
        detected_oem = fn_oem
        oem_confidence = max(0.50, txt_conf)
    elif txt_oem:
        # Text-only detection
        detected_oem = txt_oem
        oem_confidence = txt_conf
    else:
        detected_oem = None
        oem_confidence = 0.0

    # ── Year resolution: filename year is high-signal ──
    fn_year = filename_meta["year"]
    txt_year = text_meta["year"]
    if fn_year:
        detected_year = fn_year
    elif txt_year:
        detected_year = txt_year
    else:
        detected_year = None

    # ── Model resolution: filename takes priority ──
    detected_model = filename_meta["model"] or text_meta["model"]

    # ── Operation resolution: filename takes priority ──
    detected_operation = filename_meta["operation"] or text_meta["operation"]

    # ── Model-to-OEM inference ─────────────────────────────────────────────────
    # When no explicit OEM was found in filename or text, but a known model is
    # present, infer the OEM from the model.  Applied here (not in
    # _extract_filename_metadata) so that the public API of that function is
    # unchanged and existing metadata-voting tests continue to pass.
    if not detected_oem and detected_model and detected_model in _MODEL_TO_OEM:
        detected_oem = _MODEL_TO_OEM[detected_model]
        oem_confidence = 0.35
    elif (
        detected_oem
        and not fn_oem  # only text gave us an OEM
        and detected_model
        and detected_model in _MODEL_TO_OEM
    ):
        model_implied = _MODEL_TO_OEM[detected_model]
        if model_implied != detected_oem:
            # Model identity (from filename) is stronger than an isolated OEM
            # mention scraped from noisy PDF text.
            warnings.append(
                f"MODEL_OEM_OVERRIDE: text-detected OEM={detected_oem!r} overridden "
                f"by model {detected_model!r} → {model_implied!r}."
            )
            detected_oem = model_implied
            oem_confidence = 0.35
        else:
            # Model name confirms text OEM — boost confidence; a single OEM hit
            # in a long document normally receives the isolation penalty, but
            # the model name corroborates the identity from a second channel.
            oem_confidence = max(oem_confidence, 0.35)

    # ── Operation-to-role fallback ─────────────────────────────────────────────
    # When text extraction was too sparse for content-based role detection but
    # the filename names a known operation (e.g. 'quarter_panel_replacement'),
    # infer the document role from the operation.  Only fires when role is still
    # "unknown" — it never overrides a content-detected role.
    if role == "unknown" and detected_operation and detected_operation in _OPERATION_TO_ROLE:
        role = _OPERATION_TO_ROLE[detected_operation]
        role_result = {
            "primary_role": role,
            "supporting_roles": [],
            "role_scores": {},
            "role_evidence": [],
        }
        warnings.append(
            f"ROLE_FROM_OPERATION: role '{role}' inferred from filename operation "
            f"'{detected_operation}' — text extraction was insufficient for "
            "content-based role detection."
        )

    # ── Final confidence adjustments ──
    confidence = oem_confidence
    # Confidence floor: if text is readable and a role was detected, don't
    # collapse to 0.0 just because no OEM was found.
    if role != "unknown" and text.strip() and confidence == 0.0:
        confidence = 0.25
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
        detected_oem=detected_oem,
        detected_model=detected_model,
        detected_year=detected_year,
        detected_operation=detected_operation,
        document_role=role,
        supporting_roles=role_result["supporting_roles"],
        role_scores=role_result["role_scores"],
        role_evidence=role_result["role_evidence"],
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

    Classifies each file, aggregates metadata using filename-weighted voting,
    identifies detected and missing document roles, and assembles a complete
    IntakeManifest. Handles empty lists and unreadable files gracefully.

    Packet-level OEM is determined by:
    1. Filename consensus (>=50% of readable files agree via filename): strong
    2. Weighted text consensus (when no filename majority): fallback
    Diagnostics explain the evidence source and any conflicts detected.
    """
    intake_id = "intake_" + str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()

    paths = [Path(p) for p in paths]
    files: list[IntakeFile] = []
    diagnostics: list[IntakeDiagnostic] = []
    path_file_pairs: list[tuple[Path, IntakeFile]] = []

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
        path_file_pairs.append((path, f))
        for w in f.warnings:
            diagnostics.append(IntakeDiagnostic(
                code="FILE_WARNING", severity="warning", message=w, file_id=f.file_id,
            ))
        for e in f.errors:
            diagnostics.append(IntakeDiagnostic(
                code="FILE_ERROR", severity="error", message=e, file_id=f.file_id,
            ))

    readable_pairs = [(p, f) for p, f in path_file_pairs if not f.errors]
    readable = [f for _, f in readable_pairs]
    n_readable = len(readable)

    # Collect roles from primary document_role and supporting_roles across all readable files.
    # Supporting roles score ≥30% of the top role score and count as packet-level coverage.
    _role_set: set[str] = set()
    for _f in readable:
        if _f.document_role != "unknown":
            _role_set.add(_f.document_role)
        for _r in _f.supporting_roles:
            if _r != "unknown":
                _role_set.add(_r)
    detected_roles = sorted(_role_set)
    weights = [f.confidence for f in readable]
    avg_conf = sum(weights) / len(weights) if weights else 0.0

    # ── Packet-level metadata voting ──────────────────────────────────────────

    # Extract filename metadata for all readable files to use as strong evidence
    fn_oems: list[str | None] = []
    fn_years: list[int | None] = []
    fn_models: list[str | None] = []
    for path, _ in readable_pairs:
        fm = _extract_filename_metadata(path.stem)
        fn_oem_val = fm["oem"]
        # Apply the same model-to-OEM inference used in classify_intake_file so
        # that packet-level OEM voting correctly counts model-only filenames
        # (e.g. "2023 Elantra …" → Hyundai).
        if fn_oem_val is None and fm["model"] and fm["model"] in _MODEL_TO_OEM:
            fn_oem_val = _MODEL_TO_OEM[fm["model"]]
        fn_oems.append(fn_oem_val)
        fn_years.append(fm["year"])
        fn_models.append(fm["model"])

    # OEM voting: filename evidence weighted more heavily than isolated text
    fn_oem_counter: Counter = Counter(o for o in fn_oems if o)
    txt_oem_counter: Counter = Counter()
    for f, w in zip(readable, weights):
        if f.detected_oem:
            txt_oem_counter[f.detected_oem] += w

    detected_oem: str | None = None
    oem_confidence: float = avg_conf

    if fn_oem_counter:
        top_fn_oem, top_fn_count = fn_oem_counter.most_common(1)[0]
        fn_agreement = top_fn_count / max(n_readable, 1)

        if fn_agreement >= 0.5:
            # Majority of files agree on this OEM via filename — strong evidence
            detected_oem = top_fn_oem
            oem_confidence = min(0.85, 0.55 + fn_agreement * 0.30)
            diagnostics.append(IntakeDiagnostic(
                code="OEM_DETECTED_BY_FILENAME",
                severity="info",
                message=(
                    f"OEM {top_fn_oem!r} determined from filename evidence "
                    f"({top_fn_count}/{n_readable} file(s) agree)."
                ),
            ))
        else:
            # Mixed filename evidence — use combined weighted vote
            combined: dict[str, float] = {}
            for oem, cnt in fn_oem_counter.items():
                combined[oem] = combined.get(oem, 0.0) + cnt * 2.0
            for oem, score in txt_oem_counter.items():
                combined[oem] = combined.get(oem, 0.0) + score
            detected_oem = max(combined, key=lambda k: combined[k]) if combined else None
    else:
        # No filename OEM evidence — use text-only weighted consensus
        detected_oem = _weighted_consensus([f.detected_oem for f in readable], weights)

    # Year voting: filename years are high-signal
    fn_year_counter: Counter = Counter(y for y in fn_years if y)
    if fn_year_counter:
        detected_year: int | None = fn_year_counter.most_common(1)[0][0]
    else:
        detected_year = _weighted_consensus([f.detected_year for f in readable], [1.0] * n_readable)

    # Model voting: filename models take priority
    fn_model_counter: Counter = Counter(m for m in fn_models if m)
    if fn_model_counter:
        detected_model: str | None = fn_model_counter.most_common(1)[0][0]
    else:
        detected_model = _weighted_consensus([f.detected_model for f in readable], weights)

    # Operation voting: existing logic
    detected_operation = _weighted_consensus([f.detected_operation for f in readable], weights)

    detected_packet = IntakePacket(
        detected_oem=detected_oem,
        detected_model=detected_model,
        detected_year=detected_year,
        detected_operation=detected_operation,
        oem_confidence=round(oem_confidence, 3),
        detected_roles=detected_roles,
        file_count=len(files),
    )

    _ESSENTIAL = {"repair_procedure"}
    _USEFUL = {"welding", "corrosion_protection", "materials"}
    found_set = set(detected_roles)
    missing_roles = sorted((_ESSENTIAL | _USEFUL) - found_set)

    # ── Readiness ─────────────────────────────────────────────────────────────
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

    # ── Cross-file diagnostics ────────────────────────────────────────────────

    # OEM conflict across files (text-level)
    oem_vals = [f.detected_oem for f in readable if f.detected_oem]
    if len(set(oem_vals)) > 1:
        diagnostics.append(IntakeDiagnostic(
            code="OEM_CONFLICT",
            severity="warning",
            message=(
                f"Multiple OEM signals detected across files: {sorted(set(oem_vals))}. "
                "Files may originate from different OEM repair manuals."
            ),
        ))

    # Filename/text OEM disagreements at packet level
    for (path, f), fn_oem in zip(readable_pairs, fn_oems):
        conflict_warnings = [w for w in f.warnings if w.startswith("METADATA_CONFLICT:")]
        if conflict_warnings:
            diagnostics.append(IntakeDiagnostic(
                code="FILENAME_TEXT_DISAGREEMENT",
                severity="warning",
                message=(
                    f"{f.filename}: Filename OEM evidence conflicts with extracted "
                    f"text OEM signal. Filename evidence prioritised."
                ),
                file_id=f.file_id,
                detail=conflict_warnings[0],
            ))

    # Year conflicts between filename and text
    txt_years_all = [f.detected_year for f in readable if f.detected_year]
    if detected_year and txt_years_all:
        txt_year_majority = Counter(txt_years_all).most_common(1)[0][0]
        if txt_year_majority != detected_year and fn_year_counter:
            diagnostics.append(IntakeDiagnostic(
                code="YEAR_CONFLICT",
                severity="info",
                message=(
                    f"Filename year ({detected_year}) differs from predominant "
                    f"document text year ({txt_year_majority}). Filename year preferred."
                ),
            ))

    # Model conflicts
    txt_models = [f.detected_model for f in readable if f.detected_model]
    if txt_models and detected_model:
        unique_txt_models = set(txt_models)
        if len(unique_txt_models) > 1:
            diagnostics.append(IntakeDiagnostic(
                code="MODEL_CONFLICT",
                severity="info",
                message=(
                    f"Multiple model signals detected across files: "
                    f"{sorted(unique_txt_models)}. Review source documents."
                ),
            ))

    # Weak metadata confidence
    if detected_oem and oem_confidence < 0.40:
        diagnostics.append(IntakeDiagnostic(
            code="WEAK_METADATA_CONFIDENCE",
            severity="warning",
            message=(
                f"OEM {detected_oem!r} detected with low confidence ({oem_confidence:.0%}). "
                "Metadata may be unreliable. Verify source documents before normalization."
            ),
        ))

    # No strong packet consensus
    if not detected_oem:
        if n_readable > 0 and txt_oem_counter and len(txt_oem_counter) > 1:
            diagnostics.append(IntakeDiagnostic(
                code="NO_STRONG_PACKET_CONSENSUS",
                severity="warning",
                message=(
                    f"No single OEM achieved consensus. Detected signals: "
                    f"{sorted(txt_oem_counter.keys())}. "
                    "Supply filenames that clearly identify the OEM/model/year."
                ),
            ))
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
