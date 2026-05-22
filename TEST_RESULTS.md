# RepairGraph — Test Results

**119 / 119 passed. 0 failures. 0 errors.**
Python 3.11.15 · pytest 9.0.3

---

## test_extractor.py — 5 / 5
Text extraction pipeline from raw OEM procedure text.

| Test | Result |
|---|---|
| Extract structure nodes (panel, separator, stiffener, etc.) | ✅ PASS |
| Extract joining methods (spot weld, MIG brazing, etc.) | ✅ PASS |
| Extract dependency phrases | ✅ PASS |
| Build complete draft object | ✅ PASS |
| Filter pronouns from typed dependency targets | ✅ PASS |

---

## test_graph_export.py — 6 / 6
Graph builder from extracted text.

| Test | Result |
|---|---|
| Graph contains nodes and edges | ✅ PASS |
| Graph contains replace_component edge | ✅ PASS |
| Graph contains operation node | ✅ PASS |
| Node IDs are canonical (underscored, not raw phrases) | ✅ PASS |
| Alias resolution collapses duplicate separator nodes | ✅ PASS |
| Graph contains joining method relationships | ✅ PASS |

---

## test_graph_from_normalized.py — 11 / 11
Graph builder from normalized JSON.

| Test | Result |
|---|---|
| Build graph from CR-V procedure | ✅ PASS |
| Graph contains operation node | ✅ PASS |
| Graph contains joining method edges | ✅ PASS |
| Graph contains corrosion protection edges | ✅ PASS |
| Graph contains sectioning edges | ✅ PASS |
| Graph contains material spec nodes when structure is provided | ✅ PASS |
| Graph meta contains model / OEM / year | ✅ PASS |
| Multi-vehicle graph builds from all 5 procedures | ✅ PASS |
| Multi-vehicle graph contains shares_component cross-vehicle edges | ✅ PASS |
| Multi-vehicle graph deduplicates shared nodes | ✅ PASS |

---

## test_mermaid_export.py — 2 / 2
Mermaid diagram export.

| Test | Result |
|---|---|
| Output contains graph TD header | ✅ PASS |
| Output contains relationship labels | ✅ PASS |

---

## test_query.py — 17 / 17
Query module: loaders and cross-vehicle analysis.

| Test | Result |
|---|---|
| Load all 5 procedures | ✅ PASS |
| Load all 5 vehicle structures | ✅ PASS |
| Load CR-V procedure by model | ✅ PASS |
| Load CR-V vehicle structure by model | ✅ PASS |
| Get joining methods from procedure | ✅ PASS |
| Get replacement dependencies | ✅ PASS |
| Get inspection dependencies | ✅ PASS |
| Get corrosion requirements | ✅ PASS |
| Get sectioning locations | ✅ PASS |
| Find procedures requiring MIG brazing | ✅ PASS |
| Find procedures requiring spot weld (≥3 models) | ✅ PASS |
| Find procedures referencing a specific component | ✅ PASS |
| Find procedures by corrosion requirement | ✅ PASS |
| Compare two procedures (shared vs. model-specific) | ✅ PASS |
| Get common components across all procedures | ✅ PASS |
| Get UHSS components from vehicle structure | ✅ PASS |

---

## test_inference.py — 26 / 26
Core inference: complexity scoring, material risk, supplement candidates, corpus motifs.

| Test | Result |
|---|---|
| Complexity score is positive | ✅ PASS |
| Complexity tier is valid (low / moderate / high / critical) | ✅ PASS |
| Complexity breakdown has all four sub-scores | ✅ PASS |
| Accord scores higher complexity than Civic | ✅ PASS |
| MIG brazing flagged for Accord | ✅ PASS |
| MIG brazing not flagged for Civic | ✅ PASS |
| Sectioning flagged for CR-V | ✅ PASS |
| UHSS flag only appears when structure is provided | ✅ PASS |
| Material risk returns non-empty list for Accord | ✅ PASS |
| UHSS component (rear_roof_rail_upper) flagged | ✅ PASS |
| UHSS count matches list length | ✅ PASS |
| MIG brazing gap flagged when UHSS present but absent from procedure | ✅ PASS |
| Zinc-plated components listed | ✅ PASS |
| Supplement candidates non-empty | ✅ PASS |
| Replacement parts appear as part candidates | ✅ PASS |
| Corrosion requirements become material + labor candidates | ✅ PASS |
| Sectioning produces labor candidate | ✅ PASS |
| MIG brazing labor inferred for Accord with UHSS structure | ✅ PASS |
| by_category covers all candidates exactly | ✅ PASS |
| Corpus size matches input | ✅ PASS |
| spot_weld is universal across all 5 procedures | ✅ PASS |
| sealer_application_required is universal | ✅ PASS |
| wheel_arch_separator is common (≥60% of procedures) | ✅ PASS |
| Odyssey has model-specific components | ✅ PASS |
| Common component frequency is between 0 and 1 | ✅ PASS |
| Empty corpus handled without error | ✅ PASS |

---

## test_missing_operations.py — 9 / 9
Missing operation detection via corpus comparison.

| Test | Result |
|---|---|
| Result has correct structure | ✅ PASS |
| total_gaps equals sum of all three gap lists | ✅ PASS |
| Empty corpus returns zero gaps | ✅ PASS |
| Missing component items have all required fields | ✅ PASS |
| High-confidence items have corpus frequency ≥ 80% | ✅ PASS |
| Pilot is missing at least one common replacement part | ✅ PASS |
| Missing joining methods only include universal ones | ✅ PASS |
| sealer not flagged when procedure already has it | ✅ PASS |
| Model label present in result | ✅ PASS |

---

## test_qa_checklist.py — 14 / 14
QA checklist generation.

| Test | Result |
|---|---|
| Result has correct structure | ✅ PASS |
| total_checks matches checks list length | ✅ PASS |
| Checks list is non-empty | ✅ PASS |
| by_priority covers all checks exactly | ✅ PASS |
| Accord with UHSS structure produces critical-priority checks | ✅ PASS |
| Civic without UHSS produces no critical checks | ✅ PASS |
| Joining compliance checks present | ✅ PASS |
| Component replacement checks present | ✅ PASS |
| Corrosion protection checks present | ✅ PASS |
| Dimensional verification check present | ✅ PASS |
| Corpus gaps add completeness checks | ✅ PASS |
| No completeness checks when corpus not provided | ✅ PASS |
| Every check has a pass_condition | ✅ PASS |
| Model metadata present in result | ✅ PASS |

---

## test_sequencing.py — 11 / 11
Phased operation sequence inference.

| Test | Result |
|---|---|
| Result has phases and total_phases | ✅ PASS |
| Model / OEM / year / operation present in result | ✅ PASS |
| Phase numbers are sequential (1, 2, 3…) | ✅ PASS |
| Inspection phase comes before replacement phase | ✅ PASS |
| Corrosion protection phase comes after joining phase | ✅ PASS |
| Joining phase present for all 5 models | ✅ PASS |
| Sectioning phase present for CR-V (has sectioning locations) | ✅ PASS |
| Sectioning phase absent for Pilot (no sectioning locations) | ✅ PASS |
| Verification phase present when repair notes exist | ✅ PASS |
| Every phase has at least one item | ✅ PASS |
| Accord joining phase contains mig_brazing and spot_weld | ✅ PASS |

---

## test_schema_validation.py — 8 / 8
JSON Schema validation using jsonschema against schemas/.

| Test | Result |
|---|---|
| Valid repair procedure passes validation | ✅ PASS |
| Valid vehicle structure passes validation | ✅ PASS |
| Procedure missing oem field fails | ✅ PASS |
| Procedure missing operation field fails | ✅ PASS |
| Structure missing domain field fails | ✅ PASS |
| Procedure with year as string (not integer) fails | ✅ PASS |
| Structure with year as string fails | ✅ PASS |
| Fully populated procedure with optional fields passes | ✅ PASS |

---

## test_validate_all_seed_data.py — 10 / 10
All 10 normalized seed data files validated against JSON Schemas.

| File | Result |
|---|---|
| data/normalized/honda/2025_accord/repair_procedure_quarter_panel.json | ✅ PASS |
| data/normalized/honda/2025_civic/repair_procedure_quarter_panel.json | ✅ PASS |
| data/normalized/honda/2025_crv/repair_procedure_quarter_panel.json | ✅ PASS |
| data/normalized/honda/2025_odyssey/repair_procedure_quarter_panel.json | ✅ PASS |
| data/normalized/honda/2025_pilot/repair_procedure_quarter_panel.json | ✅ PASS |
| data/normalized/honda/2025_accord/vehicle_structure.json | ✅ PASS |
| data/normalized/honda/2025_civic/vehicle_structure.json | ✅ PASS |
| data/normalized/honda/2025_crv/vehicle_structure.json | ✅ PASS |
| data/normalized/honda/2025_odyssey/vehicle_structure.json | ✅ PASS |
| data/normalized/honda/2025_pilot/vehicle_structure.json | ✅ PASS |

---

## test_validate_seed_data.py — 2 / 2
Original seed data validation.

| Test | Result |
|---|---|
| CR-V repair procedure | ✅ PASS |
| CR-V vehicle structure | ✅ PASS |

---

## Summary

| Test File | Tests | Passed | Failed |
|---|---|---|---|
| test_extractor.py | 5 | 5 | 0 |
| test_graph_export.py | 6 | 6 | 0 |
| test_graph_from_normalized.py | 11 | 11 | 0 |
| test_mermaid_export.py | 2 | 2 | 0 |
| test_query.py | 17 | 17 | 0 |
| test_inference.py | 26 | 26 | 0 |
| test_missing_operations.py | 9 | 9 | 0 |
| test_qa_checklist.py | 14 | 14 | 0 |
| test_sequencing.py | 11 | 11 | 0 |
| test_schema_validation.py | 8 | 8 | 0 |
| test_validate_all_seed_data.py | 10 | 10 | 0 |
| test_validate_seed_data.py | 2 | 2 | 0 |
| **Total** | **119** | **119** | **0** |
