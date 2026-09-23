import base64
import json
import re
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from wishlist_updater.config import Character
from wishlist_updater.simc_source import (
    HEALER_SPECS,
    SLOT_ORDER,
    BlizzardAPIError,
    RaiderIOError,
    build_simc,
    build_simc_from_raiderio,
    fetch_simc_from_blizzard,
    fetch_simc_from_raiderio,
    parse_simc_text,
)

FIXTURES = Path(__file__).parent / "fixtures" / "blizzard"
ADDON_SIMC = (Path(__file__).parent / "fixtures" / "simc" / "shiftheal_addon.simc").read_text()

ACTIVE_TALENTS = (
    "CEQAR03Gt7xPmcDNOjs2Zlb3yCDAAAAAAgZmxsMmZMzYYGYZmZmBAAAwYmlZwMzM2mxMDgZ"
    "KAmZDDhxsMAjBWMzMLAaGzMGDmBYmZAD"
)

_LINE0_RE = re.compile(
    r"^# (?P<name>.+?) - (?P<spec>.+?) - (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - "
    r"(?P<region>[A-Z]+)/(?P<realm>.+)$"
)
_COMPARE_KEYS = {"id", "enchant_id", "gem_id", "bonus_id", "crafted_stats"}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _parse_item_lines(text: str) -> dict[str, dict[str, str]]:
    """Pull slot -> {key: value} out of a SimC string, for the keys we can compare."""
    by_slot: dict[str, dict[str, str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=," not in line:
            continue
        slot, rest = line.split("=,", 1)
        if slot not in SLOT_ORDER:
            continue
        fields = {}
        for part in rest.split(","):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            if key in _COMPARE_KEYS:
                fields[key] = value
        by_slot[slot] = fields
    return by_slot


@pytest.fixture
def blizzard_json():
    return _load("summary.json"), _load("equipment.json"), _load("specializations.json")


@pytest.fixture
def profile(blizzard_json):
    summary, equipment, specializations = blizzard_json
    return build_simc(
        summary, equipment, specializations, region="eu", now=datetime(2026, 9, 22, 21, 27)
    )


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# -- build_simc: item fields match the real addon export -----------------------


def test_equipped_items_match_addon_export(profile):
    generated = _parse_item_lines(profile.text)
    expected = _parse_item_lines(ADDON_SIMC)

    assert set(generated) == set(SLOT_ORDER)
    for slot in SLOT_ORDER:
        assert generated[slot] == expected[slot], f"mismatch for slot {slot!r}"


# -- QE Live parser contract -----------------------------------------------------


def test_class_line_is_within_first_eight_lines(profile):
    lines = profile.text.splitlines()
    class_idx = lines.index(f'{profile.class_token}="{profile.name}"')
    assert class_idx < 8


def test_header_line_matches_qe_regex(profile):
    line0 = profile.text.splitlines()[0]
    m = _LINE0_RE.match(line0)
    assert m is not None
    assert line0.split("-")[0].replace("#", "").strip() == "Shiftheal"
    assert m.group("region") == "EU"
    assert m.group("realm") == "Ragnaros"


def test_talents_line_matches_active_loadout(profile):
    assert f"talents={ACTIVE_TALENTS}" in profile.text.splitlines()


def test_profile_identity_fields(profile):
    assert profile.name == "Shiftheal"
    assert profile.class_token == "priest"
    assert profile.spec_token == "holy"
    assert (profile.class_token, profile.spec_token) in HEALER_SPECS


def test_omits_talents_line_when_no_active_loadout(blizzard_json):
    summary, equipment, specializations = blizzard_json
    specializations = dict(specializations, specializations=[])
    profile = build_simc(summary, equipment, specializations, region="eu", now=datetime.now())
    assert not any(line.startswith("talents=") for line in profile.text.splitlines())


# -- parse_simc_text --------------------------------------------------------------


def test_parse_simc_text_reads_real_addon_export():
    profile = parse_simc_text(ADDON_SIMC)
    assert profile.name == "Shiftheal"
    assert profile.class_token == "priest"
    assert profile.spec_token == "holy"
    assert profile.text == ADDON_SIMC


@pytest.mark.parametrize("garbage", ["", "just some\nrandom text\n", "level=90\nspec=holy\n"])
def test_parse_simc_text_rejects_garbage(garbage):
    with pytest.raises(ValueError):
        parse_simc_text(garbage)


# -- fetch_simc_from_blizzard: OAuth + API plumbing -------------------------------


async def test_fetch_simc_from_blizzard_end_to_end(blizzard_json):
    summary, equipment, specializations = blizzard_json
    seen = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["requests"].append(request)
        if request.url.host == "oauth.battle.net":
            assert request.method == "POST"
            body = request.content.decode()
            assert "grant_type=client_credentials" in body
            assert request.headers["Authorization"].startswith("Basic ")
            expected = base64.b64encode(b"my-client-id:my-client-secret").decode()
            assert request.headers["Authorization"] == f"Basic {expected}"
            return httpx.Response(200, json={"access_token": "tok-abc123"})

        assert request.headers["Authorization"] == "Bearer tok-abc123"
        assert request.url.params["namespace"] == "profile-eu"
        assert request.url.params["locale"] == "en_US"
        path = request.url.path
        assert "/profile/wow/character/ragnaros/shiftheal" in path
        if path.endswith("/equipment"):
            return httpx.Response(200, json=equipment)
        if path.endswith("/specializations"):
            return httpx.Response(200, json=specializations)
        return httpx.Response(200, json=summary)

    character = Character(name="Shiftheal", realm="ragnaros", region="eu")
    async with _client(handler) as client:
        profile = await fetch_simc_from_blizzard(
            character,
            "my-client-id",
            "my-client-secret",
            client=client,
            now=datetime(2026, 9, 22, 21, 27),
        )

    assert profile.name == "Shiftheal"
    assert profile.class_token == "priest"
    assert profile.spec_token == "holy"
    hosts = {r.url.host for r in seen["requests"]}
    assert hosts == {"oauth.battle.net", "eu.api.blizzard.com"}


async def test_fetch_simc_from_blizzard_404_does_not_leak_secrets():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth.battle.net":
            return httpx.Response(200, json={"access_token": "tok-super-secret"})
        return httpx.Response(404, json={"code": 404, "detail": "Not Found"})

    character = Character(name="Ghost", realm="ragnaros", region="eu")
    async with _client(handler) as client:
        with pytest.raises(BlizzardAPIError) as exc_info:
            await fetch_simc_from_blizzard(
                character, "my-client-id", "my-client-secret", client=client
            )

    message = str(exc_info.value)
    assert "Ghost" in message
    assert "my-client-id" not in message
    assert "my-client-secret" not in message
    assert "tok-super-secret" not in message


def test_blizzard_sample_fixture_is_current():
    """tests/fixtures/simc/shiftheal_blizzard.simc is the QE-module test input; keep it in sync."""
    fixtures = Path(__file__).parent / "fixtures"
    summary, equipment, specs = (
        json.loads((fixtures / "blizzard" / n).read_text())
        for n in ("summary.json", "equipment.json", "specializations.json")
    )
    profile = build_simc(summary, equipment, specs, region="eu", now=datetime(2026, 9, 22, 21, 27))
    assert profile.text == (fixtures / "simc" / "shiftheal_blizzard.simc").read_text()


# --- Raider.io -------------------------------------------------------------------

RAIDERIO_JSON = json.loads(
    (Path(__file__).parent / "fixtures" / "raiderio" / "shiftheal.json").read_text()
)
SHIFTHEAL = Character("Shiftheal", "ragnaros", "eu")


def _raiderio_profile():
    return build_simc_from_raiderio(
        RAIDERIO_JSON, realm_slug="ragnaros", region="eu", now=datetime(2026, 9, 22, 21, 27)
    )


def test_raiderio_items_match_addon_export():
    """Real Raider.io data vs. the real in-game export taken the same day.

    Raider.io has no crafted stats (QE derives them from bonus IDs) and no tabard.
    """
    generated = _parse_item_lines(_raiderio_profile().text)
    expected = _parse_item_lines(ADDON_SIMC)
    for slot, fields in expected.items():
        if slot == "tabard":
            continue
        fields = {k: v for k, v in fields.items() if k != "crafted_stats"}
        assert generated[slot] == fields, slot


def test_raiderio_header_and_identity():
    profile = _raiderio_profile()
    lines = profile.text.splitlines()
    assert _LINE0_RE.match(lines[0]).group("name") == "Shiftheal"
    assert lines[0].split("-")[0].replace("#", "").strip() == "Shiftheal"
    class_idx = lines.index('priest="Shiftheal"')
    assert class_idx < 8
    assert "spec=holy" in lines[:10]
    assert not any(line.startswith("level=") for line in lines)
    assert f"talents={RAIDERIO_JSON['talentLoadout']['loadout_text']}" in lines
    identity = (profile.name, profile.class_token, profile.spec_token)
    assert identity == ("Shiftheal", "priest", "holy")
    assert ("priest", "holy") in HEALER_SPECS


async def test_fetch_simc_from_raiderio_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return httpx.Response(200, json=RAIDERIO_JSON)

    async with _client(handler) as client:
        profile = await fetch_simc_from_raiderio(SHIFTHEAL, api_key="rio-key", client=client)

    assert seen["url"].host == "raider.io"
    assert seen["url"].path == "/api/v1/characters/profile"
    assert dict(seen["url"].params) == {
        "region": "eu",
        "realm": "ragnaros",
        "name": "Shiftheal",
        "fields": "gear,talents",
        "access_key": "rio-key",
    }
    assert profile.name == "Shiftheal"


async def test_fetch_simc_from_raiderio_without_key_omits_access_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=RAIDERIO_JSON)

    async with _client(handler) as client:
        await fetch_simc_from_raiderio(SHIFTHEAL, client=client)
    assert "access_key" not in seen["params"]


async def test_fetch_simc_from_raiderio_not_found_does_not_leak_key():
    body = {
        "statusCode": 400,
        "error": "Bad Request",
        "message": "Could not find requested character",
    }

    async with _client(lambda r: httpx.Response(400, json=body)) as client:
        with pytest.raises(RaiderIOError) as exc:
            await fetch_simc_from_raiderio(SHIFTHEAL, api_key="rio-secret", client=client)
    assert "Could not find requested character" in str(exc.value)
    assert "rio-secret" not in str(exc.value)


async def test_fetch_simc_from_raiderio_network_error_does_not_leak_key():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"boom connecting to {request.url}")

    async with _client(handler) as client:
        with pytest.raises(RaiderIOError) as exc:
            await fetch_simc_from_raiderio(SHIFTHEAL, api_key="rio-secret", client=client)
    assert "rio-secret" not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.live
async def test_live_raiderio_shiftheal():
    profile = await fetch_simc_from_raiderio(SHIFTHEAL)
    assert profile.class_token == "priest"
    assert "main_hand=,id=" in profile.text


def test_raiderio_sample_fixture_is_current():
    """tests/fixtures/simc/shiftheal_raiderio.simc is the QE-module test input; keep it in sync."""
    expected = (Path(__file__).parent / "fixtures" / "simc" / "shiftheal_raiderio.simc").read_text()
    assert _raiderio_profile().text == expected


@pytest.mark.parametrize("drop_talents", [False, True])
@pytest.mark.parametrize("source", ["blizzard", "raiderio"])
def test_item_lines_start_at_or_after_line_8(source, drop_talents, blizzard_json):
    """QE's processAllLines() only parses item lines from index 8 onward."""
    now = datetime(2026, 9, 22, 21, 27)
    if source == "blizzard":
        summary, equipment, specs = blizzard_json
        if drop_talents:
            specs = {**specs, "active_specialization": {"id": -1}}
        text = build_simc(summary, equipment, specs, region="eu", now=now).text
    else:
        data = {**RAIDERIO_JSON, "talentLoadout": {}} if drop_talents else RAIDERIO_JSON
        text = build_simc_from_raiderio(data, realm_slug="ragnaros", region="eu", now=now).text
    lines = text.splitlines()
    first_item = next(i for i, line in enumerate(lines) if "=,id=" in line)
    assert first_item >= 8
    assert any(line.startswith("priest=") for line in lines[:8])


def test_raiderio_profile_carries_crawl_time():
    assert _raiderio_profile().gear_as_of == RAIDERIO_JSON["last_crawled_at"]
