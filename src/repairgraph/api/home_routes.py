"""
FastAPI router for the home page — GET / — the single entry point tying
together intake, review, progress, and fleet.

No prefix (unlike every other router, all under /internal) because this is
meant to be the first thing anyone hitting the server sees.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["home"])


@router.get("/", summary="Home — entry point", response_class=HTMLResponse)
def get_home() -> HTMLResponse:
    """Return the home page: upload -> review -> track progress -> fleet.

    Shows the currently active job (if any) and how many jobs are tracked,
    using the same vehicle_store / fleet_summary sources the rest of the
    product reads from — never a claim the rest of the app doesn't back up.
    """
    from repairgraph.core.vehicle_store import get_active_vehicle
    from repairgraph.review.home_page import build_home_page_html
    from repairgraph.state.fleet import build_fleet_summary

    active = get_active_vehicle()
    job_count = build_fleet_summary()["job_count"]
    html = build_home_page_html(active.to_dict() if active else None, job_count)
    return HTMLResponse(content=html, status_code=200)
