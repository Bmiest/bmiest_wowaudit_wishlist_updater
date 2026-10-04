import json

import httpx

from wishlist_updater.drop_sources import (
    INSTANCE_DB_URL,
    ITEM_DB_URL,
    item_icons,
    item_names,
    item_slots,
    item_sources,
    parse_encounter_names,
    parse_raids,
)
from wishlist_updater.summary import add_item_info

# Trimmed from QE's src/Databases/InstanceDB.ts, keeping the shapes the parser relies on.
INSTANCE_DB = """
export const getSourceName = (instanceID: number, encounterID: number): string => {
  if (encounterID === 999) {
    return "Catalyst";
  }
};

export const instanceDB: Record<string | number, string> = {
  "-1": "Dungeons",
  "1320": "The Venomous Abyss",
};

export const retailInstanceDB: Record<string | number, any> = {
  // Venomous Abyss
  1320: {
    name: "Venomous Abyss",
    bossOrder: [2888, 2874, 2895],
    bosses: {
      2888: "Nek'zali",
      2874: "Entombed Sentinels",
      2895: "Ula'tek",
    },
  },
  1296: {
    name: "Liberation of Undermine",
    bossOrder: [2639, 999],
    bosses: {
      2639: "Vexie and the Geargrinders", // Vexie and the Geargrinders.
      999: "BoE Trash Drops & Catalyst",
    },
  },
  "-1": {
    Retail: {
      bossOrder: [],
      bossOrderMythicPlus: [1322, 1041], // Dungeon Order

      1322: "Altar of Fangs",
      1041: "Kings Rest",
    },
    Classic: {
      //# 316 = Scarlet Monastery
      bossOrder: [],
      246: "Scholomance",
    },
  },
};
"""

ITEM_DB = [
    {
        "id": 268265,
        "name": "Ula'tek's Venom Pendant",
        "icon": "INV_Jewelry_Necklace_01",
        "slot": "Neck",
        "sources": [{"instanceId": 1320, "encounterId": 2895}],
    },
    {
        "id": 158366,
        "name": "Lord Waycrest's Signet",
        "icon": "inv_ring_02",
        "slot": "Finger",
        "sources": [{"instanceId": -1, "encounterId": 1041}],
    },
    {"id": 271874, "name": "Venomkeeper's Horrific Cowl", "icon": "inv_helm_01", "slot": "Head"},
    {"id": 268218, "name": "Nek'zali's Spiritwalkers", "icon": "inv_boots_01", "slot": "Feet"},
    {"id": 250004, "name": "<b>Bad</b>", "icon": "../../evil.jpg?x=1"},  # unsafe icon
    {"id": 250000, "sources": [{"instanceId": -98, "encounterId": -98}]},  # Delves
    {"id": 250001, "sources": [{"instanceId": -4, "encounterId": 1}]},  # Crafted
    {
        "id": 250002,
        "sources": [
            {"instanceId": 1320, "encounterId": 2888},
            {"instanceId": 1320, "encounterId": 2874},
            {"instanceId": 1320, "encounterId": 2888},
        ],
    },
    {"id": 250003},  # no sources at all
]


def test_parse_encounter_names_reads_raid_bosses_and_retail_dungeons():
    names = parse_encounter_names(INSTANCE_DB)
    assert names[(1320, 2888)] == "Nek'zali"
    assert names[(1320, 2895)] == "Ula'tek"
    assert names[(1296, 2639)] == "Vexie and the Geargrinders"
    assert names[(-1, 1322)] == "Altar of Fangs"
    assert names[(-1, 1041)] == "Kings Rest"
    assert (-1, 246) not in names  # Classic dungeons are a different game
    assert (2888, 2874) not in names  # bossOrder arrays aren't names


def test_item_sources_names_raid_and_dungeon_items_only():
    names = parse_encounter_names(INSTANCE_DB)
    assert item_sources(ITEM_DB, names, {i["id"] for i in ITEM_DB}) == {
        268265: "Ula'tek",
        158366: "Kings Rest",
        250002: "Nek'zali / Entombed Sentinels",  # several bosses, each once
    }
    assert item_sources(ITEM_DB, names, {268265}) == {268265: "Ula'tek"}


def test_item_slots_only_for_the_asked_items_that_have_one():
    assert item_slots(ITEM_DB, {268265, 158366, 250000, 250003}) == {
        268265: "Neck",
        158366: "Finger",
    }
    assert item_slots(ITEM_DB, {158366}) == {158366: "Finger"}


def _characters():
    return [
        {
            "reports": [
                {
                    "results": [
                        {"item": 268265, "dropLoc": "Raid", "percDiff": 1.5},
                        {"item": 250000, "dropLoc": "Delves", "percDiff": 0.2},
                    ]
                },
                {"results": [{"item": 158366, "dropLoc": "Dungeon", "percDiff": 0.8}]},
            ]
        }
    ]


def test_add_item_info_tags_every_result():
    def handler(request):
        if str(request.url) == INSTANCE_DB_URL:
            return httpx.Response(200, text=INSTANCE_DB)
        if str(request.url) == ITEM_DB_URL:
            return httpx.Response(200, text=json.dumps(ITEM_DB))
        return httpx.Response(404)

    characters = _characters()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        add_item_info(characters, client)
    reports = characters[0]["reports"]
    assert [r["dropSource"] for r in reports[0]["results"]] == ["Ula'tek", None]
    assert [r["slot"] for r in reports[0]["results"]] == ["Neck", None]
    assert reports[1]["results"][0]["dropSource"] == "Kings Rest"
    assert reports[1]["results"][0]["slot"] == "Finger"


def test_add_item_info_leaves_names_and_slots_out_when_qe_is_unreachable():
    characters = _characters()
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        assert add_item_info(characters, client) == []
    results = [r for rep in characters[0]["reports"] for r in rep["results"]]
    assert [r["dropSource"] for r in results] == [None, None, None]
    assert [r["slot"] for r in results] == [None, None, None]
    assert [r["name"] for r in results] == [None, None, None]


def test_parse_raids_keeps_kill_order_and_full_names():
    raids = parse_raids(INSTANCE_DB)
    assert [r["id"] for r in raids] == [1320, 1296]  # file order; the "-1" dungeons aren't raids
    abyss = raids[0]
    assert abyss["name"] == "The Venomous Abyss"  # from the instanceDB table
    assert [b["name"] for b in abyss["bosses"]] == ["Nek'zali", "Entombed Sentinels", "Ula'tek"]
    assert [b["id"] for b in abyss["bosses"]] == [2888, 2874, 2895]
    assert raids[1]["name"] == "Liberation of Undermine"  # no instanceDB entry: QE's own name


def test_item_names_and_icons_only_safe_ones():
    ids = {i["id"] for i in ITEM_DB}
    names = item_names(ITEM_DB, ids)
    assert names[268265] == "Ula'tek's Venom Pendant"
    assert names[250004] == "<b>Bad</b>"  # only ever rendered as text by the dashboard
    icons = item_icons(ITEM_DB, ids)
    assert icons[268265] == "inv_jewelry_necklace_01"  # lower-cased for the CDN path
    assert 250004 not in icons  # not a plain icon name: left out
    assert item_names(ITEM_DB, {158366}) == {158366: "Lord Waycrest's Signet"}


def _handler(request):
    if str(request.url) == INSTANCE_DB_URL:
        return httpx.Response(200, text=INSTANCE_DB)
    if str(request.url) == ITEM_DB_URL:
        return httpx.Response(200, text=json.dumps(ITEM_DB))
    return httpx.Response(404)


def test_add_item_info_names_upgrades_gear_and_crests_and_returns_raids():
    characters = _characters()
    characters[0]["reports"][0]["results"].append(
        {"item": 158366, "dropLoc": "Dungeon", "percDiff": 0}  # not an upgrade: no name
    )
    characters[0]["gear"] = [
        {"slot": "head", "item_id": 271874, "name": None},
        {"slot": "neck", "item_id": 268265, "name": "Name from the /simc export"},
    ]
    characters[0]["crest_upgrades"] = [{"slot": "Feet", "item_id": 268218, "name": None}]
    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        raids = add_item_info(characters, client)
    first = characters[0]["reports"][0]["results"]
    assert first[0]["name"] == "Ula'tek's Venom Pendant"
    assert first[0]["icon"] == "inv_jewelry_necklace_01"
    assert (first[1]["name"], first[1]["icon"]) == (None, None)  # Delves item QE doesn't know
    assert "name" not in first[2] and "icon" not in first[2]
    head, neck = characters[0]["gear"]
    assert (head["name"], head["icon"]) == ("Venomkeeper's Horrific Cowl", "inv_helm_01")
    assert neck["name"] == "Name from the /simc export"  # the export's name wins
    assert characters[0]["crest_upgrades"][0]["name"] == "Nek'zali's Spiritwalkers"
    # Only the raid the results drop in, with every boss in kill order (not just the ones
    # that drop an upgrade), so the dashboard can show the whole raid night.
    assert [r["name"] for r in raids] == ["The Venomous Abyss"]
    assert [b["name"] for b in raids[0]["bosses"]] == ["Nek'zali", "Entombed Sentinels", "Ula'tek"]


def test_add_item_info_without_results_fetches_nothing():
    def boom(request):
        raise AssertionError("no request expected")

    characters = [{"reports": [], "gear": [{"slot": "head", "item_id": 1}]}]
    with httpx.Client(transport=httpx.MockTransport(boom)) as client:
        assert add_item_info(characters, client) == []
