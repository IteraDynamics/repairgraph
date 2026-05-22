# RepairGraph

RepairGraph is a procedural intelligence engine for collision repair.

It transforms customer-authorized OEM repair procedures, construction/material diagrams, weld specifications, and corrosion requirements into structured, machine-readable repair graphs — and then reasons over those graphs to produce actionable intelligence.

The goal is not to replace OEM procedures or redistribute OEM documentation. The goal is a structured intelligence layer that answers questions static documents cannot: what joining methods are required, which components are likely missing from an estimate, what material constraints govern a repair, and how procedures compare across vehicles.

## Current focus

RepairGraph v0.1 covers a narrow seed domain:

- OEM: Honda
- Model year: 2025
- Models: CR-V, Accord, Civic, Pilot, Odyssey
- Operation family: rear side outer panel / quarter panel replacement
- Supporting context: weld symbol definitions, corrosion protection, roof and side panel construction/material diagrams

## Architecture

```
OEM repair procedure
    ↓
Extraction + normalization (Layer 2)
    ↓
RepairGraph canonical JSON (Layer 3)
    ↓
Node/edge graph (Layer 4)
    ↓
Query + inference (Layer 5)
    ↓
Actionable repair intelligence
```

## Repository structure

```
src/repairgraph/
  extract/           # Text extraction pipeline (draft JSON from OEM text)
  graph/             # Graph builders and exporters
  query/             # Query and cross-vehicle analysis
  inference/         # Repair intelligence: complexity, risk, supplements, gaps
  taxonomy/          # Controlled vocabularies and canonical aliases
  validate.py        # Schema validation for normalized data

data/normalized/honda/
  2025_accord/       # Accord repair procedure and vehicle structure
  2025_civic/        # Civic repair procedure and vehicle structure
  2025_crv/          # CR-V repair procedure and vehicle structure
  2025_odyssey/      # Odyssey repair procedure and vehicle structure
  2025_pilot/        # Pilot repair procedure and vehicle structure
  corrosion_requirements.json
  joining_methods.json

schemas/             # JSON schemas for repair procedures and vehicle structures
docs/                # Vision, roadmap, compiler model, schema notes
tests/               # 119 tests covering all layers
```

## Milestones

### Milestone 0.1 — Foundation (complete)
- Canonical ontology for Honda quarter panel operations
- Extraction pipeline from raw OEM text
- Normalized JSON schemas for repair procedures and vehicle structures
- Graph export (JSON + Mermaid) from extracted text

### Milestone 0.2 — Seed data corpus (complete)
- Normalized repair procedures for 5 Honda models: CR-V, Accord, Civic, Pilot, Odyssey
- Vehicle structure data (materials, structure nodes) for all 5 models
- OEM taxonomy files: corrosion requirements, joining methods

### Milestone 0.3 — Query module (complete)
- Load procedures and structures by model or corpus-wide
- Query joining methods, dependencies, corrosion requirements, UHSS/HSS components
- Cross-vehicle search, procedure comparison, and common component analysis

### Milestone 0.4 — Graph model (complete)
- Graph builder from normalized JSON (single-vehicle and multi-vehicle)
- Multi-vehicle graph with `shares_component` cross-vehicle edges
- Mermaid diagram export for all models

### Milestone 0.5 — Inference layer (complete)
- **Repair complexity scoring** — tier a procedure (low/moderate/high/critical) with a weighted breakdown and risk flags
- **Material risk surfacing** — flag UHSS joining constraints, detect MIG brazing gaps adjacent to high-strength zones
- **Supplement candidate inference** — categorize likely parts, materials, and labor additions an estimator should include
- **Cross-model motif analysis** — identify universal, common, and model-specific components across the corpus
- **Missing operation detection** — compare a procedure against corpus patterns and flag components, joining methods, or corrosion requirements that appear in most procedures but are absent from this one
- **Procedure sequencing** — infer a phased operation order (inspection → sectioning → replacement → joining → corrosion protection → verification)
- **QA checklist generation** — produce a structured, prioritized checklist covering material compliance, joining verification, component replacement, corrosion protection, dimensional verification, and corpus-gap completeness checks
- **JSON Schema validation** — all normalized data validated against `schemas/` using `jsonschema`, with type checking (not just field presence)

## Installation

```bash
pip install -e .
```

## CLI commands

```bash
# Validate all normalized seed data
repairgraph-validate

# Query procedures (single vehicle + corpus-wide)
repairgraph-query

# Inference: complexity, risk, supplements, missing operations
repairgraph-infer

# Export graph JSON + Mermaid from normalized data
repairgraph-export-normalized-graph

# Export draft JSON from raw OEM text
repairgraph-export-draft

# Export graph JSON from draft (text-extracted)
repairgraph-export-graph
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Key capabilities

### Repair complexity scoring

```python
from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.inference.repair_complexity import score_repair_complexity

proc = load_procedure("Honda", 2025, "Accord")
structure = load_vehicle_structure("Honda", 2025, "Accord")
result = score_repair_complexity(proc, structure)
# result["tier"]       → "critical"
# result["score"]      → 21
# result["risk_flags"] → ["mig_brazing_required", "sectioning_required",
#                          "high_replacement_count", "uhss_material_present"]
```

### Material risk surfacing

```python
from repairgraph.inference.material_risk import surface_material_risks

result = surface_material_risks(proc, structure)
# result["material_risks"] → list of UHSS/HSS constraints with implications
# result["uhss_component_count"] → 2
# Flags gap if UHSS is present but MIG brazing is absent from the procedure
```

### Supplement candidate inference

```python
from repairgraph.inference.supplement_candidates import infer_supplement_candidates

result = infer_supplement_candidates(proc, structure)
# result["by_category"]["parts"]              → replacement part line items
# result["by_category"]["materials_and_labor"] → sealer, adhesive, foam
# result["by_category"]["labor"]              → sectioning, MIG brazing
```

### Missing operation detection

```python
from repairgraph.query.loader import load_all_procedures
from repairgraph.inference.missing_operations import detect_missing_operations

all_procedures = load_all_procedures()
corpus = [p for p in all_procedures if p["model"] != "Pilot"]
proc = load_procedure("Honda", 2025, "Pilot")
result = detect_missing_operations(proc, corpus)
# result["missing_components"]          → components common in corpus but absent here
# result["missing_joining_methods"]     → universal methods not in this procedure
# result["missing_corrosion_requirements"] → universal requirements not listed
```

### Cross-model motif analysis

```python
from repairgraph.inference.motifs import find_corpus_motifs

result = find_corpus_motifs(load_all_procedures())
# result["universal_joining_methods"]    → ["adhesive_bonding", "spot_weld"]
# result["universal_corrosion_requirements"] → ["sealer_application_required"]
# result["common_components"]            → components in ≥60% of procedures
# result["model_specific_components"]    → components unique to one model
```

### Operation sequencing

```python
from repairgraph.query.loader import load_procedure
from repairgraph.inference.sequencing import build_operation_sequence

proc = load_procedure("Honda", 2025, "CR-V")
result = build_operation_sequence(proc)
for phase in result["phases"]:
    print(f"{phase['phase']}. {phase['label']}")
# 1. Pre-Repair Inspection
# 2. Sectioning Preparation
# 3. Component Removal and Replacement
# 4. Panel Installation and Joining
# 5. Corrosion Protection
# 6. Post-Repair Verification
```

### QA checklist generation

```python
from repairgraph.inference.qa_checklist import generate_qa_checklist

proc = load_procedure("Honda", 2025, "Accord")
structure = load_vehicle_structure("Honda", 2025, "Accord")
corpus = [p for p in load_all_procedures() if p["model"] != "Accord"]
result = generate_qa_checklist(proc, structure, corpus)
# result["by_priority"]["critical"] → UHSS joining compliance checks
# result["by_priority"]["high"]     → replacement, corrosion, dimensional checks
# result["by_category"]["completeness"] → corpus-gap checks
```

### Cross-vehicle queries

```python
from repairgraph.query.loader import load_all_procedures, load_procedure
from repairgraph.query.cross_vehicle import find_by_joining_method, compare_procedures

procedures = load_all_procedures()
mig_models = find_by_joining_method(procedures, "mig_brazing")

crv = load_procedure("Honda", 2025, "CR-V")
accord = load_procedure("Honda", 2025, "Accord")
diff = compare_procedures(crv, accord)
# diff["joining_methods"]["only_second"] → ["mig_brazing", "mag_plug_weld"]
```

### Multi-vehicle graph

```python
from repairgraph.query.loader import load_all_procedures, load_all_vehicle_structures
from repairgraph.graph.build_from_normalized import build_multi_vehicle_graph

procedures = load_all_procedures()
structures = load_all_vehicle_structures()
structure_by_model = {s["model"]: s for s in structures}
pairs = [(proc, structure_by_model.get(proc["model"])) for proc in procedures]
graph = build_multi_vehicle_graph(pairs)
# graph["edges"] includes cross-vehicle "shares_component" relationships
```

## Material classification

Honda tensile strength classifications used in RepairGraph:

| Classification | Range |
|---|---|
| mild | below 340 MPa |
| HSS | 340–780 MPa |
| UHSS | 980 MPa and above |

UHSS components require special handling — spot welding is prohibited and MIG brazing is required at adjacent joins. The Accord's rear roof rail upper (1500 MPa) and quarter pillar stiffener (980 MPa) are key examples.

## What this is not

RepairGraph is not a PDF redistribution project, a generic document chatbot, or a replacement for OEM repair subscriptions. It is a transformation and reasoning layer for authorized repair information.
