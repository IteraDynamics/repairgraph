"""Schema for RepairGraph operational insight payloads."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}


@dataclass(frozen=True)
class InsightFinding:
    finding_id: str
    severity: Literal["critical", "high", "medium", "low", "informational"]
    category: str
    title: str
    explanation: str
    recommended_action: str
    supporting_evidence: tuple[str, ...]
    confidence: Literal["high", "medium", "low"]

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "supporting_evidence": list(self.supporting_evidence),
            "confidence": self.confidence,
        }


@dataclass
class InsightPayload:
    schema_name: str = "repairgraph.insights.payload"
    advisory: bool = True
    overall_status: Literal["blocked", "at_risk", "ready", "complete", "unknown"] = "unknown"
    risk_level: Literal["critical", "high", "medium", "low", "none"] = "none"
    findings: list[InsightFinding] = field(default_factory=list)
    summary_headline: str = ""
    next_action: str = ""
    finding_counts: dict[str, int] = field(default_factory=dict)

    @property
    def top_findings(self) -> list[InsightFinding]:
        return self.findings[:5]

    def to_dict(self) -> dict:
        return {
            "schema_name": self.schema_name,
            "advisory": self.advisory,
            "overall_status": self.overall_status,
            "risk_level": self.risk_level,
            "findings": [f.to_dict() for f in self.findings],
            "top_findings": [f.to_dict() for f in self.top_findings],
            "summary_headline": self.summary_headline,
            "next_action": self.next_action,
            "finding_counts": self.finding_counts,
        }
