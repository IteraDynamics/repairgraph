from repairgraph.query.loader import (
    load_all_procedures,
    load_procedure,
    load_vehicle_structure,
)
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.schema import RepairState


def test_initialize_repair_state_returns_repair_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = [p for p in load_all_procedures() if p["model"] != "Accord"]

    state = initialize_repair_state(procedure, structure, corpus)

    assert isinstance(state, RepairState)
    assert state.session.status == "not_started"
    assert state.session.oem == "Honda"
    assert state.session.year == 2025
    assert state.session.model == "Accord"
    assert state.session.operation == "rear_side_outer_panel_replacement"


def test_initialize_repair_state_creates_phases_from_sequence():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    phase_names = [phase.name for phase in state.phases]

    assert "pre_repair_inspection" in phase_names
    assert "sectioning_preparation" in phase_names
    assert "component_replacement" in phase_names
    assert all(phase.status == "not_started" for phase in state.phases)


def test_initialize_repair_state_creates_pending_actions():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    assert state.actions
    assert all(action.status == "pending" for action in state.actions)
    assert any(
        action.action_type == "replace_component"
        and action.target == "rear_combination_adapter"
        for action in state.actions
    )


def test_initialize_repair_state_maps_action_zone_refs_when_available():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    replacement_actions = [
        action for action in state.actions
        if action.action_type == "replace_component"
    ]

    assert any("rear_pillar_separator" in action.zone_refs for action in replacement_actions)


def test_initialize_repair_state_creates_qa_gates():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = [p for p in load_all_procedures() if p["model"] != "Accord"]

    state = initialize_repair_state(procedure, structure, corpus)

    assert state.qa_gates
    assert all(gate.status == "open" for gate in state.qa_gates)
    assert any(gate.blocks_completion for gate in state.qa_gates)


def test_initialize_repair_state_creates_zone_activations_from_topology():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    zone_ids = {zone.zone_id for zone in state.zones}

    assert "rear_side_outer_panel" in zone_ids
    assert "rear_pillar_separator" in zone_ids
    assert all(zone.status == "inactive" for zone in state.zones)


def test_initialize_repair_state_preserves_material_context_on_zones():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    material_by_zone = {
        zone.zone_id: zone.material_classification
        for zone in state.zones
    }

    assert material_by_zone["quarter_pillar_stiffener"] == "UHSS"
    assert material_by_zone["rear_roof_rail_upper"] == "UHSS"


def test_initialize_repair_state_creates_blockers_for_blocking_qa_gates():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = [p for p in load_all_procedures() if p["model"] != "Accord"]

    state = initialize_repair_state(procedure, structure, corpus)

    assert state.blockers
    assert all(blocker.status == "open" for blocker in state.blockers)
    assert all(blocker.type == "qa_gate" for blocker in state.blockers)
    assert any("session_completion" in blocker.blocks for blocker in state.blockers)


def test_initialize_repair_state_sets_next_recommended_actions_from_first_phase():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    assert state.next_recommended_actions == state.phases[0].pending_actions


def test_initialize_repair_state_has_no_events_initially():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    assert state.events == []


def test_initialize_repair_state_interpretation_note_is_advisory():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")

    state = initialize_repair_state(procedure, structure)

    assert "advisory workflow projection" in state.interpretation_note
    assert "does not certify repair completion" in state.interpretation_note


def test_initialize_repair_state_works_for_all_seed_models():
    procedures = load_all_procedures()

    for procedure in procedures:
        structure = load_vehicle_structure(
            procedure["oem"],
            procedure["year"],
            procedure["model"],
        )

        state = initialize_repair_state(procedure, structure)

        assert state.session.model == procedure["model"]
        assert state.phases
        assert state.actions
        assert state.zones
