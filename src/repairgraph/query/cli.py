import json
from pathlib import Path

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
    get_hss_components,
)
from repairgraph.query.cross_vehicle import (
    find_by_joining_method,
    find_by_component,
    find_by_corrosion_requirement,
    compare_procedures,
    get_common_components,
    procedures_requiring_uhss_handling,
)


def _proc_label(procedure: dict) -> str:
    return f"{procedure['year']} {procedure['oem']} {procedure['model']}"


def _print_section(title: str, items):
    print(f"\n{title}")
    print("-" * len(title))
    if not items:
        print("  (none)")
        return
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                print(f"  {json.dumps(item)}")
            else:
                print(f"  {item}")
    elif isinstance(items, dict):
        print(json.dumps(items, indent=2))


def run_single_procedure_queries(oem: str, year: int, model: str):
    procedure = load_procedure(oem, year, model)
    structure = load_vehicle_structure(oem, year, model)

    if not procedure:
        print(f"No procedure found for {year} {oem} {model}")
        return

    print(f"\n=== RepairGraph Query: {_proc_label(procedure)} ===")
    print(f"Operation: {procedure.get('operation', 'unknown')}")

    _print_section("Joining Methods Required", get_joining_methods(procedure))
    _print_section("Components to Replace", get_replacement_dependencies(procedure))
    _print_section("Components to Inspect if Damaged", get_inspection_dependencies(procedure))
    _print_section("Corrosion Protection Requirements", get_corrosion_requirements(procedure))
    _print_section("Sectioning Locations", get_sectioning_locations(procedure))

    if structure:
        _print_section("UHSS Components", [m["component"] for m in get_uhss_components(structure)])
        _print_section("HSS Components", [m["component"] for m in get_hss_components(structure)])


def run_corpus_queries():
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    print("\n=== RepairGraph Corpus Queries ===")
    print(f"Loaded {len(procedures)} procedures, {len(structures)} vehicle structures")

    print("\n--- Procedures requiring MIG brazing ---")
    for p in find_by_joining_method(procedures, "mig_brazing"):
        print(f"  {_proc_label(p)}")

    print("\n--- Procedures requiring urethane foam management ---")
    for p in find_by_corrosion_requirement(procedures, "urethane_foam_management_required"):
        print(f"  {_proc_label(p)}")

    print("\n--- Procedures requiring urethane foam replacement ---")
    for p in find_by_corrosion_requirement(procedures, "urethane_foam_replacement_required"):
        print(f"  {_proc_label(p)}")

    print("\n--- Procedures referencing wheel_arch_separator ---")
    for p in find_by_component(procedures, "wheel_arch_separator"):
        print(f"  {_proc_label(p)}")

    print("\n--- Common replacement components across all procedures ---")
    common = get_common_components(procedures)
    for c in common:
        print(f"  {c}")

    print("\n--- Procedures with UHSS components ---")
    for label in procedures_requiring_uhss_handling(procedures, structures):
        print(f"  {label}")


def main():
    run_single_procedure_queries("Honda", 2025, "CR-V")
    run_corpus_queries()


if __name__ == "__main__":
    main()
