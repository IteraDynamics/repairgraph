"""
Intake Evidence Inspector for RepairGraph OEM repair packet intake.

Builds structured evidence/debug payloads from IntakeManifest data so that
users and developers can understand why each file was classified, why
confidence is low, why roles are found or missing, and what evidence drove
each decision.

All outputs are derived from IntakeManifest/IntakeFile fields only — no files
are re-read. Outputs are deterministic and JSON-serializable.

Advisory: Classification explanations are heuristic estimates. They do not
certify OEM authenticity, document completeness, or normalization readiness.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from repairgraph.intake.schema import IntakeFile, IntakeManifest

# Diagnostic codes emitted by this module
DIAG_SPARSE_TEXT_EXTRACTION = "SPARSE_TEXT_EXTRACTION"
DIAG_ROLE_SCORE_BELOW_THRESHOLD = "ROLE_SCORE_BELOW_THRESHOLD"
DIAG_SUPPORTING_ROLE_ONLY = "SUPPORTING_ROLE_ONLY"
DIAG_ROLE_COVERAGE_FROM_SUPPORTING = "ROLE_COVERAGE_FROM_SUPPORTING_ROLE"
DIAG_BREADCRUMB_EVIDENCE_FOUND = "BREADCRUMB_EVIDENCE_FOUND"
DIAG_FILENAME_ONLY_METADATA = "FILENAME_ONLY_METADATA"
DIAG_ROLE_FROM_OPERATION = "ROLE_FROM_OPERATION"

_ALL_TRACKED_ROLES = [
    "repair_procedure",
    "sectioning",
    "welding",
    "corrosion_protection",
    "materials",
    "dimensions",
    "calibration",
    "precautions",
]

# Separator normaliser from classify.py — duplicated here to avoid importing a private symbol
_FILENAME_SEP_RE = re.compile(r"[\s_\(\)\[\]\.]+")


def _filename_tokens(filename: str) -> list[str]:
    """Return normalised tokens from a filename stem."""
    stem = Path(filename).stem
    # Collapse multi-hyphen separators (e.g. ALLDATA's '--') into spaces before
    # other normalization.  Single hyphens are preserved for model names (F-150).
    stem = re.sub(r"-{2,}", " ", stem)
    normalized = _FILENAME_SEP_RE.sub(" ", stem).strip()
    return [t for t in normalized.split() if t]


def _text_quality(file: IntakeFile) -> str:
    """Derive text quality indicator from IntakeFile warning/score fields.

    Returns one of: "none", "sparse", "usable".
    """
    if file.errors:
        return "none"
    warning_joined = " ".join(file.warnings).lower()
    if "file is empty" in warning_joined:
        return "none"
    if "minimal content" in warning_joined or "yielded minimal" in warning_joined:
        return "sparse"
    if not file.role_scores and not file.role_evidence:
        # No signal at all — either unsupported extension or truly empty content
        if file.extension.lower() not in {".txt", ".md", ".csv", ".json", ".html", ".pdf"}:
            return "none"
        return "sparse"
    return "usable"


def _text_quality_reason(file: IntakeFile, quality: str) -> str:
    """Human-readable explanation for text quality."""
    if quality == "none":
        if file.errors:
            return "File could not be read due to errors."
        if "file is empty" in " ".join(file.warnings).lower():
            return "File is empty — no content to extract."
        if "minimal content" in " ".join(file.warnings).lower():
            return "PDF or binary file yielded no readable text."
        return "No readable text was extracted from this file."
    if quality == "sparse":
        if "minimal content" in " ".join(file.warnings).lower():
            return "PDF text extraction yielded minimal content. File may be scanned/image-only."
        if not file.role_scores:
            return "Text was extracted but no known role patterns matched. Content may be very short or unrecognized."
        return "Limited text was extracted. Classification confidence is reduced."
    return "Document text was readable and role patterns were matched."


def _build_filename_evidence(file: IntakeFile) -> dict[str, Any]:
    """Build filename evidence from an IntakeFile.

    Calls _extract_filename_metadata directly so that the returned
    parsed_oem_candidates reflects what was actually parsed from the filename,
    not the (possibly model-inferred or text-detected) file.detected_oem.
    """
    from repairgraph.intake.classify import _extract_filename_metadata, _MODEL_TO_OEM  # noqa: PLC0415
    stem = Path(file.filename).stem
    fn_meta = _extract_filename_metadata(stem)
    tokens = _filename_tokens(file.filename)
    model_inferred_oem = (
        _MODEL_TO_OEM.get(fn_meta["model"]) if fn_meta["model"] else None
    )
    return {
        "parsed_oem_candidates": [fn_meta["oem"]] if fn_meta["oem"] else [],
        "parsed_model_candidates": [fn_meta["model"]] if fn_meta["model"] else [],
        "parsed_year_candidates": [fn_meta["year"]] if fn_meta["year"] else [],
        "parsed_operation_candidates": [fn_meta["operation"]] if fn_meta["operation"] else [],
        "model_inferred_oem": model_inferred_oem,
        "filename_tokens": tokens,
        "note": (
            "Filename evidence is high-signal and takes priority over document text "
            "for OEM, model, and year detection. It is not subject to the isolation penalty."
        ),
    }


def _build_text_evidence(file: IntakeFile) -> dict[str, Any]:
    """Build text evidence summary from an IntakeFile."""
    quality = _text_quality(file)
    reason = _text_quality_reason(file, quality)

    # Estimate text length proxy from whether role scoring occurred
    has_role_signals = bool(file.role_scores)
    role_signal_count = len(file.role_scores)

    # Extract non-breadcrumb evidence phrases (these come from text matches)
    text_matched_phrases = [
        ev for ev in file.role_evidence if not ev.startswith("[bc]")
    ]

    return {
        "text_quality": quality,
        "text_quality_reason": reason,
        "has_role_signals": has_role_signals,
        "role_signal_count": role_signal_count,
        "text_matched_phrases": text_matched_phrases,
        "note": (
            "Extracted text is not stored in the manifest. "
            "Text quality is inferred from warnings and role scoring results."
        ),
    }


def _build_breadcrumb_evidence(file: IntakeFile) -> dict[str, Any]:
    """Extract breadcrumb navigation evidence from role_evidence tags."""
    breadcrumb_items = [ev for ev in file.role_evidence if ev.startswith("[bc]")]
    segments = [item[5:].strip() for item in breadcrumb_items]  # strip "[bc] " prefix

    # Map breadcrumb segments to likely roles (from role_evidence assignment)
    # We know which role the evidence was filed under by looking at role_scores
    role_implications: dict[str, list[str]] = {}
    # Breadcrumb segments imply the primary role and/or supporting roles
    all_roles = [file.document_role] + file.supporting_roles
    for seg in segments:
        for role in all_roles:
            role_implications.setdefault(role, []).append(seg)
            break  # just credit the primary matching role

    return {
        "detected_breadcrumb_segments": segments,
        "breadcrumb_count": len(segments),
        "role_implications_from_breadcrumbs": role_implications,
        "breadcrumbs_found": len(segments) > 0,
        "note": (
            "Breadcrumb navigation lines (e.g. 'Elantra > Body Frame > Weld Points') "
            "are the highest-weight evidence signal (5× keyword weight). "
            "They indicate ALLDATA-style document navigation structure."
        ),
    }


def _build_role_evidence_section(file: IntakeFile) -> dict[str, Any]:
    """Build role evidence section from an IntakeFile."""
    confidence_explanation = _explain_confidence(file)

    # Separate breadcrumb vs phrase evidence
    breadcrumb_evidence = [ev for ev in file.role_evidence if ev.startswith("[bc]")]
    phrase_evidence = [ev for ev in file.role_evidence if not ev.startswith("[bc]")]

    return {
        "primary_role": file.document_role,
        "supporting_roles": file.supporting_roles,
        "role_scores": file.role_scores,
        "role_evidence_phrases": phrase_evidence,
        "role_evidence_breadcrumbs": breadcrumb_evidence,
        "confidence": file.confidence,
        "confidence_explanation": confidence_explanation,
        "score_note": (
            "role_scores are normalised to [0.0, 1.0] where 1.0 = highest-scoring role. "
            "supporting_roles are roles scoring ≥30% of the top score."
        ),
    }


def _explain_confidence(file: IntakeFile) -> str:
    """Return a plain-language explanation of why confidence has its value."""
    parts: list[str] = []

    if file.errors:
        return "Confidence is 0.0 — file could not be read."

    if file.confidence == 0.0:
        if not file.role_scores:
            return "Confidence is 0.0 — no text was extracted and no role signals were found."
        return (
            "Confidence is 0.0 — text was extracted and role patterns matched, "
            "but no OEM could be detected from filename or document content."
        )

    # Explain OEM source — build as a single sentence so qualifiers don't
    # start new fragments after a period when joined with ". ".
    if file.detected_oem:
        warning_joined = " ".join(file.warnings)
        if "METADATA_CONFLICT" in warning_joined:
            parts.append(
                f"OEM '{file.detected_oem}' detected "
                "(filename/text conflict — filename prioritised, confidence reduced)"
            )
        elif file.confidence >= 0.70:
            parts.append(
                f"OEM '{file.detected_oem}' detected with strong agreement "
                "between filename and text"
            )
        elif file.confidence >= 0.50:
            parts.append(
                f"OEM '{file.detected_oem}' detected from filename evidence "
                "(text corroboration absent or weak)"
            )
        else:
            parts.append(
                f"OEM '{file.detected_oem}' detected with limited corroboration"
            )
    else:
        parts.append("No OEM detected (reduces base confidence)")

    # Explain role penalty
    if file.document_role == "unknown":
        parts.append("Unknown role incurs a −0.1 confidence penalty")

    # Explain PDF cap
    if file.extension.lower() == ".pdf" and file.confidence <= 0.60:
        parts.append("PDF files are capped at 60% confidence due to heuristic text extraction")

    # Explain unsupported extension
    if file.extension.lower() not in {".txt", ".md", ".csv", ".json", ".html", ".pdf"}:
        parts.append("Unsupported extension capped at 20% confidence")

    # Overall assessment
    if file.confidence >= 0.65:
        parts.append(f"→ Final confidence {file.confidence:.0%} (high)")
    elif file.confidence >= 0.35:
        parts.append(f"→ Final confidence {file.confidence:.0%} (medium — review recommended)")
    else:
        parts.append(f"→ Final confidence {file.confidence:.0%} (low — classification unreliable)")

    return ". ".join(parts) + "."


def _build_diagnostics_for_file(file: IntakeFile) -> list[dict[str, Any]]:
    """Generate diagnostic codes and explanations for a single file."""
    diags: list[dict[str, Any]] = []

    # Error file — stop early
    if file.errors:
        diags.append({
            "code": "FILE_READ_ERROR",
            "message": "File could not be read.",
            "detail": "; ".join(file.errors),
        })
        return diags

    quality = _text_quality(file)

    # Sparse/no text
    if quality == "none":
        diags.append({
            "code": DIAG_SPARSE_TEXT_EXTRACTION,
            "message": "No usable text was extracted from this file.",
            "detail": (
                "Classification is based on filename evidence only. "
                "Role detection requires readable text content."
            ),
        })
    elif quality == "sparse":
        diags.append({
            "code": DIAG_SPARSE_TEXT_EXTRACTION,
            "message": "Minimal text was extracted. Classification confidence is reduced.",
            "detail": (
                "Consider supplying text-format documents (.txt, .md) for best results. "
                "PDF heuristic extraction may miss content in scanned or image-based files."
            ),
        })

    # Filename-only metadata
    if file.detected_oem and not file.role_scores:
        diags.append({
            "code": DIAG_FILENAME_ONLY_METADATA,
            "message": "OEM/metadata identified from filename — no text metadata evidence.",
            "detail": (
                f"OEM={file.detected_oem!r} was identified from filename tokens or model name, "
                "but document text was not readable or had no matching OEM patterns."
            ),
        })

    # Operation-inferred role
    if "ROLE_FROM_OPERATION" in " ".join(file.warnings):
        op_warn = next(
            (w for w in file.warnings if w.startswith("ROLE_FROM_OPERATION:")), ""
        )
        diags.append({
            "code": DIAG_ROLE_FROM_OPERATION,
            "message": (
                f"Role '{file.document_role}' inferred from filename operation — "
                "text content was too sparse for direct role detection."
            ),
            "detail": (
                op_warn or (
                    "Supply text-format documents for content-based role detection. "
                    "Operation-inferred roles carry lower confidence than content-detected roles."
                )
            ),
        })

    # Role detection issues
    if file.document_role == "unknown":
        if not file.role_scores:
            diags.append({
                "code": DIAG_ROLE_SCORE_BELOW_THRESHOLD,
                "message": "No role scored above threshold — document role is unknown.",
                "detail": (
                    "No keyword patterns, ontology phrases, or breadcrumb segments "
                    "matched any known document role. Check if document text is readable "
                    "and contains repair-related content."
                ),
            })
        else:
            max_score = max(file.role_scores.values(), default=0.0)
            diags.append({
                "code": DIAG_ROLE_SCORE_BELOW_THRESHOLD,
                "message": "All role scores are below detection threshold — document role is unknown.",
                "detail": (
                    f"Highest normalised score: {max_score:.0%}. "
                    "Scores are normalised to 1.0 for the top role. "
                    "This indicates weak or ambiguous role signals."
                ),
            })

        # Supporting role only (unknown primary but some supporting signals)
        if file.supporting_roles:
            diags.append({
                "code": DIAG_SUPPORTING_ROLE_ONLY,
                "message": (
                    f"Role(s) detected only as supporting: {', '.join(file.supporting_roles)}. "
                    "No strong primary role was identified."
                ),
                "detail": (
                    "Supporting roles score ≥30% of the top score but none scored "
                    "strongly enough to be a reliable primary classification."
                ),
            })

    elif file.confidence < 0.30:
        diags.append({
            "code": DIAG_ROLE_SCORE_BELOW_THRESHOLD,
            "message": f"Low confidence ({file.confidence:.0%}) — classification may be unreliable.",
            "detail": _explain_confidence(file),
        })

    # Supporting roles present (informational)
    if file.supporting_roles and file.document_role != "unknown":
        diags.append({
            "code": DIAG_ROLE_COVERAGE_FROM_SUPPORTING,
            "message": (
                f"Supporting roles detected: {', '.join(file.supporting_roles)}. "
                "These contribute to packet-level role coverage."
            ),
            "detail": (
                "Supporting roles count as found in the packet role coverage summary. "
                "They score ≥30% of the top role score."
            ),
        })

    # Breadcrumb evidence
    breadcrumb_items = [ev for ev in file.role_evidence if ev.startswith("[bc]")]
    if breadcrumb_items:
        diags.append({
            "code": DIAG_BREADCRUMB_EVIDENCE_FOUND,
            "message": (
                f"Breadcrumb navigation detected ({len(breadcrumb_items)} segment(s)). "
                "These are the strongest role evidence signals (5× weight)."
            ),
            "detail": "; ".join(s[5:].strip() for s in breadcrumb_items[:3]),
        })

    return diags


def explain_file_classification(file: IntakeFile) -> list[str]:
    """Return a list of plain-language sentences explaining how this file was classified.

    Covers: OEM detection source, text quality, role classification rationale,
    evidence phrases, and confidence reasoning.
    """
    lines: list[str] = []
    quality = _text_quality(file)
    fn_ev = _build_filename_evidence(file)

    # OEM detection
    if file.detected_oem:
        has_fn_oem = bool(fn_ev["parsed_oem_candidates"])
        model_inferred_oem = fn_ev.get("model_inferred_oem")
        warning_joined = " ".join(file.warnings)
        if has_fn_oem:
            if "METADATA_CONFLICT" in warning_joined:
                lines.append(
                    f"OEM '{file.detected_oem}' detected from filename; "
                    "document text indicated a different OEM (conflict resolved by filename priority)."
                )
            else:
                lines.append(f"OEM '{file.detected_oem}' detected from filename tokens.")
        elif model_inferred_oem and model_inferred_oem == file.detected_oem:
            lines.append(
                f"OEM '{file.detected_oem}' inferred from model name "
                f"'{file.detected_model}' found in filename."
            )
        elif "MODEL_OEM_OVERRIDE" in warning_joined:
            lines.append(
                f"OEM '{file.detected_oem}' inferred from model name '{file.detected_model}' "
                "(overriding weak text-detected OEM signal)."
            )
        else:
            lines.append(f"OEM '{file.detected_oem}' detected from document text.")
    else:
        lines.append("No OEM could be detected from filename or document text.")

    if file.detected_model:
        lines.append(f"Model '{file.detected_model}' detected.")
    if file.detected_year:
        lines.append(f"Year '{file.detected_year}' detected.")

    # Text quality
    if quality == "none":
        lines.append(
            "No usable text was extracted — role classification relies on filename evidence only."
        )
    elif quality == "sparse":
        lines.append(
            "Limited text was extracted — classification confidence is reduced. "
            "Consider supplying text-format documents."
        )
    else:
        count = len(file.role_scores)
        lines.append(
            f"Document text was readable; {count} role(s) scored above zero."
        )

    # Role classification
    warning_text = " ".join(file.warnings)
    if file.document_role == "unknown":
        if not file.role_scores:
            lines.append(
                "Document role could not be determined — no role patterns matched. "
                "The file may not contain collision repair content, or text extraction failed."
            )
        else:
            lines.append(
                "Document role could not be determined — all role scores fell below threshold."
            )
        if file.supporting_roles:
            lines.append(
                f"Weak signals detected for: {', '.join(file.supporting_roles)} "
                "(insufficient for primary classification)."
            )
    elif "ROLE_FROM_OPERATION" in warning_text:
        lines.append(
            f"Primary role '{file.document_role}' inferred from filename operation — "
            "text extraction did not yield enough content for direct role detection."
        )
    else:
        lines.append(
            f"Primary role '{file.document_role}' selected as the highest-scoring role."
        )
        if file.supporting_roles:
            lines.append(
                f"Supporting roles also detected: {', '.join(file.supporting_roles)}. "
                "These count as covered in the packet role coverage summary."
            )

    # Evidence
    bc_items = [e for e in file.role_evidence if e.startswith("[bc]")]
    phrase_items = [e for e in file.role_evidence if not e.startswith("[bc]")]
    if phrase_items:
        lines.append(f"Ontology/keyword evidence: {', '.join(phrase_items[:4])}.")
    if bc_items:
        segs = [s[5:].strip() for s in bc_items[:3]]
        lines.append(f"Breadcrumb navigation evidence: {', '.join(segs)}.")

    # Confidence
    lines.append(_explain_confidence(file))

    return lines


def build_file_evidence(file: IntakeFile) -> dict[str, Any]:
    """Build a structured evidence payload for a single IntakeFile.

    Returns a JSON-serializable dict containing:
    - filename_evidence: parsed OEM/model/year/operation candidates and tokens
    - text_evidence: quality indicator and text signal summary
    - breadcrumb_evidence: detected breadcrumb segments and role implications
    - role_evidence: primary/supporting roles, scores, evidence phrases, confidence
    - diagnostics_for_file: structured diagnostic codes with explanations
    - classification_explanation: ordered plain-language explanation sentences
    """
    return {
        "file_id": file.file_id,
        "filename": file.filename,
        "extension": file.extension,
        "size_bytes": file.size_bytes,
        "filename_evidence": _build_filename_evidence(file),
        "text_evidence": _build_text_evidence(file),
        "breadcrumb_evidence": _build_breadcrumb_evidence(file),
        "role_evidence": _build_role_evidence_section(file),
        "diagnostics_for_file": _build_diagnostics_for_file(file),
        "classification_explanation": explain_file_classification(file),
    }


def summarize_role_coverage(manifest: IntakeManifest) -> dict[str, Any]:
    """Compute role coverage respecting both primary and supporting roles.

    A role is considered 'found' if it appears as the primary document_role
    or as a supporting_role in any readable file. Missing roles exclude those
    covered by supporting roles.

    Returns a JSON-serializable dict with coverage detail per role.
    """
    # Roles found as primary document_role in any readable file
    found_primary: set[str] = set()
    # Roles found as supporting_role in any readable file
    found_supporting: set[str] = set()

    for f in manifest.files:
        if f.errors:
            continue
        if f.document_role != "unknown":
            found_primary.add(f.document_role)
        for r in f.supporting_roles:
            if r != "unknown":
                found_supporting.add(r)

    all_found = found_primary | found_supporting
    supporting_only = found_supporting - found_primary

    coverage_detail: dict[str, dict[str, Any]] = {}
    for role in _ALL_TRACKED_ROLES:
        if role in found_primary:
            coverage_detail[role] = {
                "found": True,
                "source": "primary_role",
                "note": "Detected as primary document_role in at least one file.",
            }
        elif role in found_supporting:
            coverage_detail[role] = {
                "found": True,
                "source": "supporting_role",
                "note": (
                    "Detected as supporting role (≥30% of top score) in at least one file. "
                    "Not a primary classification."
                ),
            }
        else:
            coverage_detail[role] = {
                "found": False,
                "source": None,
                "note": "Not detected in any file as primary or supporting role.",
            }

    found_count = len(all_found)
    total = len(_ALL_TRACKED_ROLES)

    return {
        "roles_found": sorted(all_found),
        "roles_missing": sorted(r for r in _ALL_TRACKED_ROLES if r not in all_found),
        "found_from_primary_role": sorted(found_primary),
        "found_from_supporting_role_only": sorted(supporting_only),
        "coverage_detail": coverage_detail,
        "coverage_note": (
            f"Found {found_count} of {total} tracked roles. "
            f"{len(supporting_only)} role(s) covered via supporting roles only."
        ),
        "advisory": (
            "Role coverage includes supporting roles detected at ≥30% of the top role score. "
            "Supporting role coverage is weaker evidence than primary classification. "
            "Review source documents before relying on supporting-role coverage for normalization."
        ),
    }


def build_intake_evidence_payload(manifest: IntakeManifest) -> dict[str, Any]:
    """Build a complete evidence/debug payload from an IntakeManifest.

    Produces a JSON-serializable dict containing:
    - per-file evidence (filename, text, breadcrumb, role evidence, diagnostics)
    - corrected role coverage summary respecting supporting roles
    - advisory language

    Does not re-read files — all data is derived from the manifest.
    Deterministic for a given manifest.
    """
    return {
        "schema_name": "repairgraph.intake_evidence",
        "schema_version": "0.1",
        "intake_id": manifest.intake_id,
        "created_at": manifest.created_at,
        "file_evidence": [build_file_evidence(f) for f in manifest.files],
        "role_coverage": summarize_role_coverage(manifest),
        "advisory": (
            "Evidence payloads are heuristic estimates derived from classification outputs. "
            "They do not certify OEM authenticity, document completeness, or normalization readiness. "
            "All outputs require qualified review before use in repair workflow generation."
        ),
    }
