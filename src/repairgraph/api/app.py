"""
RepairGraph internal FastAPI application.

Exposes state workflow and AR payload intelligence as local/internal demo
endpoints. No authentication, no persistence, no external network calls.

Advisory: All API outputs are workflow intelligence derived from RepairGraph
procedure data. They do not certify repair completion, OEM compliance, or
repair quality.
"""
from __future__ import annotations

from fastapi import FastAPI

from repairgraph.api.intake_routes import router as intake_router
from repairgraph.api.state_routes import router as state_router

app = FastAPI(
    title="RepairGraph Internal API",
    description=(
        "Internal demo endpoints for RepairGraph state workflow, AR payload, "
        "and OEM intake intelligence. Not a production API surface. "
        "No authentication required. All outputs are advisory."
    ),
    version="0.1.0",
)

app.include_router(state_router)
app.include_router(intake_router)
