from pathlib import Path

import pytest

from wishlist_updater import cli
from wishlist_updater.config import Character, Config, ConfigError, Secrets

ADDON_SIMC = (Path(__file__).parent / "fixtures/simc/shiftheal_addon.simc").read_text()
REPORT_URL = "https://questionablyepic.com/live/upgradereport/abc123"

SHIFTHEAL = Character("Shiftheal", "ragnaros", "eu")
CONFIG = Config(characters=(SHIFTHEAL,), qe={"raid_difficulty": "Mythic"})
SECRETS = Secrets(wowaudit_api_key="k", blizzard_client_id=None, blizzard_client_secret=None)


async def fake_report(profile, qe_settings):
    assert profile.name == "Shiftheal"
    assert qe_settings == {"raid_difficulty": "Mythic"}
    return REPORT_URL


@pytest.fixture
def uploads(monkeypatch):
    calls = []

    async def fake_upload(report, api_key, *, character_name=None, **_):
        calls.append((report, api_key, character_name))
        return {"created": True}

    monkeypatch.setattr(cli, "upload_report", fake_upload)
    return calls


async def _process(
    simc=ADDON_SIMC, *, dry_run=False, generate=fake_report, secrets=SECRETS, config=CONFIG
):
    return await cli.process_character(
        SHIFTHEAL,
        config=config,
        secrets=secrets,
        simc_override=simc,
        generate_report=generate,
        dry_run=dry_run,
    )


async def test_happy_path_uploads_report(uploads):
    outcome = await _process()
    assert outcome.error is None
    assert outcome.uploaded
    assert outcome.report_url == REPORT_URL
    assert uploads == [(REPORT_URL, "k", "Shiftheal")]


async def test_dry_run_skips_upload(uploads):
    outcome = await _process(dry_run=True)
    assert outcome.report_url == REPORT_URL
    assert not outcome.uploaded
    assert uploads == []


async def test_non_healer_is_skipped(uploads):
    outcome = await _process(ADDON_SIMC.replace("spec=holy", "spec=shadow"))
    assert outcome.skipped and "healer" in outcome.skipped
    assert outcome.report_url is None
    assert uploads == []


async def test_simc_for_other_character_is_an_error(uploads):
    outcome = await _process(ADDON_SIMC.replace('priest="Shiftheal"', 'priest="Someoneelse"'))
    assert outcome.error and "Someoneelse" in outcome.error
    assert uploads == []


async def test_report_failure_is_captured_not_raised(uploads):
    async def boom(profile, qe_settings):
        raise RuntimeError("QE changed its UI")

    outcome = await _process(generate=boom)
    assert outcome.error == "RuntimeError: QE changed its UI"
    assert uploads == []


async def test_blizzard_source_requires_credentials(uploads):
    config = Config(characters=(SHIFTHEAL,), qe=CONFIG.qe, simc_source="blizzard")
    outcome = await _process(simc=None, config=config)
    assert outcome.error and "BLIZZARD_CLIENT_ID" in outcome.error


async def test_raiderio_is_the_default_source(uploads, monkeypatch):
    seen = {}

    async def fake_raiderio(character, *, api_key=None):
        seen["args"] = (character, api_key)
        return cli.parse_simc_text(ADDON_SIMC)

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)
    secrets = Secrets(wowaudit_api_key="k", raiderio_api_key="rio")
    outcome = await _process(simc=None, secrets=secrets)
    assert outcome.uploaded
    assert seen["args"] == (SHIFTHEAL, "rio")


def test_select_characters():
    assert cli.select_characters(CONFIG, None) == (SHIFTHEAL,)
    assert cli.select_characters(CONFIG, "shiftHEAL") == (SHIFTHEAL,)
    with pytest.raises(ConfigError):
        cli.select_characters(CONFIG, "nobody")


def test_step_summary(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    cli.write_step_summary(
        [
            cli.Outcome(SHIFTHEAL, report_url=REPORT_URL, uploaded=True),
            cli.Outcome(SHIFTHEAL, error="Boom | pipe"),
        ]
    )
    text = summary.read_text()
    assert "✅ imported" in text and f"[link]({REPORT_URL})" in text
    assert "Boom / pipe" in text


async def test_overrides_applied_to_fetched_gear_not_to_simc_exports(uploads, monkeypatch):
    from wishlist_updater.config import ItemOverride

    seen = []

    async def capture(profile, qe_settings):
        seen.append(profile.text)
        return REPORT_URL

    async def fake_raiderio(character, *, api_key=None):
        return cli.parse_simc_text('priest="Shiftheal"\nspec=holy\nhead=,id=1,ilevel=5\n')

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)
    char = Character(
        "Shiftheal", "ragnaros", "eu", {"head": ItemOverride(1, redirected_base_stats=9)}
    )
    config = Config(characters=(char,), qe={"raid_difficulty": "Mythic"})
    for simc in (None, ADDON_SIMC):
        outcome = await cli.process_character(
            char,
            config=config,
            secrets=SECRETS,
            simc_override=simc,
            generate_report=capture,
            dry_run=True,
        )
        assert outcome.error is None
    assert "head=,id=1,redirected_base_stats=9,ilevel=5" in seen[0]
    assert seen[1] == ADDON_SIMC
