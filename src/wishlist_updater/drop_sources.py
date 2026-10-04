"""Which raid boss or dungeon an item drops from, its slot, name and icon, and each raid's
kill order, for the dashboard.

QE's report results only say "Raid" or "Dungeon" and a difficulty. QE Live's public source
repo has the rest: ItemDB.json maps each item to its name, icon, slot and its
{instanceId, encounterId} sources, and InstanceDB.ts names them and lists each raid's bosses
in kill order (`bossOrder`). For raids the encounter is the boss; for Mythic+ (instance -1)
QE files the dungeons themselves as the encounters. QE adds a new tier there, so the dashboard
picks it up without changes here.

Everything here ends up on the public dashboard (as text, never markup).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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
# `1320: { name: "Venomous Abyss", bossOrder: [2888, 2874], bosses: {...} }`, in file order
_RAID_ORDER_RE = re.compile(
    r"(\d+)\s*:\s*\{\s*name\s*:\s*\"([^\"\\\n]{1,80})\"\s*,[^{}]*?"
    r"bossOrder\s*:\s*\[([^\]]*)\][^{}]*?bosses\s*:\s*\{([^{}]*)\}"
)
# `export const instanceDB: Record<string | number, string> = { "1320": "The Venomous Abyss", }`
_INSTANCE_NAMES_RE = re.compile(r"\binstanceDB\s*:[^=]*=\s*\{([^{}]*)\}")
_QUOTED_NAME_RE = re.compile(r"\"(-?\d+)\"\s*:\s*\"([^\"\\\n]{1,80})\"")
# An icon file name on Wowhead's/Blizzard's icon CDN ("inv_helm_cloth_raidpriest_d_01").
_ICON_RE = re.compile(r"^[a-z0-9_-]{1,80}$")


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


def parse_raids(instance_db: str) -> list[dict]:
    """Every raid in QE's InstanceDB.ts, in file order (newest tier first):
    [{"id": 1320, "name": "The Venomous Abyss", "bosses": [{"id": 2888, "name": "Nek'zali"}, ...]}]
    with the bosses in QE's `bossOrder` (kill order). The raid's full name comes from the
    `instanceDB` table when it has one ("The Venomous Abyss" rather than "Venomous Abyss")."""
    full_names = {}
    if m := _INSTANCE_NAMES_RE.search(instance_db):
        full_names = {int(i): name for i, name in _QUOTED_NAME_RE.findall(m[1])}
    raids = []
    for m in _RAID_ORDER_RE.finditer(instance_db):
        raid_id = int(m[1])
        names = {int(e): name for e, name in _NAME_RE.findall(m[4])}
        order = [int(e) for e in re.findall(r"\d+", m[3])]
        bosses = [{"id": e, "name": names[e]} for e in order if e in names]
        if bosses:
            raids.append({"id": raid_id, "name": full_names.get(raid_id, m[2]), "bosses": bosses})
    return raids


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


def item_slots(item_db: list[dict], item_ids: set[int]) -> dict[int, str]:
    """{item id: QE's slot name} ("Head", "Finger", "Trinket", "1H Weapon", "Offhand", ...)."""
    return {
        item["id"]: item["slot"]
        for item in item_db
        if item.get("id") in item_ids and isinstance(item.get("slot"), str)
    }


def item_names(item_db: list[dict], item_ids: set[int]) -> dict[int, str]:
    """{item id: English item name}. Game names are never translated on the dashboard."""
    return {
        item["id"]: item["name"].strip()
        for item in item_db
        if item.get("id") in item_ids
        and isinstance(item.get("name"), str)
        and 0 < len(item["name"].strip()) <= 120
    }


def item_icons(item_db: list[dict], item_ids: set[int]) -> dict[int, str]:
    """{item id: icon file name}, only names safe to put on the icon CDN's fixed path."""
    icons = {}
    for item in item_db:
        if item.get("id") in item_ids and isinstance(item.get("icon"), str):
            icon = item["icon"].strip().lower()
            if _ICON_RE.match(icon):
                icons[item["id"]] = icon
    return icons


def raids_for(item_db: list[dict], raids: list[dict], item_ids: set[int]) -> list[dict]:
    """The raids (from parse_raids) that any of these items drops in, in QE's order."""
    instances = {
        src.get("instanceId")
        for item in item_db
        if item.get("id") in item_ids
        for src in item.get("sources") or []
    }
    return [raid for raid in raids if raid["id"] in instances]


@dataclass(frozen=True)
class ItemInfo:
    sources: dict[int, str] = field(default_factory=dict)  # item id -> boss or dungeon
    slots: dict[int, str] = field(default_factory=dict)  # item id -> QE slot name
    names: dict[int, str] = field(default_factory=dict)  # item id -> item name
    icons: dict[int, str] = field(default_factory=dict)  # item id -> icon file name
    raids: list[dict] = field(default_factory=list)  # raids with their bosses in kill order


def fetch_item_info(
    item_ids: set[int], client: httpx.Client, raid_item_ids: set[int] | None = None
) -> ItemInfo:
    """Sources, slots, names and icons of `item_ids` from QE's databases, plus the raids that
    `raid_item_ids` (default: all of them) drop in (raises httpx.HTTPError / ValueError)."""
    if not item_ids:
        return ItemInfo()
    instance_db = client.get(INSTANCE_DB_URL)
    instance_db.raise_for_status()
    item_db = client.get(ITEM_DB_URL)
    item_db.raise_for_status()
    items = item_db.json()
    if not isinstance(items, list):
        raise ValueError("QE ItemDB.json is not a list")
    items = [i for i in items if isinstance(i, dict)]
    return ItemInfo(
        sources=item_sources(items, parse_encounter_names(instance_db.text), item_ids),
        slots=item_slots(items, item_ids),
        names=item_names(items, item_ids),
        icons=item_icons(items, item_ids),
        raids=raids_for(
            items,
            parse_raids(instance_db.text),
            item_ids if raid_item_ids is None else raid_item_ids,
        ),
    )
