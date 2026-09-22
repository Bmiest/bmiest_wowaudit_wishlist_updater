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


def fetch_report(report_id: str, client: httpx.Client) -> dict:
    """A saved QE report as QE's public API returns it ({} if it has none)."""
    resp = client.get(QE_GET_REPORT_URL, params={"reportID": report_id})
    resp.raise_for_status()
    body = resp.json()
    if isinstance(body, str):
        body = json.loads(body)
    return body if isinstance(body, dict) and "results" in body else {}


def slim_results(report: dict) -> list[dict]:
    """Only the result columns the dashboard shows."""
    keep = ("item", "level", "dropType", "dropLoc", "dropDifficulty", "percDiff", "score")
    return [{k: r.get(k) for k in keep} for r in report.get("results") or []]


def crest_upgrades(current: dict, capped: dict, gear: list[dict]) -> list[dict]:
    """What upgrading each equipped item to its track's max would gain.

    `current` is a QE report with the equipped gear at its real level, `capped` one with
    "Upgrade ALL to Max Level" on (its equippedItems sit at each track's cap). QE scores
    candidates by item id and level, so the current report's result for *your own item* at
    the cap level is exactly the gain from spending crests on it.
    """
    names = {g["item_id"]: g.get("name") for g in gear}
    caps = {(i.get("id"), i.get("slot")): i.get("level") for i in capped.get("equippedItems") or []}
    by_item: dict[tuple[int, int], float] = {}
    for r in current.get("results") or []:
        key = (int(r["item"]), int(r["level"]))
        by_item[key] = max(by_item.get(key, float("-inf")), float(r.get("percDiff") or 0))

    upgrades = []
    for item in current.get("equippedItems") or []:
        level, cap = item.get("level"), caps.get((item.get("id"), item.get("slot")))
        if not level or not cap or cap <= level:
            continue
        gain = by_item.get((int(item["id"]), int(cap)))
        upgrades.append(
            {
                "slot": item.get("slot"),
                "item_id": item["id"],
                "name": names.get(item["id"]) or item.get("name") or None,
                "track": item.get("upgradeTrack") or None,
                "rank": item.get("upgradeRank"),
                "level": level,
                "max_level": cap,
                "gain_pct": gain,  # None: QE had no result to estimate it from
            }
        )
    upgrades.sort(key=lambda u: (u["gain_pct"] is None, -(u["gain_pct"] or 0)))
    return upgrades


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
    fetched: dict[str, dict] = {}  # report id -> full QE report (never published as-is)

    def report(client: httpx.Client, report_id: str | None) -> dict:
        if not (fetch_results and report_id):
            return {}
        if report_id not in fetched:
            try:
                fetched[report_id] = fetch_report(report_id, client)
            except (httpx.HTTPError, ValueError):
                fetched[report_id] = {}  # the dashboard still links to the report
        return fetched[report_id]

    with httpx.Client(timeout=30) as client:
        for o in outcomes:
            c = characters.setdefault(
                o.character.label,
                {
                    "name": o.character.name,
                    "realm": o.character.realm,
                    "region": o.character.region,
                    "gear": parse_gear(o.simc) if o.simc else [],
                    "warnings": [],
                    "skipped": o.skipped,
                    "error": None,
                    "reports": [],
                    "crest_report": None,
                    "crest_upgrades": None,
                },
            )
            c["warnings"] += [w for w in o.warnings if w not in c["warnings"]]
            if not o.difficulty:
                c["error"] = o.error
                continue
            report_id = _report_id(o.report_url)
            if o.kind == "crest":
                c["crest_report"] = {
                    "difficulty": o.difficulty,
                    "report_id": report_id,
                    "report_url": o.report_url,
                }
                # Caps come from the newest wishlist report (upgrade_all_to_max on).
                capped = next(
                    (r for r in reversed(c["reports"]) if r["report_id"] and not r["error"]), None
                )
                if capped and report(client, report_id):
                    c["crest_upgrades"] = crest_upgrades(
                        report(client, report_id), report(client, capped["report_id"]), c["gear"]
                    )
                continue
            c["reports"].append(
                {
                    "difficulty": o.difficulty,
                    "report_id": report_id,
                    "report_url": o.report_url,
                    "uploaded_via": o.uploaded_via,
                    "error": o.error,
                    "results": slim_results(report(client, report_id)),
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
