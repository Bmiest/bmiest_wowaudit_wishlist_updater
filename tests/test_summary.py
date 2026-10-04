import json
from datetime import UTC, datetime
from pathlib import Path

from wishlist_updater import cli
from wishlist_updater.config import Character
from wishlist_updater.summary import build_summary, parse_gear

FIXTURES = Path(__file__).parent / "fixtures" / "simc"
ADDON = (FIXTURES / "shiftheal_addon.simc").read_text()
RAIDERIO = (FIXTURES / "shiftheal_raiderio.simc").read_text()
SHIFTHEAL = Character("Shiftheal", "ragnaros", "eu")


def test_parse_gear_from_generated_simc():
    gear = parse_gear(RAIDERIO)
    head = gear[0]
    assert head["slot"] == "head" and head["item_id"] == 271555
    assert head["name"] == "Cosmic Penitent's Truesight" and head["ilvl"] == 321
    assert head["enchant_id"] == 7961 and head["bonus_ids"][:2] == [12846, 13334]
    assert {g["slot"] for g in gear} >= {"neck", "main_hand", "off_hand", "trinket2"}


def test_parse_gear_ignores_bags_and_uses_comment_ilvl():
    gear = parse_gear(ADDON)
    slots = [g["slot"] for g in gear]
    assert len(slots) == len(set(slots))  # bag lines are commented out and skipped
    waist = next(g for g in gear if g["slot"] == "waist")
    assert waist["ilvl"] == 331 and waist["crafted_stats"] == [40, 36]


def test_build_summary_is_public_safe_and_grouped(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    outcomes = [
        cli.Outcome(
            SHIFTHEAL,
            "Heroic",
            report_url="https://questionablyepic.com/live/upgradereport/aaa",
            uploaded_via="login session",
            simc=ADDON,
        ),
        cli.Outcome(
            SHIFTHEAL,
            "Mythic",
            report_url="https://questionablyepic.com/live/upgradereport/bbb",
            error="WowAuditWebError: boom",
            simc=ADDON,
        ),
    ]
    s = build_summary(
        outcomes,
        started_at=datetime(2026, 9, 22, tzinfo=UTC),
        fetch_results=False,
    )
    assert s["run"]["url"] == "https://github.com/o/r/actions/runs/42"
    assert s["run"]["ok"] is False
    [char] = s["characters"]
    assert (char["class"], char["spec"]) == ("Priest", "Holy")
    assert [r["difficulty"] for r in char["reports"]] == ["Heroic", "Mythic"]
    assert char["reports"][0]["report_id"] == "aaa"
    assert s["raids"] == []  # no results fetched, so no raids for the boss tiles
    text = json.dumps(s)
    # the raw /simc export (bags, currencies) never goes to the public site
    assert "upgrade_currencies" not in text and "Gear from Bags" not in text


# --- crest planner ---------------------------------------------------------------

from wishlist_updater.config import Config  # noqa: E402
from wishlist_updater.summary import crest_upgrades  # noqa: E402

CURRENT = {
    "equippedItems": [
        {"id": 268218, "slot": "Feet", "level": 318, "upgradeTrack": "Myth", "upgradeRank": 1},
        {"id": 159288, "slot": "Back", "level": 311, "upgradeTrack": "Hero", "upgradeRank": 3},
        {"id": 999, "slot": "Wrist", "level": 300, "upgradeTrack": "Hero", "upgradeRank": 1},
        {"id": 271092, "slot": "1H Weapon", "level": 334, "upgradeTrack": "Myth", "upgradeRank": 6},
        {"id": 239649, "slot": "Waist", "level": 331, "upgradeTrack": "", "upgradeRank": 0},
    ],
    "results": [
        {"item": 268218, "level": 334, "dropType": "max", "percDiff": 0.674},
        {"item": 268218, "level": 334, "dropType": "bonus", "percDiff": 0.674},
        {"item": 268218, "level": 318, "dropType": "drop", "percDiff": 0},
        {"item": 159288, "level": 321, "dropType": "max", "percDiff": 0.283},
    ],
}
CAPPED = {
    "equippedItems": [
        {"id": 268218, "slot": "Feet", "level": 334},
        {"id": 159288, "slot": "Back", "level": 321},
        {"id": 999, "slot": "Wrist", "level": 321},
        {"id": 271092, "slot": "1H Weapon", "level": 334},
        {"id": 239649, "slot": "Waist", "level": 331},
    ]
}


def test_crest_upgrades_ranked_by_gain_with_unknowns_last():
    gear = [{"item_id": 268218, "name": "Nek'zali's Spiritwalkers"}]
    ups = crest_upgrades(CURRENT, CAPPED, gear)
    assert [u["item_id"] for u in ups] == [268218, 159288, 999]
    feet = ups[0]
    assert feet["name"] == "Nek'zali's Spiritwalkers"
    assert (feet["track"], feet["rank"], feet["level"], feet["max_level"]) == ("Myth", 1, 318, 334)
    assert feet["gain_pct"] == 0.674
    assert ups[2]["gain_pct"] is None  # no QE result at the cap level to estimate from


def test_crest_planner_outcome_is_report_only_and_separate(monkeypatch):
    calls = []

    async def generate(profile, qe_settings):
        calls.append((qe_settings["raid_difficulty"], qe_settings.get("upgrade_all_to_max")))
        return "https://questionablyepic.com/live/upgradereport/x" + str(len(calls))

    uploads = []

    async def upload(url, name):
        uploads.append(url)

    config = Config(
        characters=(SHIFTHEAL,),
        qe={"raid_difficulty": ["Heroic", "Mythic"], "upgrade_all_to_max": True},
        crest_planner=True,
    )
    import asyncio

    outcomes = asyncio.run(
        cli.process_character(
            SHIFTHEAL,
            config=config,
            secrets=cli.Secrets(wowaudit_api_key="k"),
            simc_override=ADDON,
            generate_report=generate,
            upload=upload,
            upload_method="API key",
        )
    )
    assert calls == [("Heroic", True), ("Mythic", True), ("Mythic", False)]
    assert len(uploads) == 2  # the crest report is never uploaded
    assert [o.kind for o in outcomes] == ["wishlist", "wishlist", "crest"]
    assert outcomes[-1].label.endswith("crest planner") and outcomes[-1].uploaded_via is None

    s = build_summary(
        outcomes,
        started_at=datetime(2026, 9, 22, tzinfo=UTC),
        fetch_results=False,
    )
    [char] = s["characters"]
    assert [r["difficulty"] for r in char["reports"]] == ["Heroic", "Mythic"]
    assert char["crest_report"]["report_id"] == "x3"


def test_crest_planner_failure_is_only_a_warning():
    async def generate(profile, qe_settings):
        if qe_settings.get("upgrade_all_to_max") is False:
            raise RuntimeError("QE hiccup")
        return "https://questionablyepic.com/live/upgradereport/ok"

    config = Config(characters=(SHIFTHEAL,), qe={"raid_difficulty": "Mythic"}, crest_planner=True)
    import asyncio

    outcomes = asyncio.run(
        cli.process_character(
            SHIFTHEAL,
            config=config,
            secrets=cli.Secrets(wowaudit_api_key=None),
            simc_override=ADDON,
            generate_report=generate,
            upload=None,
        )
    )
    assert [o.kind for o in outcomes] == ["wishlist"]
    assert outcomes[0].error is None
    assert any("Crest planner" in w for w in outcomes[0].warnings)


def test_upload_failure_marks_the_run_failed_without_saying_why():
    outcomes = [
        cli.Outcome(
            SHIFTHEAL,
            "Mythic",
            report_url="https://questionablyepic.com/live/upgradereport/bbb",
            upload_error="WowAuditWebError: Report items must contain vault sockets.",
            simc=ADDON,
        ),
    ]
    s = build_summary(outcomes, started_at=datetime(2026, 9, 24, tzinfo=UTC), fetch_results=False)
    assert s["run"]["ok"] is False
    [report] = s["characters"][0]["reports"]
    assert report["error"] is None and report["report_id"] == "bbb"  # the report itself is fine
    assert report["uploaded"] is False
    text = json.dumps(s).lower()
    assert "wowaudit" not in text and "socket" not in text
    for key in ("uploaded_via", "upload_error", "upload_skipped", "upload_method"):
        assert key not in text


def test_uploaded_flag_is_the_only_public_upload_detail():
    outcomes = [
        cli.Outcome(
            SHIFTHEAL,
            "Heroic",
            report_url="https://questionablyepic.com/live/upgradereport/h",
            dashboard_only=True,
            simc=ADDON,
        ),
        cli.Outcome(
            SHIFTHEAL,
            "Mythic",
            report_url="https://questionablyepic.com/live/upgradereport/m",
            uploaded_via="login session",
            simc=ADDON,
        ),
    ]
    s = build_summary(outcomes, started_at=datetime(2026, 9, 24, tzinfo=UTC), fetch_results=False)
    assert [(r["difficulty"], r["uploaded"]) for r in s["characters"][0]["reports"]] == [
        ("Heroic", False),
        ("Mythic", True),
    ]
    assert "login session" not in json.dumps(s)


def test_raid_night_is_published_and_optional():
    from wishlist_updater.config import RaidNight

    outcomes = [cli.Outcome(SHIFTHEAL, "Mythic", simc=ADDON)]
    started = datetime(2026, 9, 24, tzinfo=UTC)
    night = RaidNight(days=("Wednesday",), start="20:00", end="23:00", timezone="Europe/Brussels")
    s = build_summary(outcomes, started_at=started, fetch_results=False, raid_night=night)
    assert s["raid_night"] == {
        "days": ["Wednesday"],
        "start": "20:00",
        "end": "23:00",
        "timezone": "Europe/Brussels",
    }
    assert s["schema"] == 2 and s["raids"] == []
    assert build_summary(outcomes, started_at=started, fetch_results=False)["raid_night"] is None


def test_add_item_info_names_upgrades_gear_and_crests(monkeypatch):
    from wishlist_updater import summary
    from wishlist_updater.drop_sources import ItemInfo

    seen = {}

    def fake_fetch(item_ids, client, raid_item_ids=None):
        seen.update(item_ids=item_ids, raid_item_ids=raid_item_ids)
        return ItemInfo(
            sources={1: "Ula'tek", 2: "Altar of Fangs"},
            slots={1: "Head", 2: "Finger"},
            names={1: "Cowl", 2: "Ring", 10: "Old Cowl", 11: "Boots"},
            icons={1: "inv_helm_01", 10: "inv_helm_00", 11: "inv_boot_01"},
            raids=[{"id": 1320, "name": "The Venomous Abyss", "bosses": []}],
        )

    monkeypatch.setattr(summary, "fetch_item_info", fake_fetch)
    chars = [
        {
            "gear": [{"item_id": 10, "name": None}],
            "crest_upgrades": [{"item_id": 11, "name": "From simc"}],
            "reports": [{"results": [{"item": 1, "percDiff": 0.5}, {"item": 2, "percDiff": 0}]}],
        }
    ]
    raids = summary.add_item_info(chars, client=None)
    assert raids[0]["name"] == "The Venomous Abyss"
    assert seen == {"item_ids": {1, 2, 10, 11}, "raid_item_ids": {1, 2}}
    up, zero = chars[0]["reports"][0]["results"]
    assert (up["name"], up["icon"], up["dropSource"], up["slot"]) == (
        "Cowl",
        "inv_helm_01",
        "Ula'tek",
        "Head",
    )
    assert "name" not in zero and zero["dropSource"] == "Altar of Fangs"  # not an upgrade
    assert chars[0]["gear"][0] == {"item_id": 10, "name": "Old Cowl", "icon": "inv_helm_00"}
    assert chars[0]["crest_upgrades"][0]["name"] == "From simc"  # the export's name wins
