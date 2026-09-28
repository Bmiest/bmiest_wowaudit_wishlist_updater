import json

import httpx

from wishlist_updater.drop_sources import (
    INSTANCE_DB_URL,
    ITEM_DB_URL,
    item_sources,
    parse_encounter_names,
)
from wishlist_updater.summary import add_drop_sources

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
    {"id": 268265, "sources": [{"instanceId": 1320, "encounterId": 2895}]},
    {"id": 158366, "sources": [{"instanceId": -1, "encounterId": 1041}]},
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


def test_add_drop_sources_tags_every_result():
    def handler(request):
        if str(request.url) == INSTANCE_DB_URL:
            return httpx.Response(200, text=INSTANCE_DB)
        if str(request.url) == ITEM_DB_URL:
            return httpx.Response(200, text=json.dumps(ITEM_DB))
        return httpx.Response(404)

    characters = _characters()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        add_drop_sources(characters, client)
    reports = characters[0]["reports"]
    assert [r["dropSource"] for r in reports[0]["results"]] == ["Ula'tek", None]
    assert reports[1]["results"][0]["dropSource"] == "Kings Rest"


def test_add_drop_sources_leaves_names_out_when_qe_is_unreachable():
    characters = _characters()
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        add_drop_sources(characters, client)
    results = [r for rep in characters[0]["reports"] for r in rep["results"]]
    assert [r["dropSource"] for r in results] == [None, None, None]
