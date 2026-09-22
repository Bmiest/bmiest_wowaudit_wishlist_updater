"""Build a SimC profile string for a character from the Blizzard Profile API.

The output is meant to be pasted into QuestionablyEpic Live (QE), whose parser
(github.com/Voulk/QuestionablyEpic, src/General/Items/GearImport/SimCImportEngine.ts)
reads the player name off line 0 (`# Name - Spec - date - REGION/Realm`), requires
the `<class>="<name>"` line within the first 8 lines, and then splits each item
line on commas looking for `id=`, `enchant_id=`, `gem_id=`, `bonus_id=`,
`crafted_stats=`, and `ilevel=`.

API: https://oauth.battle.net/token (client-credentials) and
https://{region}.api.blizzard.com/profile/wow/character/{realm}/{name}[...],
namespace `profile-{region}`. Only equipped gear is used -- no bags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .config import Character

TOKEN_URL = "https://oauth.battle.net/token"

SLOT_ORDER = (
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "shirt",
    "tabard",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
)

_SLOT_TOKENS = {
    "HEAD": "head",
    "NECK": "neck",
    "SHOULDER": "shoulder",
    "BACK": "back",
    "CHEST": "chest",
    "SHIRT": "shirt",
    "TABARD": "tabard",
    "WRIST": "wrist",
    "HANDS": "hands",
    "WAIST": "waist",
    "LEGS": "legs",
    "FEET": "feet",
    "FINGER_1": "finger1",
    "FINGER_2": "finger2",
    "TRINKET_1": "trinket1",
    "TRINKET_2": "trinket2",
    "MAIN_HAND": "main_hand",
    "OFF_HAND": "off_hand",
}

# Fallback when modified_crafting_stat entries omit "id" and only give "type".
_CRAFTED_STAT_IDS = {
    "CRIT_RATING": 32,
    "HASTE_RATING": 36,
    "VERSATILITY": 40,
    "MASTERY_RATING": 49,
}

HEALER_SPECS: frozenset[tuple[str, str]] = frozenset(
    {
        ("priest", "holy"),
        ("priest", "discipline"),
        ("druid", "restoration"),
        ("shaman", "restoration"),
        ("paladin", "holy"),
        ("monk", "mistweaver"),
        ("evoker", "preservation"),
    }
)

_CLASS_LINE_RE = re.compile(r'^(\w+)="([^"]*)"$')


class BlizzardAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class SimcProfile:
    text: str
    name: str
    class_token: str
    spec_token: str


def _class_token(class_name: str) -> str:
    return class_name.lower().replace(" ", "")


def _spec_token(spec_name: str) -> str:
    return spec_name.lower().replace(" ", "_")


def _race_token(race_name: str) -> str:
    return race_name.lower().replace(" ", "_").replace("'", "")


def _server_token(realm_slug: str) -> str:
    return realm_slug.replace("-", "_")


def _enchant_ids(enchantments: list[dict]) -> list[int]:
    return [
        e["enchantment_id"]
        for e in enchantments
        if e.get("enchantment_slot", {}).get("type") == "PERMANENT"
    ]


def _gem_ids(sockets: list[dict]) -> list[int]:
    return [s["item"]["id"] for s in sockets if s.get("item", {}).get("id") is not None]


def _crafted_stat_ids(entries: list[dict]) -> list[int]:
    ids = []
    for entry in entries:
        stat_id = entry.get("id")
        if stat_id is None:
            stat_id = _CRAFTED_STAT_IDS.get(entry.get("type", ""))
        if stat_id is not None:
            ids.append(stat_id)
    return ids


def _equipped_by_slot(equipment: dict) -> dict[str, dict]:
    by_slot = {}
    for item in equipment.get("equipped_items", []):
        token = _SLOT_TOKENS.get(item.get("slot", {}).get("type"))
        if token:
            by_slot[token] = item
    return by_slot


def _active_talent_code(specializations: dict) -> str | None:
    active_id = specializations.get("active_specialization", {}).get("id")
    if active_id is None:
        return None
    for entry in specializations.get("specializations", []):
        if entry.get("specialization", {}).get("id") != active_id:
            continue
        for loadout in entry.get("loadouts", []):
            if loadout.get("is_active"):
                return loadout.get("talent_loadout_code")
    return None


def _item_lines(slot_token: str, item: dict) -> list[str]:
    ilvl = item["level"]["value"]
    parts = [f"{slot_token}=", f"id={item['item']['id']}"]

    enchant_ids = _enchant_ids(item.get("enchantments", []))
    if enchant_ids:
        parts.append(f"enchant_id={'/'.join(str(i) for i in enchant_ids)}")

    gem_ids = _gem_ids(item.get("sockets", []))
    if gem_ids:
        parts.append(f"gem_id={'/'.join(str(i) for i in gem_ids)}")

    bonus_ids = item.get("bonus_list") or []
    if bonus_ids:
        parts.append(f"bonus_id={'/'.join(str(i) for i in bonus_ids)}")

    crafted = _crafted_stat_ids(item.get("modified_crafting_stat", []))
    if crafted:
        parts.append(f"crafted_stats={'/'.join(str(i) for i in crafted)}")

    parts.append(f"ilevel={ilvl}")

    return [f"# {item.get('name', '')} ({ilvl})", ",".join(parts)]


def build_simc(
    summary: dict, equipment: dict, specializations: dict, *, region: str, now: datetime
) -> SimcProfile:
    """Pure function: Blizzard Profile API JSON -> SimC."""
    name = summary["name"]
    class_name = summary["character_class"]["name"]
    spec_name = summary["active_spec"]["name"]
    class_token = _class_token(class_name)
    spec_token = _spec_token(spec_name)
    region = region.lower()

    lines = [
        f"# {name} - {spec_name} - {now.strftime('%Y-%m-%d %H:%M')} - "
        f"{region.upper()}/{summary['realm']['name']}",
        "# Generated by wishlist-updater from the Blizzard Profile API "
        "(equipped gear only, no bags)",
        f'{class_token}="{name}"',
        f"level={summary['level']}",
        f"race={_race_token(summary['race']['name'])}",
        f"region={region}",
        f"server={_server_token(summary['realm']['slug'])}",
        f"spec={spec_token}",
    ]

    talent_code = _active_talent_code(specializations)
    if talent_code:
        lines.append(f"talents={talent_code}")

    lines.append("")

    by_slot = _equipped_by_slot(equipment)
    for slot in SLOT_ORDER:
        item = by_slot.get(slot)
        if item is not None:
            lines.extend(_item_lines(slot, item))

    return SimcProfile(
        text="\n".join(lines) + "\n", name=name, class_token=class_token, spec_token=spec_token
    )


def parse_simc_text(text: str) -> SimcProfile:
    """Wrap an existing SimC string, e.g. a real /simc addon export."""
    class_token = None
    name = None
    spec_token = None
    for line in text.splitlines():
        stripped = line.strip()
        if class_token is None and (m := _CLASS_LINE_RE.match(stripped)):
            class_token, name = m.group(1), m.group(2)
        elif stripped.startswith("spec="):
            spec_token = stripped.removeprefix("spec=").strip()

    if class_token is None or name is None:
        raise ValueError('SimC text has no `<class>="<name>"` line')
    if spec_token is None:
        raise ValueError("SimC text has no `spec=` line")

    return SimcProfile(text=text, name=name, class_token=class_token, spec_token=spec_token)


async def _get_access_token(client: httpx.AsyncClient, client_id: str, client_secret: str) -> str:
    try:
        resp = await client.post(
            TOKEN_URL, data={"grant_type": "client_credentials"}, auth=(client_id, client_secret)
        )
    except httpx.HTTPError as exc:
        # str(exc) never includes request headers, so the secret can't leak here.
        raise BlizzardAPIError(f"Blizzard token request failed: {exc}") from exc
    if not resp.is_success:
        raise BlizzardAPIError(f"Blizzard token request failed (HTTP {resp.status_code})")
    try:
        return resp.json()["access_token"]
    except (ValueError, KeyError) as exc:
        raise BlizzardAPIError("Blizzard token response missing access_token") from exc


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    headers: dict,
    character: Character,
    *,
    not_found_message: str | None = None,
) -> dict:
    try:
        resp = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise BlizzardAPIError(f"Blizzard API request failed for {character.label}: {exc}") from exc
    if resp.status_code == 404 and not_found_message:
        raise BlizzardAPIError(not_found_message)
    if not resp.is_success:
        raise BlizzardAPIError(
            f"Blizzard API error for {character.label} (HTTP {resp.status_code}): {url}"
        )
    return resp.json()


async def fetch_simc_from_blizzard(
    character: Character,
    client_id: str,
    client_secret: str,
    *,
    client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> SimcProfile:
    now = now or datetime.now(UTC)
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        token = await _get_access_token(client, client_id, client_secret)
        headers = {"Authorization": f"Bearer {token}"}
        params = {"namespace": f"profile-{character.region}", "locale": "en_US"}
        base = (
            f"https://{character.region}.api.blizzard.com/profile/wow/character/"
            f"{character.realm}/{character.name.lower()}"
        )

        summary = await _get_json(
            client,
            base,
            params,
            headers,
            character,
            not_found_message=f"Character not found or profile hidden: {character.label}",
        )
        equipment = await _get_json(client, f"{base}/equipment", params, headers, character)
        specializations = await _get_json(
            client, f"{base}/specializations", params, headers, character
        )
    finally:
        if owns_client:
            await client.aclose()

    return build_simc(summary, equipment, specializations, region=character.region, now=now)
