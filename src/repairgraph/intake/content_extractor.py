"""
Deterministic content extraction from OEM document text.

Rule-based (no OCR, no ML, no LLMs) extraction of structured procedure facts
from the text the intake classifier already reads. Every extracted fact
carries the exact source snippet it was derived from as evidence, so every
downstream conclusion remains traceable to customer-supplied text.

Design principles
-----------------
- Extract only what pattern-matches in the actual document text. If the text
  does not state it, the fact does not exist. Never fabricate.
- Every fact carries an evidence object with the matched snippet.
- Component names are normalized to snake_case IDs and passed through the
  taxonomy alias table so intake-derived and fixture procedures share a
  vocabulary.
- Output is a plain JSON-serializable dict (stored on IntakeFile and merged
  by the normalizer).

All outputs are advisory and require verification against OEM procedures.
"""
from __future__ import annotations

import re
from typing import Any

from repairgraph.extract.dependencies import normalize_target
from repairgraph.taxonomy.aliases import resolve_alias

# ---------------------------------------------------------------------------
# Component recognition
# ---------------------------------------------------------------------------

# Structural nouns that terminate a component phrase. A component is 0-3
# qualifier words followed by one of these (e.g. "rear pillar gutter",
# "quarter pillar stiffener", "side sill extension end flange").
_STRUCTURAL_NOUNS = (
    "outer panel", "inner panel", "panel", "separator", "stiffener",
    "rail", "gutter", "extension", "adapter", "flange", "pillar", "sill",
    "crossmember", "cross member", "reinforcement", "bracket", "member",
    "wheelhouse", "apron", "dogleg", "rocker",
)

# Words that must not begin (or be) a component phrase.
_PHRASE_STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "each", "any", "all",
    "of", "to", "and", "or", "with", "on", "in", "at", "for", "from", "new",
    "old", "damaged", "replacement", "repair", "service", "affected",
    "adjacent", "existing", "entire", "remaining", "original",
}

_COMPONENT_RE = re.compile(
    r"\b((?:[a-z][a-z\-]*\s+){0,3}(?:%s))\b" % "|".join(
        n.replace(" ", r"\s+") for n in sorted(_STRUCTURAL_NOUNS, key=len, reverse=True)
    ),
    re.IGNORECASE,
)

# Words that disqualify a phrase from being a component identity when they
# appear anywhere in it: verbs, prepositions, units, brand names, and
# procedure vocabulary that the qualifier window can accidentally absorb.
_PHRASE_JUNKWORDS = {
    "mm", "mpa", "weld", "welds", "welding", "brazing", "bonding",
    "inspect", "check", "examine", "apply", "applied", "remove", "removed",
    "install", "installed", "installing", "make", "made", "use", "using",
    "per", "replace", "replaces", "replacing", "removing",
    "from", "at", "in", "on", "along", "inside", "outside", "above", "below",
    "before", "after", "during", "between", "near", "toward", "against",
    "position", "procedure", "replacement", "section", "sectioning",
    "honda", "toyota", "hyundai", "nissan", "ford", "kia", "chevrolet",
    "subaru", "mazda", "volkswagen", "bmw", "gmc", "ram", "jeep", "lexus",
}

# PDF text extraction hard-wraps lines mid-sentence. Join single line breaks
# into spaces; only blank lines (paragraph breaks) and sentence punctuation
# terminate a sentence.
_LINE_WRAP_RE = re.compile(r"[ \t]*\n[ \t]*(?!\n)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n{2,}\s*")

_MAX_SNIPPET = 160


def _evidence(snippet: str) -> dict[str, Any]:
    return {
        "source_type": "document_text",
        "basis": [snippet.strip()[:_MAX_SNIPPET]],
        "confidence": "medium",
        "requires_oem_verification": True,
        "interpretation": "advisory",
    }


def _sentences(text: str) -> list[str]:
    unwrapped = _LINE_WRAP_RE.sub(" ", text)
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(unwrapped) if s.strip()]


def _clean_component_phrase(phrase: str) -> str | None:
    """Strip leading stopwords from a matched phrase; None if nothing remains."""
    words = phrase.lower().split()
    while words and words[0] in _PHRASE_STOPWORDS:
        words = words[1:]
    if not words:
        return None
    if any(w in _PHRASE_JUNKWORDS for w in words):
        return None
    cleaned = " ".join(words)
    # A bare structural noun with no qualifier ("panel", "rail") is too
    # ambiguous to be a component identity.
    if cleaned in _STRUCTURAL_NOUNS:
        return None
    return cleaned


def _components_in(sentence: str) -> list[str]:
    """Return normalized component IDs mentioned in a sentence, in order.

    When a candidate phrase is rejected (junk/stopword content), scanning
    resumes one word into the rejected span rather than after it — a greedy
    match that absorbed a verb ("inspect the rear pillar") must not consume
    the real component that follows ("rear pillar gutter").
    """
    found: list[str] = []
    pos = 0
    while pos < len(sentence):
        m = _COMPONENT_RE.search(sentence, pos)
        if not m:
            break
        cleaned = _clean_component_phrase(m.group(1))
        if cleaned:
            node = resolve_alias(normalize_target(cleaned))
            if node and node not in found:
                found.append(node)
            pos = m.end()
        else:
            first_word = m.group(1).split()[0]
            pos = m.start() + len(first_word) + 1
    return found


# ---------------------------------------------------------------------------
# Dependency extraction
# ---------------------------------------------------------------------------

_REPLACE_RE = re.compile(r"\breplace\b", re.IGNORECASE)
_INSPECT_RE = re.compile(r"\b(?:inspect|check|examine)\b.*?\bfor\s+(?:damage|deformation|distortion|cracks?)", re.IGNORECASE)


def _extract_dependencies(sentences: list[str]) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for sentence in sentences:
        if _REPLACE_RE.search(sentence):
            dep_type = "replace_component"
        elif _INSPECT_RE.search(sentence):
            dep_type = "inspect_if_damaged"
        else:
            continue

        for component in _components_in(sentence):
            key = (dep_type, component)
            if key in seen:
                continue
            seen.add(key)
            deps.append({
                "type": dep_type,
                "target": component,
                "evidence": _evidence(sentence),
            })

    return deps


# ---------------------------------------------------------------------------
# Spatial relationship extraction
# ---------------------------------------------------------------------------

# Phrase → canonical relationship (must be in topology ALLOWED_SPATIAL_RELATIONSHIPS)
_RELATIONSHIP_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:is\s+)?adjacent\s+to\b", re.IGNORECASE), "adjacent_to"),
    (re.compile(r"\boverlaps?\b", re.IGNORECASE), "adjacent_to"),
    (re.compile(r"\b(?:is\s+)?(?:welded|joined|attached|bonded|brazed)\s+to\b", re.IGNORECASE), "joined_to"),
    (re.compile(r"\bjoins\b", re.IGNORECASE), "joins_to"),
]


def _extract_spatial_relationships(sentences: list[str]) -> list[dict[str, Any]]:
    rels: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for sentence in sentences:
        for pattern, relationship in _RELATIONSHIP_PATTERNS:
            m = pattern.search(sentence)
            if not m:
                continue
            left = _components_in(sentence[: m.start()])
            right = _components_in(sentence[m.end():])
            if not left or not right:
                continue
            source, target = left[-1], right[0]
            if source == target:
                continue
            key = (source, relationship, target)
            if key in seen:
                continue
            seen.add(key)
            rels.append({
                "source": source,
                "relationship": relationship,
                "target": target,
                "evidence": _evidence(sentence),
            })
            break  # one relationship per sentence — first pattern wins

    return rels


# ---------------------------------------------------------------------------
# Sectioning extraction
# ---------------------------------------------------------------------------

_SECTIONING_RE = re.compile(
    r"\b(?:section(?:ing)?|cut(?:ting)?\s+(?:line|position|location)|make\s+the\s+cut)\b",
    re.IGNORECASE,
)
_DIMENSION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm\b", re.IGNORECASE)


def _extract_sectioning_locations(sentences: list[str]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    seen: set[str] = set()

    for sentence in sentences:
        if not _SECTIONING_RE.search(sentence):
            continue
        components = _components_in(sentence)
        if not components:
            continue
        zone = components[0]
        if zone in seen:
            continue
        seen.add(zone)
        entry: dict[str, Any] = {
            "zone": zone,
            "description": sentence.strip()[:_MAX_SNIPPET],
            "evidence": _evidence(sentence),
        }
        dim = _DIMENSION_RE.search(sentence)
        if dim:
            entry["dimension_mm"] = float(dim.group(1))
        locations.append(entry)

    return locations


# ---------------------------------------------------------------------------
# Joining method extraction (with counts where stated)
# ---------------------------------------------------------------------------

_JOINING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bresistance\s+spot\s+weld", re.IGNORECASE), "resistance_spot_weld"),
    (re.compile(r"\bspot\s+weld", re.IGNORECASE), "spot_weld"),
    (re.compile(r"\bplug\s+weld", re.IGNORECASE), "plug_weld"),
    (re.compile(r"\bmig\s+braz", re.IGNORECASE), "mig_brazing"),
    (re.compile(r"\bmig\s+weld", re.IGNORECASE), "mig_welding"),
    (re.compile(r"\bmag\s+weld", re.IGNORECASE), "mag_welding"),
    (re.compile(r"\badhesive\s+bond", re.IGNORECASE), "adhesive_bonding"),
    (re.compile(r"\bhemming\b", re.IGNORECASE), "hemming"),
    (re.compile(r"\brivet", re.IGNORECASE), "structural_rivet"),
    (re.compile(r"\bbraz", re.IGNORECASE), "brazing"),
]

_COUNT_BEFORE_RE = re.compile(r"(\d+)\s*(?:x\s*)?$")


def _extract_joining_methods(sentences: list[str]) -> list[dict[str, Any]]:
    methods: dict[str, dict[str, Any]] = {}

    for sentence in sentences:
        matched: set[str] = set()
        for pattern, method_id in _JOINING_PATTERNS:
            m = pattern.search(sentence)
            if not m or method_id in matched:
                continue
            # Skip broader patterns when a more specific one already matched
            # (mig_brazing also matches the generic 'braz' pattern).
            if method_id == "brazing" and "mig_brazing" in matched:
                continue
            if method_id == "spot_weld" and "resistance_spot_weld" in matched:
                continue
            matched.add(method_id)

            entry = methods.setdefault(method_id, {
                "method": method_id,
                "evidence": _evidence(sentence),
            })
            count_match = _COUNT_BEFORE_RE.search(sentence[: m.start()].strip())
            if count_match:
                entry["count"] = max(entry.get("count", 0), int(count_match.group(1)))

    return list(methods.values())


# ---------------------------------------------------------------------------
# Corrosion requirement extraction
# ---------------------------------------------------------------------------

_CORROSION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:seam\s+sealer|body\s+sealant|sealer)\b", re.IGNORECASE), "sealer_application_required"),
    (re.compile(r"\b(?:cavity\s+wax|under\s*body|undercoat|electrocoat)\b", re.IGNORECASE), "undercoating_application_required"),
    (re.compile(r"\badhesive\s+application\b", re.IGNORECASE), "adhesive_application_required"),
    (re.compile(r"\b(?:anti-?corrosion|rust\s+preventat?ive|corrosion\s+protection|weld-?through\s+primer)\b", re.IGNORECASE), "corrosion_protection_required"),
]


def _extract_corrosion_requirements(sentences: list[str]) -> list[dict[str, Any]]:
    reqs: dict[str, dict[str, Any]] = {}
    for sentence in sentences:
        for pattern, req_id in _CORROSION_PATTERNS:
            if pattern.search(sentence) and req_id not in reqs:
                reqs[req_id] = {"requirement": req_id, "evidence": _evidence(sentence)}
    return list(reqs.values())


# ---------------------------------------------------------------------------
# Material extraction
# ---------------------------------------------------------------------------

_MPA_RE = re.compile(r"(\d{3,4})\s*MPa\b", re.IGNORECASE)
_THICKNESS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm\s+(?:thick|sheet|thickness)|thickness[^0-9]{0,20}(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)
_ZINC_RE = re.compile(r"\bzinc[\s-]*(?:coated|plated|treated)?\b", re.IGNORECASE)


def _classify_tensile(mpa: int) -> str:
    if mpa >= 980:
        return "UHSS"
    if mpa >= 340:
        return "HSS"
    return "mild_steel"


def _extract_materials(sentences: list[str]) -> list[dict[str, Any]]:
    materials: dict[str, dict[str, Any]] = {}

    for sentence in sentences:
        components = _components_in(sentence)
        if not components:
            continue
        component = components[0]

        mpa_match = _MPA_RE.search(sentence)
        thickness_match = _THICKNESS_RE.search(sentence)
        zinc = bool(_ZINC_RE.search(sentence))

        if not (mpa_match or thickness_match or zinc):
            continue

        entry = materials.setdefault(component, {
            "component": component,
            "evidence": _evidence(sentence),
        })
        if mpa_match:
            mpa = int(mpa_match.group(1))
            entry["tensile_strength_mpa"] = max(entry.get("tensile_strength_mpa", 0), mpa)
            entry["classification"] = _classify_tensile(entry["tensile_strength_mpa"])
        if thickness_match:
            raw = thickness_match.group(1) or thickness_match.group(2)
            entry["thickness_mm"] = float(raw)
        if zinc:
            entry["zinc_plated"] = True

    return list(materials.values())


# ---------------------------------------------------------------------------
# Repair note extraction
# ---------------------------------------------------------------------------

_NOTE_RE = re.compile(
    r"\b(?:caution|warning|note:|important|must\s+(?:not\s+)?be|do\s+not|never|"
    r"always|required\s+before|prior\s+to\s+installation)\b",
    re.IGNORECASE,
)


def _extract_repair_notes(sentences: list[str]) -> list[str]:
    notes: list[str] = []
    for sentence in sentences:
        if _NOTE_RE.search(sentence):
            note = sentence.strip()[:_MAX_SNIPPET * 2]
            if note not in notes:
                notes.append(note)
    return notes[:20]  # keep the document's top notes; avoid unbounded output


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_document_facts(text: str) -> dict[str, Any]:
    """Extract structured procedure facts from raw document text.

    Returns a JSON-serializable dict. Empty lists mean the document text did
    not state those facts — nothing is inferred or fabricated. Every non-note
    fact includes an evidence object with the matched source snippet.
    """
    if not text or not text.strip():
        return {
            "components": [], "dependencies": [], "spatial_relationships": [],
            "sectioning_locations": [], "joining_methods": [],
            "corrosion_requirements": [], "materials": [], "repair_notes": [],
        }

    sentences = _sentences(text)

    all_components: list[str] = []
    for sentence in sentences:
        for c in _components_in(sentence):
            if c not in all_components:
                all_components.append(c)

    return {
        "components": all_components,
        "dependencies": _extract_dependencies(sentences),
        "spatial_relationships": _extract_spatial_relationships(sentences),
        "sectioning_locations": _extract_sectioning_locations(sentences),
        "joining_methods": _extract_joining_methods(sentences),
        "corrosion_requirements": _extract_corrosion_requirements(sentences),
        "materials": _extract_materials(sentences),
        "repair_notes": _extract_repair_notes(sentences),
    }
