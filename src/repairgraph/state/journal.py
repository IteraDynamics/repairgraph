"""
Session event journal — file-based persistence for repair progress events.

Each vehicle repair session has an append-only event journal stored at:

    data/sessions/<oem_lower>/<year>_<model_slug>/events.json

Events recorded here are replayed over the initial RepairState (built by
initialize_repair_state) via project_repair_state whenever the review is
compiled, so the review always reflects where the repair currently stands.

No database — just a JSON file per session, matching the storage pattern
used by data/active_vehicle.json and data/normalized/.

All state derived from journaled events remains advisory. Recording an event
documents that a human performed or verified work; it does not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from repairgraph.state.schema import RepairEvent

_SESSIONS_DIR = Path("data/sessions")
_EVENTS_FILENAME = "events.json"


def _slug(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def session_dir(oem: str, year: int, model: str) -> Path:
    """Return the journal directory for a vehicle session."""
    return _SESSIONS_DIR / _slug(oem) / f"{year}_{_slug(model)}"


def _events_path(oem: str, year: int, model: str) -> Path:
    return session_dir(oem, year, model) / _EVENTS_FILENAME


def _event_from_dict(d: dict) -> RepairEvent:
    return RepairEvent(
        event_id=d["event_id"],
        timestamp=d["timestamp"],
        event_type=d["event_type"],
        actor=d["actor"],
        target_type=d["target_type"],
        target_id=d["target_id"],
        notes=d.get("notes"),
        evidence=d.get("evidence"),
    )


def load_session_events(oem: str, year: int, model: str) -> list[RepairEvent]:
    """Load all journaled events for a vehicle session, oldest first.

    Returns an empty list when no journal exists or the journal is unreadable —
    a missing or corrupt journal must never prevent the review from building
    (the review simply shows the initial, unstarted state).
    """
    path = _events_path(oem, year, model)
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [_event_from_dict(item) for item in raw]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


def append_session_events(
    oem: str,
    year: int,
    model: str,
    events: list[RepairEvent],
) -> Path:
    """Append events to the session journal, creating it if needed.

    Returns the journal path. The journal is an ordered JSON list; events
    are appended in the order given.
    """
    path = _events_path(oem, year, model)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = raw
        except (OSError, json.JSONDecodeError):
            existing = []

    existing.extend(asdict(event) for event in events)
    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def clear_session_events(oem: str, year: int, model: str) -> bool:
    """Remove the session journal, resetting the repair to its initial state.

    Returns True if a journal existed and was removed.
    """
    path = _events_path(oem, year, model)
    if path.exists():
        path.unlink()
        return True
    return False
