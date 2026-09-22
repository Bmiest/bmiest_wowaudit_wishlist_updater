import copy
import dataclasses
import json
import logging
import re
from pathlib import Path

import pytest

from wishlist_updater.qe import (
    QEError,
    QESettings,
    check_saved_report,
    generate_upgrade_report,
    mplus_label_levels,
    parse_simc_identity,
)

FIXTURES = Path(__file__).parent / "fixtures"
ADDON_SIMC = (FIXTURES / "simc" / "shiftheal_addon.simc").read_text()
SAVED_REPORT = json.loads((FIXTURES / "qe" / "saved_report_payload.json").read_text())
# The settings the fixture report was generated with: Mythic, +10, 331.
REPORT_SETTINGS = {"qe_spec": "Holy Priest", "raid_index": 3, "mplus_index": 7, "crafted_index": 2}


def test_parse_simc_identity():
    identity = parse_simc_identity(ADDON_SIMC)
    assert identity.name == "Shiftheal"
    assert (identity.simc_class, identity.simc_spec) == ("priest", "holy")
    assert identity.qe_spec == "Holy Priest"
    assert "\r" not in identity.simc
    assert identity.simc.endswith("\n") and not identity.simc.endswith("\n\n")


def test_parse_simc_identity_normalizes_crlf_bom_and_leading_blank_lines():
    messy = "\ufeff\n  \n" + ADDON_SIMC.replace("\n", "\r\n")
    assert parse_simc_identity(messy) == parse_simc_identity(ADDON_SIMC)


def test_parse_simc_identity_requires_class_line_in_first_8_lines():
    padded = "\n".join(["# pad"] * 8 + ADDON_SIMC.split("\n")[1:])
    with pytest.raises(QEError, match="first 8 lines"):
        parse_simc_identity(padded)


def test_parse_simc_identity_rejects_non_healers():
    with pytest.raises(QEError, match="healer"):
        parse_simc_identity(ADDON_SIMC.replace("spec=holy", "spec=shadow"))


def test_parse_simc_identity_requires_spec():
    no_spec = "\n".join(line for line in ADDON_SIMC.split("\n") if not line.startswith("spec="))
    with pytest.raises(QEError, match="spec="):
        parse_simc_identity(no_spec)


def test_parse_simc_identity_rejects_1000_lines():
    with pytest.raises(QEError, match="1000"):
        parse_simc_identity(ADDON_SIMC + "# x\n" * 1000)


def test_parse_simc_identity_warns_without_name_header(caplog):
    headerless = "\n".join(line for line in ADDON_SIMC.split("\n") if not line.startswith("#"))
    with caplog.at_level(logging.WARNING):
        identity = parse_simc_identity(headerless)
    assert identity.name is None
    assert "header line" in caplog.text


@pytest.mark.parametrize(
    "label, levels",
    [
        ("M0", {0}),
        ("+2/3", {2, 3}),
        ("+4", {4}),
        ("+8/9", {8, 9}),
        ("+10", {10}),
        (" +7 ", {7}),
        ("LFR", set()),
        ("Mythic", set()),
    ],
)
def test_mplus_label_levels(label, levels):
    assert mplus_label_levels(label) == levels


def test_check_saved_report():
    assert check_saved_report(SAVED_REPORT, **REPORT_SETTINGS) == "hiswksqmzpbs"


@pytest.mark.parametrize(
    "path, value, error",
    [
        (["spec"], "Discipline Priest", "Discipline Priest report"),
        (["ufSettings", "raid"], [2], "expected"),
        (["ufSettings", "dungeon"], 6, "expected"),
        (["ufSettings", "craftedLevel"], 1, "expected"),
        (["results"], [], "no upgrade results"),
        (["id"], None, "unexpected id"),
        (["id"], "has space", "unexpected id"),
        (["id"], "", "unexpected id"),
    ],
)
def test_check_saved_report_rejects(path, value, error):
    payload = copy.deepcopy(SAVED_REPORT)
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(QEError, match=error):
        check_saved_report(payload, **REPORT_SETTINGS)


def test_qe_settings_defaults_are_the_users_settings():
    assert dataclasses.asdict(QESettings()) == {
        "raid_difficulty": "Mythic",
        "mplus_level": 10,
        "crafted_ilvl": 331,
        "catalyst_limit": 4,
        "show_percent_upgrade": True,
        "crafted_stats": None,
        "ally_buffs_scaling": 75,
        "cosmic_crescendo": 75,
        "volatile_void_suffuser": 85,
        "trappings_uptime": 60,
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        QESettings().mplus_level = 2  # type: ignore[misc]


async def _run_live(settings, artifacts_dir):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport={"width": 1600, "height": 1000})
            page = await context.new_page()
            return await generate_upgrade_report(
                page, ADDON_SIMC, settings, artifacts_dir=artifacts_dir
            )
        finally:
            await browser.close()


@pytest.mark.live
async def test_generate_upgrade_report_live(tmp_path):
    url = await _run_live(QESettings(), tmp_path)
    assert re.fullmatch(r"https://questionablyepic\.com/live/upgradereport/[a-z]{12}", url)
    assert not list(tmp_path.iterdir()), "no failure artifacts expected"


@pytest.mark.live
async def test_generate_upgrade_report_live_failure_saves_artifacts(tmp_path):
    with pytest.raises(QEError, match="applying Upgrade Finder settings.*No raid difficulty"):
        await _run_live(QESettings(raid_difficulty="Impossible"), tmp_path)
    assert sorted(path.suffix for path in tmp_path.iterdir()) == [".html", ".log", ".png"]
