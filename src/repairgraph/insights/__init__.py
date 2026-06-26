"""RepairGraph operational insight engine.

Consumes RepairState and IntakeManifest outputs to produce a deterministic
InsightPayload with prioritized findings. No AI/LLM — only rule-based logic.
"""
from repairgraph.insights.engine import build_insight_payload
from repairgraph.insights.schema import InsightFinding, InsightPayload, SEVERITY_ORDER

__all__ = ["build_insight_payload", "InsightFinding", "InsightPayload", "SEVERITY_ORDER"]
