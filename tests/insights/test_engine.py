"""Tests for the insight engine — prioritization, status derivation, and output shape."""
import pytest
from repairgraph.insights.engine import build_insight_payload
from repairgraph.insights.schema import SEVERITY_ORDER
from repairgraph.state.demo import build_accord_projected_state


@pytest.fixture(scope="module")
def accord_payload():
    state = build_accord_projected_state()
    return build_insight_payload(state)


def test_payload_has_findings(accord_payload):
    assert len(accord_payload.findings) > 0


def test_findings_sorted_by_severity(accord_payload):
    severities = [SEVERITY_ORDER[f.severity] for f in accord_payload.findings]
    assert severities == sorted(severities), "Findings must be sorted critical→informational"


def test_overall_status_blocked(accord_payload):
    # Accord demo has multiple blocked phases — should be blocked or at_risk
    assert accord_payload.overall_status in ("blocked", "at_risk")


def test_risk_level_is_high_or_critical(accord_payload):
    assert accord_payload.risk_level in ("critical", "high")


def test_headline_is_nonempty(accord_payload):
    assert accord_payload.summary_headline


def test_next_action_is_nonempty(accord_payload):
    assert accord_payload.next_action


def test_finding_counts_match_findings(accord_payload):
    from repairgraph.insights.schema import SEVERITY_ORDER
    expected = {s: 0 for s in SEVERITY_ORDER}
    for f in accord_payload.findings:
        expected[f.severity] += 1
    assert accord_payload.finding_counts == expected


def test_top_findings_at_most_five(accord_payload):
    assert len(accord_payload.top_findings) <= 5


def test_no_duplicate_finding_ids(accord_payload):
    ids = [f.finding_id for f in accord_payload.findings]
    assert len(ids) == len(set(ids))


def test_to_dict_is_serializable(accord_payload):
    import json
    d = accord_payload.to_dict()
    dumped = json.dumps(d)
    assert "findings" in dumped


def test_uhss_finding_present(accord_payload):
    ids = {f.finding_id for f in accord_payload.findings}
    assert "material_uhss_detected" in ids


def test_critical_qa_finding_present(accord_payload):
    critical_qa = [f for f in accord_payload.findings if f.severity == "critical" and f.category == "qa"]
    assert len(critical_qa) >= 1


def test_with_manifest_dict():
    """Engine accepts manifest_dict and produces intake findings."""
    state = build_accord_projected_state()
    manifest = {
        "readiness": "partial",
        "missing_roles": ["corrosion_protection"],
        "files": [],
        "detected_packet": {"oem": "Honda", "model": "Accord"},
    }
    payload = build_insight_payload(state, manifest_dict=manifest)
    ids = {f.finding_id for f in payload.findings}
    assert "intake_missing_critical_roles" in ids


def test_empty_state_does_not_crash():
    """Engine handles a minimal RepairState without errors."""
    from repairgraph.state.schema import RepairSession, RepairState
    minimal = RepairState(session=RepairSession(
        session_id="s1", oem="TestOEM", year=2024, model="TestModel",
        operation="test_op", status="in_progress",
    ))
    payload = build_insight_payload(minimal)
    assert payload is not None
    assert payload.overall_status in ("ready", "at_risk", "blocked", "complete", "unknown")
