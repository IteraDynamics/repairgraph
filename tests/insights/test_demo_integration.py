"""Integration tests — orchestrator includes insights, demo page embeds insights JSON."""
import json
import pytest


def test_full_demo_payload_has_insights():
    from repairgraph.demo.orchestrator import build_full_demo_payload
    payload = build_full_demo_payload()
    assert "insights" in payload
    ins = payload["insights"]
    assert ins["schema_name"] == "repairgraph.insights.payload"
    assert "findings" in ins
    assert "overall_status" in ins
    assert "risk_level" in ins
    assert "top_findings" in ins


def test_demo_page_embeds_insights_json():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    # Insights JSON is embedded in the page
    assert '"insights"' in html
    assert "overall_status" in html


def test_demo_page_has_hero_status_area():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "hero-status-area" in html


def test_demo_page_has_finding_card_css():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "finding-card" in html
    assert "sev-critical" in html


def test_demo_page_has_executive_summary_export():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "Executive Summary" in html


def test_demo_page_has_audit_trail_export():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "Repair Audit Trail" in html


def test_demo_page_has_technician_workflow_export():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "Technician Workflow" in html


def test_demo_page_has_replay_significance_css():
    from repairgraph.demo.demo_page import build_demo_page_html
    html = build_demo_page_html()
    assert "replay-significance" in html


def test_workflow_replay_steps_have_significance():
    from repairgraph.demo.orchestrator import build_workflow_demo_payload
    payload = build_workflow_demo_payload()
    steps = payload["replay_steps"]
    assert len(steps) > 0
    for step in steps:
        assert "significance" in step, f"Step {step.get('step')} missing significance"
        assert step["significance"], f"Step {step.get('step')} has empty significance"


def test_insight_payload_findings_sorted():
    from repairgraph.demo.orchestrator import build_insight_demo_payload
    from repairgraph.insights.schema import SEVERITY_ORDER
    payload = build_insight_demo_payload()
    severities = [SEVERITY_ORDER[f["severity"]] for f in payload["findings"]]
    assert severities == sorted(severities)
