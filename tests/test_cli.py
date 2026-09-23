from dataclasses import replace
from datetime import UTC, datetime
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
    [outcome] = await cli.process_character(
        SHIFTHEAL,
        config=config,
        secrets=secrets,
        simc_override=simc,
        generate_report=generate,
        upload=None if dry_run else cli.api_uploader(secrets.wowaudit_api_key),
        upload_method=None if dry_run else "API key",
    )
    return outcome


async def test_happy_path_uploads_report(uploads):
    outcome = await _process()
    assert outcome.error is None
    assert outcome.uploaded_via == "API key"
    assert outcome.report_url == REPORT_URL
    assert uploads == [(REPORT_URL, "k", "Shiftheal")]


async def test_dry_run_skips_upload(uploads):
    outcome = await _process(dry_run=True)
    assert outcome.report_url == REPORT_URL
    assert outcome.uploaded_via is None
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
    assert outcome.uploaded_via
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
            cli.Outcome(SHIFTHEAL, "Mythic", report_url=REPORT_URL, uploaded_via="login session"),
            cli.Outcome(SHIFTHEAL, error="Boom | pipe"),
        ]
    )
    text = summary.read_text()
    assert "✅ imported via login session" in text and f"[link]({REPORT_URL})" in text
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
        [outcome] = await cli.process_character(
            char,
            config=config,
            secrets=SECRETS,
            simc_override=simc,
            generate_report=capture,
            upload=None,
        )
        assert outcome.error is None
    assert "head=,id=1,redirected_base_stats=9,ilevel=5" in seen[0]
    assert seen[1] == ADDON_SIMC


def test_step_summary_report_only(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    cli.write_step_summary([cli.Outcome(SHIFTHEAL, report_url=REPORT_URL)])
    assert "report only" in summary.read_text()


@pytest.mark.parametrize(
    "dry_run, api_key, session, expected",
    [
        (True, "k", '{"cookies": []}', None),
        (False, "k", '{"cookies": []}', "API key"),  # the team key wins when both are set
        (False, None, '{"cookies": []}', "login session"),
        (False, None, None, None),
    ],
)
def test_choose_upload(monkeypatch, dry_run, api_key, session, expected):
    monkeypatch.delenv("WOWAUDIT_SESSION_FILE", raising=False)
    if session:
        monkeypatch.setenv("WOWAUDIT_SESSION", session)
    else:
        monkeypatch.delenv("WOWAUDIT_SESSION", raising=False)
    args = cli.build_parser().parse_args(["--dry-run"] if dry_run else [])
    config = Config(characters=(SHIFTHEAL,), qe={}, wowaudit_team_url="https://wowaudit.com/x")
    method, state = cli.choose_upload(args, config, Secrets(wowaudit_api_key=api_key))
    assert method == expected
    assert (state is not None) == (expected == "login session")


def test_choose_upload_session_needs_team_url(monkeypatch):
    monkeypatch.setenv("WOWAUDIT_SESSION", '{"cookies": []}')
    args = cli.build_parser().parse_args([])
    config = Config(characters=(SHIFTHEAL,), qe={})
    with pytest.raises(ConfigError, match="wowaudit_team_url"):
        cli.choose_upload(args, config, Secrets(wowaudit_api_key=None))


async def test_upload_failure_is_an_error_with_report_link_kept(uploads):
    async def expired(report_url, character_name):
        raise RuntimeError("Not logged in to WoWAudit. Run `wishlist-updater --wowaudit-login`")

    [outcome] = await cli.process_character(
        SHIFTHEAL,
        config=CONFIG,
        secrets=SECRETS,
        simc_override=ADDON_SIMC,
        generate_report=fake_report,
        upload=expired,
        upload_method="login session",
    )
    assert outcome.report_url == REPORT_URL
    assert outcome.uploaded_via is None
    assert "--wowaudit-login" in outcome.error


async def test_heroic_then_mythic_two_reports_two_uploads_in_order(monkeypatch):
    calls = []

    async def generate(profile, qe_settings):
        calls.append(("qe", qe_settings["raid_difficulty"]))
        return f"https://questionablyepic.com/live/upgradereport/{qe_settings['raid_difficulty']}"

    async def upload(report_url, character_name):
        calls.append(("upload", report_url.rsplit("/", 1)[1]))

    fetches = []

    async def fake_raiderio(character, *, api_key=None):
        fetches.append(character)
        return cli.parse_simc_text(ADDON_SIMC)

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)
    config = Config(
        characters=(SHIFTHEAL,), qe={"raid_difficulty": ["Heroic", "Mythic"], "mplus_level": 10}
    )
    outcomes = await cli.process_character(
        SHIFTHEAL,
        config=config,
        secrets=SECRETS,
        simc_override=None,
        generate_report=generate,
        upload=upload,
        upload_method="login session",
    )
    assert len(fetches) == 1  # gear fetched once, reused for both reports
    assert calls == [("qe", "Heroic"), ("upload", "Heroic"), ("qe", "Mythic"), ("upload", "Mythic")]
    assert [o.difficulty for o in outcomes] == ["Heroic", "Mythic"]
    assert [o.label for o in outcomes] == [
        "Shiftheal-ragnaros (EU) · Heroic",
        "Shiftheal-ragnaros (EU) · Mythic",
    ]
    assert all(o.uploaded_via == "login session" and o.simc for o in outcomes)


async def test_failed_heroic_does_not_block_mythic():
    async def generate(profile, qe_settings):
        if qe_settings["raid_difficulty"] == "Heroic":
            raise RuntimeError("QE hiccup")
        return REPORT_URL

    config = Config(characters=(SHIFTHEAL,), qe={"raid_difficulty": ["Heroic", "Mythic"]})
    heroic, mythic = await cli.process_character(
        SHIFTHEAL,
        config=config,
        secrets=SECRETS,
        simc_override=ADDON_SIMC,
        generate_report=generate,
        upload=None,
    )
    assert heroic.error == "RuntimeError: QE hiccup"
    assert mythic.error is None and mythic.report_url == REPORT_URL


def test_raid_difficulties():
    assert cli.raid_difficulties({}) == ["Mythic"]
    assert cli.raid_difficulties({"raid_difficulty": "Heroic"}) == ["Heroic"]
    assert cli.raid_difficulties({"raid_difficulty": ["Heroic", "Mythic"]}) == ["Heroic", "Mythic"]


def test_staleness_warning():
    now = datetime(2026, 9, 23, 6, 0, tzinfo=UTC)
    assert cli.staleness_warning(None, 48, now) is None
    assert cli.staleness_warning("garbage", 48, now) is None
    assert cli.staleness_warning("2026-09-22T12:00:00.000Z", 48, now) is None
    warning = cli.staleness_warning("2026-09-20T23:00:18.000Z", 48, now)
    assert warning and "2.3 days ago" in warning and "/simc" in warning


async def test_gear_as_of_flows_from_raiderio_and_triggers_warning(uploads, monkeypatch):
    async def fake_raiderio(character, *, api_key=None):
        profile = cli.parse_simc_text(ADDON_SIMC)
        return replace(profile, gear_as_of="2020-01-01T00:00:00.000Z")

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)
    outcome = await _process(simc=None)
    assert outcome.gear_as_of == "2020-01-01T00:00:00.000Z"
    assert any("Raider.io last read this character" in w for w in outcome.warnings)
    assert outcome.uploaded_via  # stale gear warns, it doesn't block the run
