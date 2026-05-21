# Extraction Limitations

## Current State

RepairGraph extraction is currently deterministic and ontology-guided.

The extraction pipeline currently relies on:

- controlled vocabularies
- phrase matching
- canonical node classes
- regex-based dependency extraction
- ontology normalization

This is intentional.

The current objective is not maximum automation.

The current objective is discovering stable procedural semantics.

---

# Current Limitations

## Structural Ambiguity

Some OEM phrases may represent:
- structure nodes
- operation descriptions
- spatial references
- repair constraints

depending on context.

---

## Relationship Ambiguity

The current extractor does not yet distinguish between:

- physical adjacency
- replacement dependency
- inspection dependency
- joining relationships
- calibration relationships

These relationship classes must eventually become explicitly typed.

---

## Spatial Semantics

The extractor currently lacks:

- coordinate systems
- dimensional references
- geometry normalization
- visual annotation support
- topology-aware spatial inference

---

## Procedure Sequencing

The extractor currently does not model:

- operation order
- prerequisite operations
- blocking operations
- repair flow branching

---

# Strategic Direction

The long-term goal is not fully autonomous extraction.

The long-term goal is compiler-assisted normalization into stable RepairGraph representations.
