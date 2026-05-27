"""
Domain model for RepairGraph OEM repair packet intake.

Defines typed dataclasses for intake file classifications, packet detection,
diagnostics, and manifests. All types are immutable-friendly, deterministic,
and side-effect free.

Advisory: RepairGraph processes OEM repair information supplied by authorized
users/subscribers. It is not an OEM document distribution platform.
Classification outputs are heuristic estimates, not certified assessments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DOCUMENT_ROLES = frozenset({
    "repair_procedure",
    "sectioning",
    "welding",
    "corrosion_protection",
    "materials",
    "dimensions",
    "calibration",
    "precautions",
    "unknown",
})

READINESS_LEVELS = frozenset({"ready", "partial", "incomplete", "unprocessable"})
DIAGNOSTIC_SEVERITIES = frozenset({"info", "warning", "error"})

SUPPORTED_EXTENSIONS = frozenset({".txt", ".pdf", ".md", ".json", ".csv", ".html"})
TEXT_EXTENSIONS = frozenset({".txt", ".md", ".csv", ".json", ".html"})
BINARY_EXTENSIONS = frozenset({".pdf"})

_INTAKE_ADVISORY = (
    "This intake classification is a heuristic estimate. It does not certify "
    "document completeness, OEM authenticity, or extraction readiness. "
    "RepairGraph processes OEM repair information supplied by authorized users. "
    "It is not an OEM document distribution platform."
)


@dataclass(slots=True)
class IntakeFile:
    """Classification result for a single intake file.

    All detected fields are heuristic estimates. confidence reflects the
    classifier's self-assessed certainty, not a ground-truth accuracy measure.
    """
    file_id: str
    filename: str
    extension: str
    size_bytes: int
    detected_oem: str | None = None
    detected_model: str | None = None
    detected_year: int | None = None
    detected_operation: str | None = None
    document_role: str = "unknown"
    supporting_roles: list[str] = field(default_factory=list)
    role_scores: dict[str, float] = field(default_factory=dict)
    role_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    advisory_note: str = _INTAKE_ADVISORY

    def __post_init__(self) -> None:
        if self.document_role not in DOCUMENT_ROLES:
            raise ValueError(f"Invalid document_role: {self.document_role!r}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(slots=True)
class IntakeDiagnostic:
    """A single diagnostic message produced during intake processing."""
    code: str
    severity: str
    message: str
    file_id: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in DIAGNOSTIC_SEVERITIES:
            raise ValueError(f"Invalid diagnostic severity: {self.severity!r}")


@dataclass(slots=True)
class IntakePacket:
    """Aggregate detected metadata across all files in an intake packet."""
    detected_oem: str | None = None
    detected_model: str | None = None
    detected_year: int | None = None
    detected_operation: str | None = None
    oem_confidence: float = 0.0
    detected_roles: list[str] = field(default_factory=list)
    file_count: int = 0


@dataclass(slots=True)
class IntakeSession:
    """Metadata for an intake processing session."""
    session_id: str
    intake_id: str
    created_at: str
    file_count: int
    source_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IntakeClassification:
    """Classification result bundle for a single file, as returned by the classifier."""
    file: IntakeFile
    role: str
    oem: str | None
    model: str | None
    year: int | None
    confidence: float


@dataclass(slots=True)
class IntakeManifest:
    """Full intake result for a packet of OEM repair files.

    Contains per-file classifications, aggregated packet metadata, missing
    role analysis, diagnostics, and an overall readiness assessment.
    """
    intake_id: str
    files: list[IntakeFile] = field(default_factory=list)
    detected_packet: IntakePacket = field(default_factory=IntakePacket)
    missing_roles: list[str] = field(default_factory=list)
    diagnostics: list[IntakeDiagnostic] = field(default_factory=list)
    readiness: str = "incomplete"
    created_at: str = ""
    advisory: str = _INTAKE_ADVISORY

    def __post_init__(self) -> None:
        if self.readiness not in READINESS_LEVELS:
            raise ValueError(f"Invalid readiness: {self.readiness!r}")
