# RepairGraph Roadmap

## Milestone 0.1 — Foundation

Goal: establish the initial RepairGraph ontology and repository structure.

Deliverables:
- product thesis
- data handling policy
- canonical schema v0
- JSON schemas for core entities
- normalized Honda seed examples

## Milestone 0.2 — Honda Seed Normalization

Goal: manually normalize a small Honda quarter-panel corpus.

Initial corpus:
- 2025 Accord rear side outer panel replacement
- 2025 Civic rear side outer panel replacement
- 2025 CR-V rear side outer panel replacement
- 2025 Odyssey rear side outer panel replacement
- 2025 Pilot rear side area outer panel replacement
- Honda weld symbols definition
- Honda corrosion protection information
- matching roof and side panel construction diagrams

Deliverables:
- Honda weld taxonomy JSON
- Honda corrosion taxonomy JSON
- one normalized procedure JSON per vehicle
- one normalized vehicle structure JSON per vehicle

## Milestone 0.3 — Query Prototype

Goal: provide a simple local query interface over normalized JSON.

Example questions:
- Which joining methods are required for this operation?
- Which related parts must be inspected or replaced?
- Which corrosion protection steps apply?
- Which construction materials are referenced?
- Which sectioning locations are described?

## Milestone 0.4 — Graph Model

Goal: convert normalized JSON into a graph-compatible representation.

Deliverables:
- nodes and edges export
- relationship taxonomy
- graph validation tests

## Milestone 0.5 — Spatial Annotation Prototype

Goal: create the first static image/photo overlay prototype.

This is not live AR yet. The objective is to validate whether structured procedure data can support spatial repair guidance.
