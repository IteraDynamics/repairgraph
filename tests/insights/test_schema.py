"""Tests for InsightFinding and InsightPayload schema."""
import pytest
from repairgraph.insights.schema import InsightFinding, InsightPayload, SEVERITY_ORDER


def _finding(**kwargs):
    defaults = dict(
        finding_id="test_id",
        severity="high",
        category="qa",
        title="Test",
        explanation="Explanation.",
        recommended_action="Do something.",
        supporting_evidence=("key=val",),
        confidence="high",
    )
    return InsightFinding(**{**defaults, **kwargs})


def test_severity_order_keys():
    assert set(SEVERITY_ORDER.keys()) == {"critical", "high", "medium", "low", "informational"}


def test_severity_order_values():
    assert SEVERITY_ORDER["critical"] < SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"]
    assert SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"] < SEVERITY_ORDER["informational"]


def test_finding_frozen():
    f = _finding()
    with pytest.raises((AttributeError, TypeError)):
        f.title = "changed"  # type: ignore[misc]


def test_finding_to_dict():
    f = _finding(finding_id="f1", severity="critical", category="workflow")
    d = f.to_dict()
    assert d["finding_id"] == "f1"
    assert d["severity"] == "critical"
    assert isinstance(d["supporting_evidence"], list)


def test_payload_top_findings_limit():
    findings = [_finding(finding_id=f"f{i}") for i in range(10)]
    payload = InsightPayload(findings=findings)
    assert len(payload.top_findings) == 5
    assert payload.top_findings[0].finding_id == "f0"


def test_payload_to_dict_structure():
    payload = InsightPayload(
        overall_status="blocked",
        risk_level="critical",
        findings=[_finding()],
        summary_headline="Repair blocked.",
        next_action="Fix QA gate.",
        finding_counts={"critical": 0, "high": 1},
    )
    d = payload.to_dict()
    assert d["schema_name"] == "repairgraph.insights.payload"
    assert d["advisory"] is True
    assert d["overall_status"] == "blocked"
    assert len(d["findings"]) == 1
    assert len(d["top_findings"]) == 1


def test_payload_top_findings_in_dict():
    findings = [_finding(finding_id=f"f{i}") for i in range(8)]
    payload = InsightPayload(findings=findings)
    d = payload.to_dict()
    assert len(d["top_findings"]) == 5
    assert len(d["findings"]) == 8
