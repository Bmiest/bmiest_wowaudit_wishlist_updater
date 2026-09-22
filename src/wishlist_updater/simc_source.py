"""Build a SimC profile string for a character from Raider.io or the Blizzard Profile API.

The output is meant to be pasted into QuestionablyEpic Live (QE), whose parser
(github.com/Voulk/QuestionablyEpic, src/General/Items/GearImport/SimCImportEngine.ts)
reads the player name off line 0 (`# Name - Spec - date - REGION/Realm`), requires
the `<class>="<name>"` line within the first 8 lines, and then splits each item
line on commas looking for `id=`, `enchant_id=`, `gem_id=`, `bonus_id=`,
`crafted_stats=`, and `ilevel=`.

Sources (equipped gear only -- no bags):
- Raider.io: https://raider.io/api/v1/characters/profile?fields=gear,talents. Public,
  no credentials needed (an optional access key raises the rate limit). Data is as
  fresh as Raider.io's last crawl of the character.
- Blizzard: https://oauth.battle.net/token (client-credentials) and
  https://{region}.api.blizzard.com/profile/wow/character/{realm}/{name}[...],
  namespace `profile-{region}`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .config import Character

TOKEN_URL = "https://oauth.battle.net/token"
RAIDERIO_PROFILE_URL = "https://raider.io/api/v1/characters/profile"

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

_RAIDERIO_SLOTS = {"mainhand": "main_hand", "offhand": "off_hand"}

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


class SimcSourceError(RuntimeError):
    pass


class BlizzardAPIError(SimcSourceError):
    pass


class RaiderIOError(SimcSourceError):
    pass


@dataclass(frozen=True)
class _GearItem:
    slot: str
    item_id: int
    name: str
    ilvl: int
    enchant_ids: list[int]
    gem_ids: list[int]
    bonus_ids: list[int]
    crafted_stats: list[int]


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


def _blizzard_gear(slot_token: str, item: dict) -> _GearItem:
    return _GearItem(
        slot=slot_token,
        item_id=item["item"]["id"],
        name=item.get("name", ""),
        ilvl=item["level"]["value"],
        enchant_ids=_enchant_ids(item.get("enchantments", [])),
        gem_ids=_gem_ids(item.get("sockets", [])),
        bonus_ids=item.get("bonus_list") or [],
        crafted_stats=_crafted_stat_ids(item.get("modified_crafting_stat", [])),
    )


def _item_lines(item: _GearItem) -> list[str]:
    parts = [f"{item.slot}=", f"id={item.item_id}"]
    for key, values in (
        ("enchant_id", item.enchant_ids),
        ("gem_id", item.gem_ids),
        ("bonus_id", item.bonus_ids),
        ("crafted_stats", item.crafted_stats),
    ):
        if values:
            parts.append(f"{key}={'/'.join(str(v) for v in values)}")
    parts.append(f"ilevel={item.ilvl}")
    return [f"# {item.name} ({item.ilvl})", ",".join(parts)]


def _render(
    *,
    name: str,
    class_name: str,
    spec_name: str,
    race_name: str,
    realm_name: str,
    realm_slug: str,
    region: str,
    level: int | None,
    talents: str | None,
    gear: dict[str, _GearItem],
    source: str,
    now: datetime,
) -> SimcProfile:
    class_token = _class_token(class_name)
    spec_token = _spec_token(spec_name)
    region = region.lower()

    lines = [
        f"# {name} - {spec_name} - {now.strftime('%Y-%m-%d %H:%M')} - "
        f"{region.upper()}/{realm_name}",
        f"# Generated by wishlist-updater from {source} (equipped gear only, no bags)",
        f'{class_token}="{name}"',
    ]
    if level is not None:
        lines.append(f"level={level}")
    lines += [
        f"race={_race_token(race_name)}",
        f"region={region}",
        f"server={_server_token(realm_slug)}",
        f"spec={spec_token}",
    ]
    if talents:
        lines.append(f"talents={talents}")
    lines.append("")

    for slot in SLOT_ORDER:
        if slot in gear:
            lines.extend(_item_lines(gear[slot]))

    return SimcProfile(
        text="\n".join(lines) + "\n", name=name, class_token=class_token, spec_token=spec_token
    )


def build_simc(
    summary: dict, equipment: dict, specializations: dict, *, region: str, now: datetime
) -> SimcProfile:
    """Pure function: Blizzard Profile API JSON -> SimC."""
    return _render(
        name=summary["name"],
        class_name=summary["character_class"]["name"],
        spec_name=summary["active_spec"]["name"],
        race_name=summary["race"]["name"],
        realm_name=summary["realm"]["name"],
        realm_slug=summary["realm"]["slug"],
        region=region,
        level=summary["level"],
        talents=_active_talent_code(specializations),
        gear={
            slot: _blizzard_gear(slot, item) for slot, item in _equipped_by_slot(equipment).items()
        },
        source="the Blizzard Profile API",
        now=now,
    )


def build_simc_from_raiderio(
    profile: dict, *, realm_slug: str, region: str, now: datetime
) -> SimcProfile:
    """Pure function: Raider.io character profile JSON (fields=gear,talents) -> SimC.

    Raider.io doesn't expose character level or crafted stats. QE doesn't need the
    level, and it derives crafted stats from the items' bonus IDs.
    """
    gear = {}
    for rio_slot, item in (profile.get("gear") or {}).get("items", {}).items():
        slot = _RAIDERIO_SLOTS.get(rio_slot, rio_slot)
        if slot not in SLOT_ORDER or not item:
            continue
        enchants = item.get("enchants") or ([item["enchant"]] if item.get("enchant") else [])
        gear[slot] = _GearItem(
            slot=slot,
            item_id=item["item_id"],
            name=item.get("name", ""),
            ilvl=item["item_level"],
            enchant_ids=list(enchants),
            gem_ids=[g for g in item.get("gems") or [] if g],
            bonus_ids=list(item.get("bonuses") or []),
            crafted_stats=[],
        )
    return _render(
        name=profile["name"],
        class_name=profile["class"],
        spec_name=profile["active_spec_name"],
        race_name=profile["race"],
        realm_name=profile["realm"],
        realm_slug=realm_slug,
        region=region,
        level=None,
        talents=(profile.get("talentLoadout") or {}).get("loadout_text"),
        gear=gear,
        source="Raider.io",
        now=now,
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


async def fetch_simc_from_raiderio(
    character: Character,
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> SimcProfile:
    now = now or datetime.now(UTC)
    params = {
        "region": character.region,
        "realm": character.realm,
        "name": character.name,
        "fields": "gear,talents",
    }
    if api_key:
        params["access_key"] = api_key

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        resp = await client.get(RAIDERIO_PROFILE_URL, params=params)
    except httpx.HTTPError as exc:
        # httpx error text can include the URL, which carries access_key; keep it out.
        raise RaiderIOError(
            f"Raider.io request failed for {character.label}: {type(exc).__name__}"
        ) from None
    finally:
        if owns_client:
            await client.aclose()

    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not resp.is_success:
        message = body.get("message") if isinstance(body, dict) else None
        raise RaiderIOError(
            f"Raider.io error for {character.label} (HTTP {resp.status_code})"
            + (f": {message}" if message else "")
        )
    if not (body.get("gear") or {}).get("items"):
        raise RaiderIOError(f"Raider.io has no gear for {character.label}")

    return build_simc_from_raiderio(
        body, realm_slug=character.realm, region=character.region, now=now
    )
