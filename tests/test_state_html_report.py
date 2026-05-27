"""
Tests for repairgraph.state.html_report.

Verifies that HTML reports are generated correctly, contain required sections,
are deterministic, and include advisory and structural content.
"""
from __future__ import annotations

import pytest

from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.state.html_report import (
    build_replay_html_report,
    build_summary_cards,
    build_visualization_sections,
    build_workflow_html_report,
)


@pytest.fixture(scope="module")
def projected_state():
    return build_accord_projected_state()


@pytest.fixture(scope="module")
def initial_state():
    return build_accord_initial_state()


@pytest.fixture(scope="module")
def demo_events(initial_state):
    return build_accord_demo_events(initial_state)


@pytest.fixture(scope="module")
def workflow_html(projected_state):
    return build_workflow_html_report(projected_state)


@pytest.fixture(scope="module")
def replay_html(initial_state, demo_events):
    return build_replay_html_report(initial_state, demo_events)


# ── build_summary_cards ────────────────────────────────────────────────────────

class TestBuildSummaryCards:
    def test_returns_list_of_dicts(self, projected_state):
        cards = build_summary_cards(projected_state)
        assert isinstance(cards, list)
        assert len(cards) > 0

    def test_cards_have_required_keys(self, projected_state):
        cards = build_summary_cards(projected_state)
        for card in cards:
            assert "value" in card
            assert "label" in card
            assert "accent" in card

    def test_card_values_are_strings(self, projected_state):
        cards = build_summary_cards(projected_state)
        for card in cards:
            assert isinstance(card["value"], str)
            assert isinstance(card["label"], str)

    def test_includes_phases_card(self, projected_state):
        cards = build_summary_cards(projected_state)
        labels = [c["label"] for c in cards]
        assert any("phase" in lbl.lower() for lbl in labels)

    def test_includes_blockers_card(self, projected_state):
        cards = build_summary_cards(projected_state)
        labels = [c["label"] for c in cards]
        assert any("blocker" in lbl.lower() for lbl in labels)

    def test_includes_events_card(self, projected_state):
        cards = build_summary_cards(projected_state)
        labels = [c["label"] for c in cards]
        assert any("event" in lbl.lower() for lbl in labels)

    def test_deterministic(self, projected_state):
        cards_a = build_summary_cards(projected_state)
        cards_b = build_summary_cards(projected_state)
        assert cards_a == cards_b


# ── build_visualization_sections ──────────────────────────────────────────────

class TestBuildVisualizationSections:
    def test_returns_dict(self, projected_state):
        vis = build_visualization_sections(projected_state)
        assert isinstance(vis, dict)

    def test_contains_all_diagram_keys(self, projected_state):
        vis = build_visualization_sections(projected_state)
        assert "workflow_timeline" in vis
        assert "phase_flow" in vis
        assert "blocker_flow" in vis
        assert "zone_activation" in vis

    def test_diagram_values_are_strings(self, projected_state):
        vis = build_visualization_sections(projected_state)
        for key in ("workflow_timeline", "phase_flow", "blocker_flow", "zone_activation"):
            assert isinstance(vis[key], str)
            assert len(vis[key]) > 0

    def test_contains_sections_list(self, projected_state):
        vis = build_visualization_sections(projected_state)
        assert "sections" in vis
        assert isinstance(vis["sections"], list)

    def test_mermaid_sources_contain_valid_header(self, projected_state):
        vis = build_visualization_sections(projected_state)
        assert "sequenceDiagram" in vis["workflow_timeline"]
        assert "flowchart" in vis["phase_flow"]
        assert "flowchart" in vis["blocker_flow"]
        assert "flowchart" in vis["zone_activation"]

    def test_deterministic(self, projected_state):
        vis_a = build_visualization_sections(projected_state)
        vis_b = build_visualization_sections(projected_state)
        assert vis_a == vis_b


# ── build_workflow_html_report ─────────────────────────────────────────────────

class TestBuildWorkflowHtmlReport:
    def test_returns_string(self, workflow_html):
        assert isinstance(workflow_html, str)

    def test_is_valid_html_document(self, workflow_html):
        assert workflow_html.startswith("<!DOCTYPE html>")
        assert "<html" in workflow_html
        assert "</html>" in workflow_html
        assert "<head>" in workflow_html
        assert "<body>" in workflow_html
        assert "</body>" in workflow_html

    def test_contains_advisory_banner(self, workflow_html):
        assert "advisory-banner" in workflow_html
        assert "Advisory" in workflow_html

    def test_contains_advisory_language(self, workflow_html):
        assert "OEM" in workflow_html
        assert "advisory" in workflow_html.lower()

    def test_contains_workflow_summary(self, workflow_html):
        assert "Workflow Summary" in workflow_html

    def test_contains_session_overview(self, workflow_html):
        assert "Session Overview" in workflow_html
        assert "Accord" in workflow_html

    def test_contains_next_actions_section(self, workflow_html):
        assert "Next Recommended Actions" in workflow_html

    def test_contains_blockers_section(self, workflow_html):
        assert "Blocker" in workflow_html

    def test_contains_event_timeline(self, workflow_html):
        assert "Event Timeline" in workflow_html

    def test_contains_phase_overview(self, workflow_html):
        assert "Phase" in workflow_html

    def test_contains_mermaid_sections(self, workflow_html):
        assert "mermaid-block" in workflow_html
        assert "sequenceDiagram" in workflow_html
        assert "flowchart" in workflow_html

    def test_contains_mermaid_workflow_timeline(self, workflow_html):
        assert "Workflow Timeline Diagram" in workflow_html

    def test_contains_mermaid_phase_flow(self, workflow_html):
        assert "Phase Flow Diagram" in workflow_html

    def test_contains_mermaid_blocker_flow(self, workflow_html):
        assert "Blocker Flow Diagram" in workflow_html

    def test_contains_mermaid_zone_activation(self, workflow_html):
        assert "Zone Activation Diagram" in workflow_html

    def test_no_external_script_src(self, workflow_html):
        assert 'src="http' not in workflow_html
        assert "src='http" not in workflow_html

    def test_no_external_link_href_cdn(self, workflow_html):
        # No CDN stylesheet links
        assert 'href="https://cdn' not in workflow_html
        assert 'href="http://cdn' not in workflow_html

    def test_inline_css_present(self, workflow_html):
        assert "<style>" in workflow_html

    def test_deterministic(self, projected_state):
        html_a = build_workflow_html_report(projected_state)
        html_b = build_workflow_html_report(projected_state)
        assert html_a == html_b

    def test_contains_oem_name(self, workflow_html):
        assert "Honda" in workflow_html

    def test_contains_model_name(self, workflow_html):
        assert "Accord" in workflow_html

    def test_contains_repairgraph_branding(self, workflow_html):
        assert "RepairGraph" in workflow_html


# ── build_replay_html_report ───────────────────────────────────────────────────

class TestBuildReplayHtmlReport:
    def test_returns_string(self, replay_html):
        assert isinstance(replay_html, str)

    def test_is_valid_html_document(self, replay_html):
        assert replay_html.startswith("<!DOCTYPE html>")
        assert "<html" in replay_html
        assert "</html>" in replay_html

    def test_contains_advisory_banner(self, replay_html):
        assert "advisory-banner" in replay_html
        assert "Advisory" in replay_html

    def test_contains_replay_inspector(self, replay_html):
        assert "Replay Inspector" in replay_html

    def test_contains_replay_panel(self, replay_html):
        assert "replay-panel" in replay_html

    def test_contains_step_chips(self, replay_html):
        assert "step-chips" in replay_html

    def test_contains_replay_controls(self, replay_html):
        assert "replay-controls" in replay_html

    def test_contains_replay_step_summary(self, replay_html):
        assert "Replay Step Summary" in replay_html

    def test_contains_inline_js_replay_data(self, replay_html):
        assert "_replayData" in replay_html
        assert "initReplay" in replay_html

    def test_contains_event_steps(self, replay_html, demo_events):
        assert f'"event_count"' not in replay_html  # this is in JSON API not HTML
        # Verify step data embedded
        assert "step" in replay_html
        assert str(len(demo_events)) in replay_html

    def test_contains_session_overview(self, replay_html):
        assert "Session Overview" in replay_html

    def test_contains_final_state_summary(self, replay_html):
        assert "Final State Summary" in replay_html

    def test_contains_mermaid_sections(self, replay_html):
        assert "mermaid-block" in replay_html
        assert "flowchart" in replay_html

    def test_no_external_dependencies(self, replay_html):
        assert 'src="http' not in replay_html
        assert "src='http" not in replay_html

    def test_deterministic(self, initial_state, demo_events):
        html_a = build_replay_html_report(initial_state, demo_events)
        html_b = build_replay_html_report(initial_state, demo_events)
        assert html_a == html_b

    def test_contains_vanilla_js_navigation(self, replay_html):
        assert "prevStep" in replay_html
        assert "nextStep" in replay_html
        assert "showStep" in replay_html

    def test_contains_oem_and_model(self, replay_html):
        assert "Honda" in replay_html
        assert "Accord" in replay_html

    def test_empty_events_handled_gracefully(self, initial_state):
        html_out = build_replay_html_report(initial_state, [])
        assert isinstance(html_out, str)
        assert "No events to replay" in html_out


# ── cross-cutting ──────────────────────────────────────────────────────────────

class TestReportCrossCutting:
    def test_workflow_report_larger_than_threshold(self, workflow_html):
        assert len(workflow_html) > 5000

    def test_replay_report_larger_than_threshold(self, replay_html):
        assert len(replay_html) > 5000

    def test_both_reports_self_contained(self, workflow_html, replay_html):
        for doc in (workflow_html, replay_html):
            assert "<!DOCTYPE html>" in doc
            assert "<style>" in doc
            assert "</html>" in doc
