import json

from repairgraph.query.loader import (
    load_all_procedures,
    load_all_vehicle_structures,
    load_procedure,
    load_vehicle_structure,
)
from repairgraph.inference.repair_complexity import score_repair_complexity
from repairgraph.inference.material_risk import surface_material_risks
from repairgraph.inference.supplement_candidates import infer_supplement_candidates
from repairgraph.inference.motifs import find_corpus_motifs
from repairgraph.inference.missing_operations import detect_missing_operations


def _section(title: str, content):
    print(f"\n{title}")
    print("-" * len(title))
    print(json.dumps(content, indent=2))


def run_single(oem: str, year: int, model: str):
    procedure = load_procedure(oem, year, model)
    structure = load_vehicle_structure(oem, year, model)

    if not procedure:
        print(f"No procedure found for {year} {oem} {model}")
        return

    label = f"{year} {oem} {model}"
    print(f"\n=== RepairGraph Inference: {label} ===")

    _section("Repair Complexity", score_repair_complexity(procedure, structure))

    if structure:
        _section("Material Risks", surface_material_risks(procedure, structure))

    _section("Supplement Candidates", infer_supplement_candidates(procedure, structure))

    all_procedures = load_all_procedures()
    corpus_without_self = [p for p in all_procedures if p.get("model") != procedure.get("model")]
    _section("Likely Missing Operations", detect_missing_operations(procedure, corpus_without_self))


def run_corpus():
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()
    structure_by_model = {s["model"]: s for s in structures}

    print(f"\n=== RepairGraph Corpus Inference ({len(procedures)} procedures) ===")

    print("\n--- Complexity Rankings ---")
    scores = [
        score_repair_complexity(p, structure_by_model.get(p["model"]))
        for p in procedures
    ]
    for s in sorted(scores, key=lambda x: -x["score"]):
        flags = ", ".join(s["risk_flags"]) or "none"
        print(f"  {s['year']} {s['oem']} {s['model']}: "
              f"score={s['score']}  tier={s['tier']}  flags=[{flags}]")

    motifs = find_corpus_motifs(procedures)

    print("\n--- Universal Components (in every procedure) ---")
    for c in motifs["universal_components"]:
        print(f"  {c}")

    print("\n--- Universal Joining Methods ---")
    for m in motifs["universal_joining_methods"]:
        print(f"  {m}")

    print("\n--- Universal Corrosion Requirements ---")
    for r in motifs["universal_corrosion_requirements"]:
        print(f"  {r}")

    print("\n--- Common Components (≥60% of procedures) ---")
    for item in motifs["common_components"]:
        models = ", ".join(item["models"])
        print(f"  {item['component']}: {item['frequency']:.0%}  [{models}]")

    print("\n--- Model-Specific Components ---")
    for item in motifs["model_specific_components"]:
        print(f"  {item['component']}: only in {item['model']}")


def main():
    run_single("Honda", 2025, "Accord")
    run_corpus()


if __name__ == "__main__":
    main()
