"""Machine-readable run summary, published to the GitHub Pages dashboard.

Everything in here ends up on a public website, so it only carries data that's public
anyway: equipped gear (Armory / Raider.io), QE report links and their results (QE's public
API) and run status. Never the WoWAudit session, wishlist contents or raw /simc exports
(those can include bags and currencies).
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from wishlist_updater.cli import Outcome

SCHEMA_VERSION = 1
QE_GET_REPORT_URL = "https://questionablyepic.com/api/getUpgradeReport.php"

_ITEM_LINE_RE = re.compile(r"^(?P<slot>[a-z_0-9]+)=,(?P<fields>.*)$")
_NAME_COMMENT_RE = re.compile(r"^# (?P<name>.+?) \((?P<ilvl>\d+)\)$")
_ID_LIST_KEYS = ("bonus_id", "gem_id", "crafted_stats")


def parse_gear(simc_text: str) -> list[dict]:
    """Equipped items from a SimC string (commented bag lines are ignored)."""
    gear = []
    pending_name: tuple[str, int] | None = None
    for raw in simc_text.splitlines():
        line = raw.strip()
        if m := _NAME_COMMENT_RE.match(line):
            pending_name = (m["name"], int(m["ilvl"]))
            continue
        m = _ITEM_LINE_RE.match(line)
        if not m:
            if line and not line.startswith("#"):
                pending_name = None
            continue
        fields = dict(f.split("=", 1) for f in m["fields"].split(",") if "=" in f)
        name, comment_ilvl = pending_name or (None, None)
        pending_name = None
        item = {
            "slot": m["slot"],
            "item_id": int(fields["id"]),
            "name": name,
            "ilvl": int(fields["ilevel"]) if "ilevel" in fields else comment_ilvl,
            "enchant_id": (
                int(fields["enchant_id"].split("/")[0]) if "enchant_id" in fields else None
            ),
        }
        for key in _ID_LIST_KEYS:
            item[key.replace("_id", "_ids")] = (
                [int(v) for v in fields[key].split("/") if v] if key in fields else []
            )
        gear.append(item)
    return gear


def fetch_report_results(report_id: str, client: httpx.Client) -> list[dict]:
    """QE's saved results for a report: only the columns the dashboard shows."""
    resp = client.get(QE_GET_REPORT_URL, params={"reportID": report_id})
    resp.raise_for_status()
    body = resp.json()
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict) or "results" not in body:
        return []
    keep = ("item", "level", "dropType", "dropLoc", "dropDifficulty", "percDiff", "score")
    return [{k: r.get(k) for k in keep} for r in body["results"]]


def _report_id(url: str | None) -> str | None:
    return url.rstrip("/").rsplit("/", 1)[-1] if url else None


def build_summary(
    outcomes: list[Outcome],
    *,
    started_at: datetime,
    upload_method: str | None,
    fetch_results: bool = True,
) -> dict:
    run_id = os.environ.get("GITHUB_RUN_ID")
    repo = os.environ.get("GITHUB_REPOSITORY")
    characters: dict[str, dict] = {}
    with httpx.Client(timeout=30) as client:
        for o in outcomes:
            c = characters.setdefault(
                o.character.label,
                {
                    "name": o.character.name,
                    "realm": o.character.realm,
                    "region": o.character.region,
                    "gear": parse_gear(o.simc) if o.simc else [],
                    "warnings": list(o.warnings),
                    "skipped": o.skipped,
                    "error": None if o.difficulty else o.error,
                    "reports": [],
                },
            )
            if not o.difficulty:
                continue
            report_id = _report_id(o.report_url)
            results: list[dict] = []
            if fetch_results and report_id:
                try:
                    results = fetch_report_results(report_id, client)
                except (httpx.HTTPError, ValueError):
                    results = []  # the dashboard still links to the report
            c["reports"].append(
                {
                    "difficulty": o.difficulty,
                    "report_id": report_id,
                    "report_url": o.report_url,
                    "uploaded_via": o.uploaded_via,
                    "error": o.error,
                    "results": results,
                }
            )
    return {
        "schema": SCHEMA_VERSION,
        "run": {
            "id": run_id,
            "url": f"https://github.com/{repo}/actions/runs/{run_id}" if run_id and repo else None,
            "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
            "commit": os.environ.get("GITHUB_SHA"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "upload_method": upload_method,
            "ok": not any(o.error for o in outcomes),
        },
        "characters": list(characters.values()),
    }


def write_summary(summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
