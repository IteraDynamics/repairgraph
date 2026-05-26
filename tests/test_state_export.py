import json

import pytest

from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.export_json import (
    ADVISORY_NOTE,
    GENERATED_BY,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    export_state_to_dict,
    export_state_to_json,
)
from repairgraph.state.initialize import initialize_repair_state


def _accord_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


def test_export_is_json_serializable():
    state = _accord_state()
    payload = export_state_to_dict(state)
    dumped = json.dumps(payload)
    assert dumped


def test_export_has_required_metadata():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["schema_name"] == SCHEMA_NAME
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["advisory"] is True
    assert payload["generated_by"] == GENERATED_BY


def test_export_schema_name_value():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["schema_name"] == "repairgraph.repair_state"


def test_export_schema_version_value():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["schema_version"] == "0.1"


def test_export_advisory_flag_is_true():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["advisory"] is True


def test_export_generated_by_value():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["generated_by"] == "repairgraph.state"


def test_export_contains_advisory_note():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert "advisory_note" in payload
    assert isinstance(payload["advisory_note"], str)
    assert len(payload["advisory_note"]) > 10


def test_export_preserves_all_state_sections():
    state = _accord_state()
    payload = export_state_to_dict(state)
    for key in (
        "session",
        "phases",
        "actions",
        "qa_gates",
        "zones",
        "blockers",
        "events",
        "next_recommended_actions",
        "interpretation_note",
    ):
        assert key in payload, f"Missing key: {key}"


def test_export_session_fields():
    state = _accord_state()
    payload = export_state_to_dict(state)
    session = payload["session"]
    assert session["oem"] == "Honda"
    assert session["year"] == 2025
    assert session["model"] == "Accord"
    assert session["status"] == "not_started"
    assert "session_id" in session
    assert "operation" in session


def test_export_phases_is_list_matching_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["phases"], list)
    assert len(payload["phases"]) == len(state.phases)


def test_export_actions_is_list_matching_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["actions"], list)
    assert len(payload["actions"]) == len(state.actions)


def test_export_qa_gates_is_list_matching_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["qa_gates"], list)
    assert len(payload["qa_gates"]) == len(state.qa_gates)


def test_export_zones_is_list_matching_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["zones"], list)
    assert len(payload["zones"]) == len(state.zones)


def test_export_blockers_is_list_matching_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["blockers"], list)
    assert len(payload["blockers"]) == len(state.blockers)


def test_export_events_empty_on_initial_state():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["events"] == []


def test_export_next_recommended_actions_list():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert isinstance(payload["next_recommended_actions"], list)
    assert payload["next_recommended_actions"] == state.next_recommended_actions


def test_export_interpretation_note_preserved():
    state = _accord_state()
    payload = export_state_to_dict(state)
    assert payload["interpretation_note"] == state.interpretation_note


def test_export_phase_fields():
    state = _accord_state()
    payload = export_state_to_dict(state)
    phase = payload["phases"][0]
    for key in ("phase", "name", "label", "status", "active_zones",
                "completed_actions", "pending_actions", "blocked_by"):
        assert key in phase, f"Missing phase field: {key}"


def test_export_action_fields():
    state = _accord_state()
    payload = export_state_to_dict(state)
    action = payload["actions"][0]
    for key in ("action_id", "phase", "action_type", "target", "status",
                "zone_refs", "requires_qa", "evidence"):
        assert key in action, f"Missing action field: {key}"


def test_export_qa_gate_fields():
    state = _accord_state()
    payload = export_state_to_dict(state)
    gate = payload["qa_gates"][0]
    for key in ("gate_id", "category", "priority", "status", "related_phase",
                "zone_refs", "check", "blocks_completion", "evidence"):
        assert key in gate, f"Missing qa_gate field: {key}"


def test_export_blocker_fields():
    state = _accord_state()
    payload = export_state_to_dict(state)
    blocker = payload["blockers"][0]
    for key in ("blocker_id", "type", "severity", "status", "blocks",
                "reason", "related_zones", "related_actions"):
        assert key in blocker, f"Missing blocker field: {key}"


def test_export_to_json_string_is_parseable():
    state = _accord_state()
    json_str = export_state_to_json(state)
    parsed = json.loads(json_str)
    assert parsed["schema_name"] == "repairgraph.repair_state"
    assert parsed["advisory"] is True


def test_export_to_json_default_indent():
    state = _accord_state()
    json_str = export_state_to_json(state)
    assert "\n" in json_str


def test_export_does_not_mutate_state():
    state = _accord_state()
    original_phase_count = len(state.phases)
    original_action_count = len(state.actions)
    export_state_to_dict(state)
    assert len(state.phases) == original_phase_count
    assert len(state.actions) == original_action_count
