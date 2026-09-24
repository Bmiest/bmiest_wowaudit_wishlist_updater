"""Remember what was last uploaded to WoWAudit, so unchanged reports aren't re-uploaded.

WoWAudit allows this automation for the user's own character on the condition that it
uploads less. A report is only uploaded when its inputs changed (the equipped gear,
talents and QE settings for that difficulty) or when the last upload is older than
`max_age_days` (QE's numbers move between patches), or when the user asks for it.

The state lives in data/upload-state.json on the public dashboard-data branch, so it
holds only fingerprints, public QE report ids and timestamps.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = 1

# Lines that describe the gear and build. Header comments (with the date) and item
# name comments don't change the report, so they don't count.
_RELEVANT_LINE_RE = re.compile(r"^(?:[a-z_]+=\"[^\"]*\"|(?:spec|talents|race)=.*|[a-z_0-9]+=,.*)$")


def fingerprint(simc_text: str, qe_settings: dict[str, object], difficulty: str) -> str:
    lines = sorted(
        line.strip() for line in simc_text.splitlines() if _RELEVANT_LINE_RE.match(line.strip())
    )
    payload = json.dumps(
        {"simc": lines, "qe": qe_settings, "difficulty": difficulty},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state(path: Path | None) -> dict:
    empty = {"schema": SCHEMA_VERSION, "characters": {}}
    if path is None or not path.exists():
        return empty
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(state, dict) or not isinstance(state.get("characters"), dict):
        return empty
    return state


def upload_decision(
    state: dict,
    character_key: str,
    difficulty: str,
    fp: str,
    *,
    now: datetime,
    max_age_days: float,
) -> str | None:
    """None when the report should be uploaded, else the reason to skip it."""
    last = state["characters"].get(character_key, {}).get(difficulty)
    if not last or last.get("fingerprint") != fp:
        return None
    try:
        uploaded = datetime.fromisoformat(last["uploaded_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if now - uploaded >= timedelta(days=max_age_days):
        return None
    return "Gear, talents and settings unchanged since the last upload"


def record_upload(
    state: dict, character_key: str, difficulty: str, fp: str, report_id: str, *, now: datetime
) -> None:
    state["characters"].setdefault(character_key, {})[difficulty] = {
        "fingerprint": fp,
        "report_id": report_id,
        "uploaded_at": now.astimezone(UTC).isoformat(timespec="seconds"),
    }


def last_uploaded_at(state: dict, character_key: str, difficulty: str) -> str | None:
    return state["characters"].get(character_key, {}).get(difficulty, {}).get("uploaded_at")


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def raid_day_decision(
    state: dict,
    character_key: str,
    difficulty: str,
    fp: str,
    *,
    now: datetime,
    upload_weekdays: tuple[int, ...],
) -> str | None:
    """Upload on raid days only (so the wishlist is fresh for the raid, and WoWAudit gets few
    uploads), and at most once per raid day unless the report's inputs changed.

    None = upload; otherwise the reason to skip. Days are UTC weekdays.
    """
    if now.weekday() not in upload_weekdays:
        days = " and ".join(WEEKDAYS[d].capitalize() for d in sorted(upload_weekdays))
        return f"Not a raid day (uploads happen on {days})"
    last = state["characters"].get(character_key, {}).get(difficulty)
    if last and last.get("fingerprint") == fp:
        try:
            uploaded = datetime.fromisoformat(last["uploaded_at"])
        except (KeyError, TypeError, ValueError):
            return None
        if uploaded.astimezone(UTC).date() == now.astimezone(UTC).date():
            return "Already uploaded today"
    return None
