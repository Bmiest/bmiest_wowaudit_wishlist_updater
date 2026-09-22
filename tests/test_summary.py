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
        upload_method="login session",
        fetch_results=False,
    )
    assert s["run"]["url"] == "https://github.com/o/r/actions/runs/42"
    assert s["run"]["ok"] is False
    [char] = s["characters"]
    assert [r["difficulty"] for r in char["reports"]] == ["Heroic", "Mythic"]
    assert char["reports"][0]["report_id"] == "aaa"
    text = json.dumps(s)
    # the raw /simc export (bags, currencies) never goes to the public site
    assert "upgrade_currencies" not in text and "Gear from Bags" not in text
