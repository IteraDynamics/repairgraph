# RepairGraph Vision

## One-Sentence Vision

RepairGraph is a machine-operable procedural intelligence layer for collision repair.

It transforms authorized OEM repair information from static human-readable procedures into structured, validated, graph-native repair intelligence that can power workflow systems, estimating intelligence, technician copilots, spatial overlays, and future wearable/AR repair guidance.

---

# What RepairGraph Is

RepairGraph is not primarily an app.

RepairGraph is not primarily a chatbot.

RepairGraph is not primarily an AR interface.

RepairGraph is a transformation and reasoning layer.

Its core function is to convert procedural collision repair information into a canonical intermediate representation that machines can query, validate, reason over, visualize, and eventually project into operational workflows.

In simple terms:

```text
OEM repair procedure
    ↓
RepairGraph compiler / normalization layer
    ↓
Machine-operable repair graph
    ↓
Applications, workflows, copilots, overlays, validation, and inference
```

The graph is the product foundation.

The applications are downstream expressions of that foundation.

---

# The Core Problem

Modern collision repair is becoming increasingly complex.

Repair decisions now depend on:

- vehicle-specific structural topology
- high-strength and ultra-high-strength material placement
- mixed joining methods
- OEM-specific weld semantics
- sectioning restrictions
- adhesive and sealer requirements
- corrosion protection requirements
- foam/acoustic separator restoration
- related component dependencies
- ADAS and calibration dependencies
- repair sequencing
- hidden structural relationships

Most of this information exists today as static documents.

Those documents are designed for human reading, not machine operation.

That creates several problems:

- procedures are difficult to query across vehicles and operations
- structural dependencies are visually buried in diagrams
- repair knowledge is fragmented across documents
- related operations are easy to miss
- estimating and supplement workflows depend heavily on human memory
- technicians must mentally translate diagrams into physical repair actions
- insurers, shops, and technicians lack a shared machine-readable representation of repair requirements

RepairGraph exists to solve the representation problem.

---

# The Representation Problem

The central RepairGraph thesis is that collision repair does not need another static document viewer.

It needs a canonical repair representation.

OEM procedures are source material.

RepairGraph is the intermediate representation.

Downstream systems should consume the RepairGraph representation rather than repeatedly reinterpreting raw PDFs, diagrams, and procedure text.

This is similar to a compiler architecture:

```text
Source language:       OEM repair procedures, diagrams, symbols, notes
Compiler:              extraction, ontology matching, normalization, validation
Intermediate form:     RepairGraph graph representation
Execution targets:     query tools, workflow systems, AR, QA, estimating, analytics
```

The strategic value is in the compiler and intermediate representation.

---

# What RepairGraph Is Not

RepairGraph is not a replacement for OEM repair subscriptions.

RepairGraph is not a system for bypassing paywalled OEM information.

RepairGraph is not intended to redistribute OEM procedures.

RepairGraph is not a generic document chatbot.

RepairGraph is not a generic RAG layer over PDFs.

RepairGraph is not merely an AI assistant that summarizes repair documents.

RepairGraph is not merely an AR overlay system.

Those may become interfaces or downstream products, but they are not the foundation.

The foundation is structured procedural repair intelligence.

---

# The Long-Term Product

The long-term product is a normalized repair intelligence graph.

This graph should represent, at minimum:

- structural components
- spatial repair zones
- material specifications
- tensile strength classifications
- zinc/coating information
- joining methods
- weld semantics
- sectioning locations
- replacement dependencies
- inspection dependencies
- corrosion protection requirements
- foam/sealer/adhesive requirements
- calibration dependencies
- sequencing relationships
- adjacent component relationships
- repair constraints

The goal is for repair procedures to become queryable and inferable.

Examples:

```text
Show every component that must be replaced during this operation.
Show all joining methods required by this procedure.
Show all corrosion protection steps tied to this repair.
Show all structure nodes adjacent to the quarter panel operation.
Show all procedures involving adhesive-type separators.
Show all Honda quarter-panel operations that reference rear pillar gutter inspection.
Show likely supplement items implied by this repair operation.
Show repair operations involving HSS or UHSS adjacency.
```

These questions are difficult to answer reliably from static documents alone.

They become natural once the data is represented as a graph.

---

# The RepairGraph Stack

## Layer 1 — Authorized Source Material

Inputs may include:

- OEM repair procedures
- weld symbol keys
- body construction diagrams
- material diagrams
- corrosion protection documents
- calibration procedures
- parts procedures
- position statements
- repair bulletins
- customer-provided repair documentation

This layer is raw source material.

It is not the moat by itself.

---

## Layer 2 — Extraction and Compiler Layer

This layer transforms source material into structured repair objects.

Responsibilities include:

- text extraction
- diagram-aware extraction where applicable
- controlled vocabulary matching
- canonical term resolution
- alias resolution
- typed dependency parsing
- joining method extraction
- material classification
- corrosion requirement extraction
- structural node detection
- sectioning reference detection
- validation against schemas

This is one of the most important layers in RepairGraph.

It is where raw procedure language becomes machine-operable repair intelligence.

---

## Layer 3 — Canonical Ontology

The ontology defines the language of RepairGraph.

Core concepts include:

- OEMStandard
- VehiclePlatform
- VehicleStructureNode
- MaterialSpec
- JoiningMethod
- RepairOperation
- SectioningLocation
- CorrosionRequirement
- CalibrationRequirement
- Dependency
- SpatialRelationship
- ProceduralRelationship

The ontology is not merely documentation.

It is the contract that keeps extraction, validation, graph export, query systems, and downstream applications aligned.

---

## Layer 4 — Repair Graph

The graph is the canonical machine-operable representation.

It should contain nodes such as:

- repair operations
- structure nodes
- joining methods
- materials
- corrosion requirements
- calibration procedures
- sectioning locations

And edges such as:

- REQUIRES_REPLACEMENT
- INSPECT_IF_DAMAGED
- USES_JOINING_METHOD
- REQUIRES_CORROSION_PROTECTION
- SECTIONS_AT
- ADJACENT_TO
- JOINS_TO
- USES_MATERIAL
- REQUIRES_CALIBRATION
- DEPENDS_ON

The graph is where repair information stops being static and becomes operational.

---

## Layer 5 — Query and Inference Layer

Once procedures are graph-native, RepairGraph can support higher-level reasoning.

Potential capabilities include:

- dependency expansion
- missing-operation detection
- procedure comparison
- supplement candidate inference
- repair complexity scoring
- material-risk surfacing
- calibration chain discovery
- corrosion requirement checks
- operation sequencing checks
- cross-model pattern analysis

This is where RepairGraph begins moving from retrieval to intelligence.

---

## Layer 6 — Applications and Interfaces

Applications are downstream consumers of the RepairGraph representation.

Possible applications include:

- technician copilots
- estimator copilots
- supplement review tools
- repair planning systems
- QA/validation systems
- training systems
- insurer-facing documentation tools
- OEM-aligned repair guidance tools
- spatial overlays
- wearable/AR guidance systems

These should be treated as interfaces, not the core substrate.

The long-term value depends on the intelligence layer underneath them.

---

# Why Graph-Native Repair Intelligence Matters

Static procedures answer narrow questions only if a human already knows where to look.

A graph can expose relationships that documents hide.

For example, a quarter-panel procedure may imply relationships among:

- rear side outer panel
- wheel arch separator
- rear pillar separator
- rear pillar gutter
- quarter pillar stiffener
- adhesive application
- sealer application
- urethane foam replacement
- spot welding
- MIG brazing
- material strength constraints

In a PDF, these are spread across notes, diagrams, symbols, callouts, and adjacent procedures.

In RepairGraph, they become connected operational facts.

That enables a system to reason about the repair as a structured workflow rather than a document lookup.

---

# The Moat

The expected moat is not the frontend.

The expected moat is not the first extraction script.

The expected moat is not an AR demo.

The expected moat is the accumulated procedural intelligence layer.

Potential moat sources include:

## 1. Canonical Repair Ontology

A durable representation of collision repair primitives, relationships, and constraints.

## 2. Procedure Normalization Engine

A system that can convert varied OEM repair language into stable machine-readable graph objects.

## 3. Alias and Identity Resolution

A canonicalization layer that prevents near-duplicate concepts from fragmenting the graph.

Example:

```text
rear wheel arch separator → wheel_arch_separator
```

## 4. Cross-Procedure Relationship Graph

Accumulated relationships across models, operations, OEMs, and repair families.

## 5. Operational Inference

The ability to infer related operations, hidden dependencies, likely supplement items, or validation requirements from structured repair context.

## 6. Execution Telemetry

If later deployed in real workflows, technician and estimator interactions could create a feedback layer showing which dependencies matter operationally, which items are missed, and where repairs become complex.

This telemetry would be extremely valuable, but it is downstream of the initial graph foundation.

---

# The Role of AR and Wearables

AR and wearables are not the core product.

They are powerful interface layers.

The reason they matter is that collision repair is physical, spatial, and procedural.

A future wearable or AR interface could use RepairGraph to:

- highlight cut zones
- display joining methods
- show hidden structural relationships
- indicate replacement dependencies
- surface corrosion protection requirements
- sequence technician tasks
- warn about material constraints
- project repair topology onto the physical vehicle

However, AR without the graph is a visualization gimmick.

RepairGraph without AR is still valuable.

The graph is the durable layer.

AR is one possible rendering target.

---

# The Role of AI

AI is useful, but AI is not the product by itself.

AI can assist with:

- extraction
- normalization
- diagram interpretation
- term matching
- relationship suggestion
- query interpretation
- workflow summarization
- inference over graph context

But RepairGraph should not depend on unstructured AI outputs as the source of truth.

The source of truth should be validated structured representations.

AI should accelerate the compiler and interface layers.

The graph should preserve discipline.

---

# Initial Wedge

The initial wedge is intentionally narrow:

- OEM: Honda
- Model year: 2025
- Repair family: rear side outer panel / quarter panel replacement
- Supporting documents: weld symbols, corrosion protection, roof and side panel construction diagrams

This narrow scope is deliberate.

The purpose is not to cover the entire industry immediately.

The purpose is to discover and validate the primitives required to represent collision repair procedures as graph-native operational intelligence.

If the ontology survives this narrow corpus, it can expand to:

- more Honda procedures
- more Honda model families
- additional operation classes
- additional OEMs
- calibration procedures
- estimating and supplement workflows
- spatial repair mapping

---

# Near-Term Success Criteria

RepairGraph is making progress if it can:

- normalize procedure text into structured draft objects
- extract typed dependencies
- canonicalize component identities
- export node-edge graphs
- visualize repair relationships
- validate normalized objects against schemas
- compare procedures across vehicles
- expose relationships that are hard to see in the source PDFs

Near-term success is not a polished app.

Near-term success is a coherent graph representation that becomes more useful as more procedures are added.

---

# Medium-Term Success Criteria

RepairGraph becomes materially more valuable when it can:

- normalize multiple procedures across multiple vehicles
- identify recurring repair motifs
- surface model-specific differences
- connect material diagrams to procedure requirements
- infer operation dependencies
- identify required corrosion and joining requirements
- generate useful visual dependency maps
- support structured queries across the corpus

At this stage, RepairGraph should begin to feel more useful than the original PDFs for certain classes of questions.

That is an important inflection point.

---

# Long-Term Success Criteria

RepairGraph reaches strategic significance if it becomes the intelligence substrate underneath collision repair workflows.

That means other systems could use RepairGraph to answer:

- what must be repaired?
- what must be removed?
- what must be replaced?
- what must be inspected?
- how must it be joined?
- where is sectioning allowed?
- what materials are involved?
- what protection must be restored?
- what dependencies are implied?
- what operations are likely missing?
- what should a technician see next?
- what should an estimator add?
- what should a QA reviewer verify?

At that point, RepairGraph is no longer merely a parser.

It becomes procedural infrastructure.

---

# Strategic North Star

The north star is this:

```text
Convert collision repair from document-driven interpretation
into graph-driven procedural intelligence.
```

That is the grand vision.

The first implementation may be small.

The first graph may only contain one Honda quarter-panel procedure.

The first visualization may be a Mermaid diagram.

But the direction is clear:

```text
static documents → structured graph → operational intelligence → spatial/workflow execution
```

RepairGraph should stay focused on owning the structured intelligence layer.

Everything else should serve that goal.
