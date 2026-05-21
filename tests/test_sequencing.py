from repairgraph.query.loader import load_procedure
from repairgraph.inference.sequencing import build_operation_sequence


def test_result_structure():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    assert "phases" in result
    assert "total_phases" in result
    assert result["total_phases"] == len(result["phases"])


def test_model_metadata_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    assert result["model"] == "CR-V"
    assert result["oem"] == "Honda"
    assert result["year"] == 2025
    assert result["operation"] == "rear_side_outer_panel_replacement"


def test_phase_numbers_are_sequential():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    numbers = [p["phase"] for p in result["phases"]]
    assert numbers == list(range(1, len(numbers) + 1))


def test_inspection_phase_before_replacement():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    names = [p["name"] for p in result["phases"]]
    assert "pre_repair_inspection" in names
    assert "component_replacement" in names
    insp_idx = names.index("pre_repair_inspection")
    repl_idx = names.index("component_replacement")
    assert insp_idx < repl_idx


def test_corrosion_phase_after_joining():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    names = [p["name"] for p in result["phases"]]
    assert "panel_installation_and_joining" in names
    assert "corrosion_protection" in names
    join_idx = names.index("panel_installation_and_joining")
    corr_idx = names.index("corrosion_protection")
    assert join_idx < corr_idx


def test_joining_phase_always_present():
    for model in ["CR-V", "Accord", "Civic", "Pilot", "Odyssey"]:
        proc = load_procedure("Honda", 2025, model)
        result = build_operation_sequence(proc)
        names = [p["name"] for p in result["phases"]]
        assert "panel_installation_and_joining" in names, f"Missing joining phase for {model}"


def test_sectioning_phase_present_when_applicable():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    names = [p["name"] for p in result["phases"]]
    assert "sectioning_preparation" in names


def test_sectioning_phase_absent_for_pilot():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = build_operation_sequence(proc)
    names = [p["name"] for p in result["phases"]]
    assert "sectioning_preparation" not in names


def test_verification_phase_present_when_notes_exist():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = build_operation_sequence(proc)
    names = [p["name"] for p in result["phases"]]
    assert "post_repair_verification" in names


def test_each_phase_has_items():
    proc = load_procedure("Honda", 2025, "Accord")
    result = build_operation_sequence(proc)
    for phase in result["phases"]:
        assert len(phase["items"]) > 0, f"Phase {phase['name']} has no items"


def test_joining_items_contain_methods():
    proc = load_procedure("Honda", 2025, "Accord")
    result = build_operation_sequence(proc)
    joining_phase = next(p for p in result["phases"] if p["name"] == "panel_installation_and_joining")
    methods = [item["method"] for item in joining_phase["items"]]
    assert "mig_brazing" in methods
    assert "spot_weld" in methods
