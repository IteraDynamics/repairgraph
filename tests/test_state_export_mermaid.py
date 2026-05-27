"""
Tests for repairgraph.state.export_mermaid — Mermaid diagram export.
"""
from __future__ import annotations

import pytest

from repairgraph.state.demo import build_accord_initial_state, build_accord_projected_state
from repairgraph.state.export_mermaid import (
    build_blocker_flow_mermaid,
    build_phase_flow_mermaid,
    build_workflow_timeline_mermaid,
    build_zone_activation_mermaid,
)


# ---------------------------------------------------------------------------
# build_workflow_timeline_mermaid
# ---------------------------------------------------------------------------

def test_workflow_timeline_returns_string():
    state = build_accord_projected_state()
    assert isinstance(build_workflow_timeline_mermaid(state), str)


def test_workflow_timeline_has_sequencediagram():
    state = build_accord_projected_state()
    assert "sequenceDiagram" in build_workflow_timeline_mermaid(state)


def test_workflow_timeline_has_advisory_comment():
    state = build_accord_projected_state()
    result = build_workflow_timeline_mermaid(state)
    assert "%% Advisory" in result


def test_workflow_timeline_includes_model_context():
    state = build_accord_projected_state()
    result = build_workflow_timeline_mermaid(state)
    assert "Accord" in result


def test_workflow_timeline_no_events_graceful():
    state = build_accord_initial_state()
    result = build_workflow_timeline_mermaid(state)
    assert "sequenceDiagram" in result
    assert "No events" in result


def test_workflow_timeline_includes_actor_participants():
    state = build_accord_projected_state()
    result = build_workflow_timeline_mermaid(state)
    assert "participant" in result


def test_workflow_timeline_includes_event_arrows():
    state = build_accord_projected_state()
    result = build_workflow_timeline_mermaid(state)
    assert "->>" in result


def test_workflow_timeline_is_deterministic():
    r1 = build_workflow_timeline_mermaid(build_accord_projected_state())
    r2 = build_workflow_timeline_mermaid(build_accord_projected_state())
    assert r1 == r2


def test_workflow_timeline_includes_event_types():
    state = build_accord_projected_state()
    result = build_workflow_timeline_mermaid(state)
    for event in state.events:
        assert event.event_type in result


# ---------------------------------------------------------------------------
# build_phase_flow_mermaid
# ---------------------------------------------------------------------------

def test_phase_flow_returns_string():
    state = build_accord_projected_state()
    assert isinstance(build_phase_flow_mermaid(state), str)


def test_phase_flow_has_flowchart():
    state = build_accord_projected_state()
    assert "flowchart" in build_phase_flow_mermaid(state)


def test_phase_flow_has_advisory_comment():
    state = build_accord_projected_state()
    result = build_phase_flow_mermaid(state)
    assert "%% Advisory" in result


def test_phase_flow_includes_model_context():
    state = build_accord_projected_state()
    result = build_phase_flow_mermaid(state)
    assert "Accord" in result


def test_phase_flow_includes_phase_nodes():
    state = build_accord_projected_state()
    result = build_phase_flow_mermaid(state)
    for phase in state.phases:
        node_id = f"P{phase.phase}"
        assert node_id in result


def test_phase_flow_includes_edges():
    state = build_accord_projected_state()
    result = build_phase_flow_mermaid(state)
    assert "-->" in result


def test_phase_flow_includes_classdefs():
    state = build_accord_projected_state()
    result = build_phase_flow_mermaid(state)
    assert "classDef" in result


def test_phase_flow_is_deterministic():
    r1 = build_phase_flow_mermaid(build_accord_projected_state())
    r2 = build_phase_flow_mermaid(build_accord_projected_state())
    assert r1 == r2


# ---------------------------------------------------------------------------
# build_blocker_flow_mermaid
# ---------------------------------------------------------------------------

def test_blocker_flow_returns_string():
    state = build_accord_projected_state()
    assert isinstance(build_blocker_flow_mermaid(state), str)


def test_blocker_flow_has_flowchart():
    state = build_accord_projected_state()
    assert "flowchart" in build_blocker_flow_mermaid(state)


def test_blocker_flow_has_advisory_comment():
    state = build_accord_projected_state()
    result = build_blocker_flow_mermaid(state)
    assert "%% Advisory" in result


def test_blocker_flow_no_blockers_graceful():
    from copy import deepcopy
    state = deepcopy(build_accord_projected_state())
    state.blockers.clear()
    result = build_blocker_flow_mermaid(state)
    assert "flowchart" in result
    assert "No blockers" in result


def test_blocker_flow_includes_classdefs():
    state = build_accord_projected_state()
    result = build_blocker_flow_mermaid(state)
    assert "classDef" in result


def test_blocker_flow_is_deterministic():
    r1 = build_blocker_flow_mermaid(build_accord_projected_state())
    r2 = build_blocker_flow_mermaid(build_accord_projected_state())
    assert r1 == r2


# ---------------------------------------------------------------------------
# build_zone_activation_mermaid
# ---------------------------------------------------------------------------

def test_zone_activation_returns_string():
    state = build_accord_projected_state()
    assert isinstance(build_zone_activation_mermaid(state), str)


def test_zone_activation_has_flowchart():
    state = build_accord_projected_state()
    assert "flowchart" in build_zone_activation_mermaid(state)


def test_zone_activation_has_advisory_comment():
    state = build_accord_projected_state()
    result = build_zone_activation_mermaid(state)
    assert "%% Advisory" in result


def test_zone_activation_no_zones_graceful():
    from copy import deepcopy
    state = deepcopy(build_accord_projected_state())
    state.zones.clear()
    result = build_zone_activation_mermaid(state)
    assert "flowchart" in result
    assert "No zones" in result


def test_zone_activation_includes_classdefs():
    state = build_accord_projected_state()
    result = build_zone_activation_mermaid(state)
    assert "classDef" in result


def test_zone_activation_is_deterministic():
    r1 = build_zone_activation_mermaid(build_accord_projected_state())
    r2 = build_zone_activation_mermaid(build_accord_projected_state())
    assert r1 == r2
