# RepairGraph

RepairGraph is an AI-native procedural intelligence engine for collision repair.

The project transforms customer-authorized OEM repair procedures, construction/material diagrams, weld specifications, corrosion requirements, and structural repair information into structured, machine-readable repair graphs.

The goal is not to replace OEM procedures or redistribute OEM repair documentation. The goal is to create a structured intelligence layer that can power contextual workflows, operational copilots, spatial overlays, QA checks, and future wearable/AR repair guidance.

## Current focus

RepairGraph v0.1 begins with a narrow seed domain:

- OEM: Honda
- Model year: 2025
- Models: CR-V, Accord, Civic, Pilot, Odyssey
- Operation family: rear side outer panel / quarter panel replacement
- Supporting context: weld symbol definitions, corrosion protection, roof and side panel construction/material diagrams

## Core concepts

RepairGraph models collision repair as relationships between:

- OEM standards
- vehicle structure nodes
- material specifications
- joining methods
- sectioning locations
- corrosion protection requirements
- replacement dependencies
- procedural sequences
- spatial repair zones

## Repository structure

```
src/repairgraph/
  extract/        # Text extraction pipeline (draft JSON from OEM text)
  graph/          # Graph builders and exporters
  query/          # Query and cross-vehicle analysis module
  taxonomy/       # Controlled vocabularies and canonical aliases
  validate.py     # JSON validation for normalized data

data/normalized/honda/
  2025_accord/    # Accord repair procedure and vehicle structure
  2025_civic/     # Civic repair procedure and vehicle structure
  2025_crv/       # CR-V repair procedure and vehicle structure
  2025_odyssey/   # Odyssey repair procedure and vehicle structure
  2025_pilot/     # Pilot repair procedure and vehicle structure
  corrosion_requirements.json
  joining_methods.json

schemas/          # JSON schemas for repair procedures and vehicle structures
tests/            # 51 tests covering extract, graph, query, and validation
```

## Milestones

### Milestone 0.1 — Foundation (complete)
- Defined canonical ontology for Honda quarter panel operations
- Created extraction pipeline from raw OEM text
- Established normalized JSON schema for repair procedures and vehicle structures
- Graph export (JSON + Mermaid) from extracted text

### Milestone 0.2 — Seed data corpus (complete)
- Normalized repair procedures for 5 Honda models: CR-V, Accord, Civic, Pilot, Odyssey
- Vehicle structure data (materials, structure nodes) for all 5 models
- OEM taxonomy files: corrosion requirements, joining methods

### Milestone 0.3 — Query module (complete)
- `repairgraph.query.loader` — load procedures and structures by model or corpus-wide
- `repairgraph.query.query_procedures` — query joining methods, dependencies, corrosion requirements, UHSS/HSS components
- `repairgraph.query.cross_vehicle` — cross-vehicle search, comparison, and common component analysis
- `repairgraph-query` CLI entry point

### Milestone 0.4 — Graph builder from normalized JSON (complete)
- `repairgraph.graph.build_from_normalized` — build single-vehicle and multi-vehicle graphs from normalized JSON
- `repairgraph.graph.export_normalized_graph` — export graph JSON and Mermaid for all models
- `repairgraph-export-normalized-graph` CLI entry point
- Multi-vehicle graph with `shares_component` cross-vehicle edges

## Installation

```bash
pip install -e .
```

## CLI commands

```bash
# Validate all normalized seed data
repairgraph-validate

# Query procedures (single vehicle + corpus queries)
repairgraph-query

# Export graph JSON from normalized data (all 5 models + multi-vehicle)
repairgraph-export-normalized-graph

# Export draft JSON from raw OEM text
repairgraph-export-draft

# Export graph JSON from draft (text-extracted)
repairgraph-export-graph

# Export Mermaid diagram from extracted graph
repairgraph-export-mermaid
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Key capabilities

### Cross-vehicle queries

```python
from repairgraph.query.loader import load_all_procedures
from repairgraph.query.cross_vehicle import find_by_joining_method, compare_procedures

procedures = load_all_procedures()

# Which models require MIG brazing?
mig_brazing_models = find_by_joining_method(procedures, "mig_brazing")

# Compare CR-V and Accord procedures
from repairgraph.query.loader import load_procedure
crv = load_procedure("Honda", 2025, "CR-V")
accord = load_procedure("Honda", 2025, "Accord")
comparison = compare_procedures(crv, accord)
```

### Graph building

```python
from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.graph.build_from_normalized import build_graph_from_normalized

proc = load_procedure("Honda", 2025, "Accord")
structure = load_vehicle_structure("Honda", 2025, "Accord")
graph = build_graph_from_normalized(proc, structure)
# graph["nodes"], graph["edges"], graph["meta"]
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
# graph includes cross-vehicle "shares_component" edges
```

## Material classification

Honda uses the following tensile strength classifications:
- **mild**: below 340 MPa
- **HSS**: 340–780 MPa
- **UHSS**: 980 MPa and above

UHSS components (980+ MPa) require special handling — MIG brazing is required at joins adjacent to UHSS zones. The Accord's rear roof rail upper (1500 MPa) is a key example.

## What this is not

RepairGraph is not a PDF redistribution project, a generic document chatbot, or a replacement for OEM repair subscriptions. It is a transformation and reasoning layer for authorized repair information.
