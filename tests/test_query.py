import pytest
from repairgraph.query.loader import (
    load_all_procedures,
    load_all_vehicle_structures,
    load_procedure,
    load_vehicle_structure,
)
from repairgraph.query.query_procedures import (
    get_joining_methods,
    get_replacement_dependencies,
    get_inspection_dependencies,
    get_corrosion_requirements,
    get_sectioning_locations,
    get_uhss_components,
)
from repairgraph.query.cross_vehicle import (
    find_by_joining_method,
    find_by_component,
    find_by_corrosion_requirement,
    compare_procedures,
    get_common_components,
)


def test_load_all_procedures():
    procedures = load_all_procedures()
    assert len(procedures) >= 5
    for proc in procedures:
        assert "oem" in proc
        assert "model" in proc
        assert "operation_family" in proc


def test_load_all_vehicle_structures():
    structures = load_all_vehicle_structures()
    assert len(structures) >= 5
    for s in structures:
        assert "oem" in s
        assert "model" in s
        assert "domain" in s


def test_load_crv_procedure():
    proc = load_procedure("Honda", 2025, "CR-V")
    assert proc is not None
    assert proc["model"] == "CR-V"


def test_load_crv_vehicle_structure():
    structure = load_vehicle_structure("Honda", 2025, "CR-V")
    assert structure is not None
    assert structure["model"] == "CR-V"


def test_get_joining_methods():
    proc = load_procedure("Honda", 2025, "CR-V")
    methods = get_joining_methods(proc)
    assert "spot_weld" in methods
    assert isinstance(methods, list)


def test_get_replacement_dependencies():
    proc = load_procedure("Honda", 2025, "CR-V")
    replacements = get_replacement_dependencies(proc)
    assert len(replacements) > 0
    assert "rear_combination_adapter" in replacements


def test_get_inspection_dependencies():
    proc = load_procedure("Honda", 2025, "CR-V")
    inspections = get_inspection_dependencies(proc)
    assert "rear_pillar_lower_gutter" in inspections


def test_get_corrosion_requirements():
    proc = load_procedure("Honda", 2025, "CR-V")
    requirements = get_corrosion_requirements(proc)
    assert "sealer_application_required" in requirements


def test_get_sectioning_locations():
    proc = load_procedure("Honda", 2025, "CR-V")
    locations = get_sectioning_locations(proc)
    assert len(locations) >= 2
    zones = [loc["zone"] for loc in locations]
    assert "front_upper_edge" in zones


def test_find_by_joining_method_mig_brazing():
    procedures = load_all_procedures()
    results = find_by_joining_method(procedures, "mig_brazing")
    models = [p["model"] for p in results]
    assert "Accord" in models


def test_find_by_joining_method_spot_weld():
    procedures = load_all_procedures()
    results = find_by_joining_method(procedures, "spot_weld")
    assert len(results) >= 3


def test_find_by_component():
    procedures = load_all_procedures()
    results = find_by_component(procedures, "wheel_arch_separator")
    assert len(results) >= 2


def test_find_by_corrosion_requirement():
    procedures = load_all_procedures()
    results = find_by_corrosion_requirement(procedures, "sealer_application_required")
    assert len(results) >= 4


def test_compare_procedures():
    proc1 = load_procedure("Honda", 2025, "CR-V")
    proc2 = load_procedure("Honda", 2025, "Accord")
    comparison = compare_procedures(proc1, proc2)

    assert "labels" in comparison
    assert "joining_methods" in comparison
    assert "replacement_dependencies" in comparison
    assert "shared" in comparison["joining_methods"]
    assert "only_first" in comparison["joining_methods"]
    assert "only_second" in comparison["joining_methods"]

    assert "spot_weld" in comparison["joining_methods"]["shared"]
    assert "mig_brazing" in comparison["joining_methods"]["only_second"]


def test_common_components_across_procedures():
    procedures = load_all_procedures()
    common = get_common_components(procedures)
    assert isinstance(common, list)


def test_get_uhss_components():
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    uhss = get_uhss_components(structure)
    assert len(uhss) > 0
    components = [m["component"] for m in uhss]
    assert "rear_roof_rail_upper" in components
