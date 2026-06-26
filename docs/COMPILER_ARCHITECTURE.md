# RepairGraph Compiler Architecture

## Overview

The RepairGraph Compiler is the orchestration layer that transforms customer-supplied procedural documentation into a canonical `OperationalModel`. It sits at the boundary between domain-specific inputs and the platform's generic intelligence outputs.

```
                Domain Documents
                        │
                        ▼
              Domain Adapter
                        │
                        ▼
          RepairGraph Compiler
                        │
                        ▼
             OperationalModel
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
     Insights        Replay         Reports
        ▼               ▼               ▼
               Product Experience
```

---

## Compiler Responsibilities

The `RepairGraphCompiler` (`src/repairgraph/core/compiler.py`) orchestrates:

1. **Source manifest** — summarizes customer-supplied inputs without retaining them
2. **Domain context** — delegates to the domain adapter for domain-specific metadata
3. **Evidence** — extracts minimal explainable evidence from the compiled state
4. **Topology** — spatial and structural repair map (via existing topology builder)
5. **State** — current repair state (via existing state initializer and event replay)
6. **Workflow summary** — high-level workflow statistics and readiness
7. **Replay** — event history and state reconstruction (via existing replay engine)
8. **Insights** — prioritized operational findings (via existing insight engine)
9. **OperationalModel** — assembles all of the above into the canonical artifact

The compiler does **not** duplicate logic from existing modules. It calls them in sequence and assembles their outputs.

---

## OperationalModel Lifecycle

```
compile_demo(adapter)                compile_from_state(state, topology, adapter, ...)
       │                                            │
       ▼                                            ▼
load_procedure()                           (caller provides state)
build_topology_graph()                             │
build_accord_initial_state()                       │
build_accord_demo_events()                         │
build_accord_projected_state()                     │
       │                                            │
       └──────────────┬─────────────────────────────┘
                      ▼
            _build_source_manifest()
            adapter.build_domain_context()
            _build_evidence()
            _build_workflow_summary()
            _build_replay_summary()
            build_insight_payload()
                      │
                      ▼
              OperationalModel
```

### Entry Points

**`compile_demo(adapter)`** — Golden path. Uses Honda Accord demo fixtures. Used by the demo page, topology viewer, and all existing internal API endpoints.

**`compile_from_state(state, topology, adapter, ...)`** — Primary entry point for production integrations. Takes an already-computed `RepairState` (and optional topology, events, source paths) and produces the `OperationalModel`.

---

## Domain Adapters

Domain adapters implement the `DomainAdapter` protocol (`src/repairgraph/core/interfaces.py`). They are responsible for:

1. Identifying the domain (`domain` property)
2. Providing domain-specific context (`build_domain_context()`)
3. Supplying any source manifest defaults (`build_source_manifest_overrides()`)

Adapters do **not** contain compilation logic. They supply inputs to the compiler.

### CollisionDomainAdapter

`src/repairgraph/adapters/collision.py`

Translates collision repair concepts into generic compiler inputs:

| Collision Concept | Where It Lives |
|---|---|
| Vehicle (OEM, year, model, trim) | `DomainContext.context_data.vehicle` |
| Repair area / active zones | `DomainContext.context_data.repair` |
| Operation type | `DomainContext.context_data.repair.operation` |
| Calibration requirement | `DomainContext.context_data.calibration_required` |
| Corrosion protection | `DomainContext.context_data.corrosion_protection_required` |
| Material classifications | `DomainContext.context_data.material_classifications` |

These concepts do **not** appear in the core platform layer (`repairgraph.core`).

#### Usage

```python
from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler

adapter = CollisionDomainAdapter(
    oem="Honda",
    year=2025,
    model="Accord",
    operation="quarter_panel_replacement",
    calibration_required=True,
)

compiler = RepairGraphCompiler()
model = compiler.compile_demo(adapter=adapter)
```

#### From Existing RepairState

```python
adapter = CollisionDomainAdapter.from_repair_state(state)
```

This extracts vehicle metadata from the session and material context from zone activations.

---

## Future Verticals

The architecture is designed to make new domains additive. To support a new domain:

1. Create a new adapter in `src/repairgraph/adapters/<domain>.py`
2. Implement the `DomainAdapter` protocol
3. Pass the adapter to `RepairGraphCompiler.compile_from_state()` or `compile_demo()`

The core platform layer (`repairgraph.core`) requires no changes. The `OperationalModel` structure remains stable across domains.

Examples of future adapters:
- `AviationMaintenanceAdapter` — ATA chapter, task card, aircraft type
- `IndustrialServiceAdapter` — equipment model, service interval, component
- `MedicalEquipmentAdapter` — device type, regulatory standard, service procedure
- `EnergyInfrastructureAdapter` — asset class, inspection interval, regulatory regime

---

## Persistence Boundary

The `OperationalModel` is the RepairGraph durable artifact. Downstream consumers should persist:

- `OperationalModel` JSON
- `InsightPayload`
- `RepairState`
- Event ledger
- Report HTML
- Source manifest (filenames + hashes, not source document content)

RepairGraph does **not** need to persist the original source documents.

---

## Backward Compatibility

All existing APIs, demo flows, reports, and viewers continue to work unchanged. The `OperationalModel` layer is additive. Existing modules (`state`, `topology`, `insights`, `intake`, `replay`) are unchanged.

The demo orchestrator (`repairgraph.demo.orchestrator`) continues to work exactly as before. The compiler is a new entry point that produces the canonical artifact — it does not replace the orchestrator.
