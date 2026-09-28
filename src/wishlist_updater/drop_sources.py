"""Which raid boss or dungeon an item drops from, for the dashboard's upgrade lists.

QE's report results only say "Raid" or "Dungeon" and a difficulty. QE Live's public source
repo has the rest: ItemDB.json maps each item to its {instanceId, encounterId} sources, and
InstanceDB.ts names them. For raids that's the boss; for Mythic+ (instance -1) QE files the
dungeons themselves as the encounters.

Everything here ends up on the public dashboard (as text, never markup).
"""

from __future__ import annotations

import re

import httpx

QE_DATABASES_URL = "https://raw.githubusercontent.com/Voulk/QuestionablyEpic/dev/src/Databases/"
ITEM_DB_URL = QE_DATABASES_URL + "ItemDB.json"
INSTANCE_DB_URL = QE_DATABASES_URL + "InstanceDB.ts"

DUNGEONS = -1  # QE's instance id for the Mythic+ pool

# `1320: { name: "Venomous Abyss", bossOrder: [...], bosses: { 2888: "Nek'zali", ... } }`
_RAID_RE = re.compile(r"(\d+)\s*:\s*\{\s*name\s*:\s*\"[^\"]*\"\s*,[^{}]*?bosses\s*:\s*\{([^{}]*)\}")
# `"-1": { Retail: { bossOrderMythicPlus: [...], 1322: "Altar of Fangs", ... } }`
_DUNGEONS_RE = re.compile(r"\bRetail\s*:\s*\{([^{}]*)\}")
_NAME_RE = re.compile(r"(-?\d+)\s*:\s*\"([^\"\\\n]{1,80})\"")


def parse_encounter_names(instance_db: str) -> dict[tuple[int, int], str]:
    """{(instanceId, encounterId): name} from QE's InstanceDB.ts."""
    names = {}
    for m in _RAID_RE.finditer(instance_db):
        for encounter, name in _NAME_RE.findall(m[2]):
            names[(int(m[1]), int(encounter))] = name
    if m := _DUNGEONS_RE.search(instance_db):
        for encounter, name in _NAME_RE.findall(m[1]):
            names[(DUNGEONS, int(encounter))] = name
    return names


def item_sources(
    item_db: list[dict], names: dict[tuple[int, int], str], item_ids: set[int]
) -> dict[int, str]:
    """{item id: "Boss" or "Boss A / Boss B"} for the items QE knows a named source for."""
    sources = {}
    for item in item_db:
        if item.get("id") not in item_ids:
            continue
        labels = []
        for src in item.get("sources") or []:
            name = names.get((src.get("instanceId"), src.get("encounterId")))
            if name and name not in labels:
                labels.append(name)
        if labels:
            sources[item["id"]] = " / ".join(labels)
    return sources


def fetch_drop_sources(item_ids: set[int], client: httpx.Client) -> dict[int, str]:
    """Look up the given items in QE's databases (raises httpx.HTTPError / ValueError)."""
    if not item_ids:
        return {}
    instance_db = client.get(INSTANCE_DB_URL)
    instance_db.raise_for_status()
    item_db = client.get(ITEM_DB_URL)
    item_db.raise_for_status()
    items = item_db.json()
    if not isinstance(items, list):
        raise ValueError("QE ItemDB.json is not a list")
    return item_sources(items, parse_encounter_names(instance_db.text), item_ids)
