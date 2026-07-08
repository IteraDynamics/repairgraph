# Fleet Dashboard

The first surface built for a manager's question rather than a technician's:
not "what's next on this job" but "which jobs need attention right now."

```
GET /internal/fleet      — JSON summary across every tracked job
GET /internal/fleet/ui   — self-contained HTML dashboard
```

## What it aggregates

Every vehicle present in `data/normalized/` (fixture or intake-derived) is
projected the same way `/internal/review/progress` projects a single job:
initial state + replayed journal events (`data/sessions/`). The fleet view is
therefore never a separate source of truth — a job's bucket always matches
what its own review page shows, because both are derived from the same
projection.

Jobs are grouped into five buckets:

| Bucket | Meaning |
| --- | --- |
| `blocked` | session status is `blocked` |
| `in_progress` | some action or QA gate has moved off its initial state |
| `not_started` | initial projection — no events recorded |
| `ready` | session status is `complete` or `ready_for_review` |
| `cancelled` | session status is `cancelled` |

Each job card shows open QA gates, open blockers, action completion count,
the next recommended action, and links straight into that job's Repair
Review and Progress pages.

## Design note: why this belongs in the platform, not just collision repair

This is deliberately the least collision-specific surface in the codebase.
`build_fleet_summary()` (`state/fleet.py`) only reads `RepairState` —
`phases`, `actions`, `qa_gates`, `blockers` — the same generic vocabulary any
future domain adapter (aviation task cards, industrial maintenance work
orders) would populate. Nothing in the aggregation logic, the status
bucketing, or the HTML page assumes a vehicle, an OEM, or a repair.

"Job" is used throughout instead of "repair" or "vehicle" for the same
reason: swapping the collision adapter for an aviation or industrial one
later should not require touching this file. The fleet dashboard is the
first proof that the platform's value — turning many individual advisory
projections into one operational picture — is not tied to the collision
vertical.

## Scale note

No database — `build_fleet_summary()` scans `data/normalized/` and
recompiles each job's state on every request, the same file-based approach
used everywhere else in this codebase. This is intentionally fine for the
fleet sizes a single shop tracks. If fleet size ever makes per-request
recompilation costly, that is the trigger to add an index/cache — not
something to build preemptively.

All outputs are advisory workflow intelligence and require verification by a
qualified technician against each job's applicable OEM procedures.
