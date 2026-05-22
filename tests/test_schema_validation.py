import pytest
from repairgraph.validate import validate_repair_procedure, validate_vehicle_structure


def test_valid_repair_procedure_passes():
    validate_repair_procedure({
        "oem": "Honda",
        "year": 2025,
        "model": "CR-V",
        "operation": "rear_side_outer_panel_replacement",
        "operation_family": "quarter_panel",
    })


def test_valid_vehicle_structure_passes():
    validate_vehicle_structure({
        "oem": "Honda",
        "year": 2025,
        "model": "CR-V",
        "domain": "roof_and_side_panel_construction",
    })


def test_repair_procedure_missing_oem_fails():
    with pytest.raises(ValueError):
        validate_repair_procedure({
            "year": 2025,
            "model": "CR-V",
            "operation": "rear_side_outer_panel_replacement",
            "operation_family": "quarter_panel",
        })


def test_repair_procedure_missing_operation_fails():
    with pytest.raises(ValueError):
        validate_repair_procedure({
            "oem": "Honda",
            "year": 2025,
            "model": "CR-V",
            "operation_family": "quarter_panel",
        })


def test_vehicle_structure_missing_domain_fails():
    with pytest.raises(ValueError):
        validate_vehicle_structure({
            "oem": "Honda",
            "year": 2025,
            "model": "CR-V",
        })


def test_repair_procedure_wrong_year_type_fails():
    with pytest.raises(ValueError):
        validate_repair_procedure({
            "oem": "Honda",
            "year": "2025",  # should be integer
            "model": "CR-V",
            "operation": "rear_side_outer_panel_replacement",
            "operation_family": "quarter_panel",
        })


def test_vehicle_structure_wrong_year_type_fails():
    with pytest.raises(ValueError):
        validate_vehicle_structure({
            "oem": "Honda",
            "year": "2025",  # should be integer
            "model": "CR-V",
            "domain": "roof_and_side_panel_construction",
        })


def test_repair_procedure_with_full_data_passes():
    validate_repair_procedure({
        "oem": "Honda",
        "year": 2025,
        "model": "Accord",
        "operation": "rear_side_outer_panel_replacement",
        "operation_family": "quarter_panel",
        "joining_methods": ["spot_weld", "mig_brazing"],
        "dependencies": [
            {"type": "replace_component", "target": "wheel_arch_separator"}
        ],
        "repair_notes": ["Check body dimensions before final welding."],
    })
