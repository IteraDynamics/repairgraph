"""Tests for insight prioritization rules — critical always before informational, etc."""
from repairgraph.insights.schema import InsightFinding, InsightPayload, SEVERITY_ORDER
from repairgraph.insights.engine import _sort_findings


def _f(finding_id, severity, category="qa"):
    return InsightFinding(
        finding_id=finding_id,
        severity=severity,
        category=category,
        title="T",
        explanation="E",
        recommended_action="R",
        supporting_evidence=(),
        confidence="high",
    )


def test_sort_critical_before_high():
    findings = [_f("b", "high"), _f("a", "critical")]
    result = _sort_findings(findings)
    assert result[0].severity == "critical"
    assert result[1].severity == "high"


def test_sort_high_before_medium():
    findings = [_f("m", "medium"), _f("h", "high")]
    result = _sort_findings(findings)
    assert result[0].severity == "high"


def test_sort_informational_last():
    findings = [_f("i", "informational"), _f("c", "critical"), _f("l", "low")]
    result = _sort_findings(findings)
    assert result[0].severity == "critical"
    assert result[-1].severity == "informational"


def test_sort_stable_within_severity():
    findings = [_f("z_id", "high", "workflow"), _f("a_id", "high", "qa")]
    result = _sort_findings(findings)
    # Same severity — sorted by category then finding_id
    assert result[0].category == "qa"
    assert result[1].category == "workflow"


def test_sort_empty():
    assert _sort_findings([]) == []


def test_sort_all_same_severity():
    findings = [_f("c", "medium"), _f("a", "medium"), _f("b", "medium")]
    result = _sort_findings(findings)
    ids = [f.finding_id for f in result]
    assert ids == sorted(ids)  # sorted by finding_id since severity+category same


def test_never_alphabetical_across_severities():
    """A severity=informational finding with id 'aaa' must not sort before severity=critical 'zzz'."""
    findings = [_f("aaa", "informational"), _f("zzz", "critical")]
    result = _sort_findings(findings)
    assert result[0].finding_id == "zzz"
    assert result[1].finding_id == "aaa"
