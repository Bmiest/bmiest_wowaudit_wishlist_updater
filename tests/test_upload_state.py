import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wishlist_updater import cli
from wishlist_updater.config import Character, Config, Secrets
from wishlist_updater.dashboard import publish
from wishlist_updater.upload_state import (
    fingerprint,
    load_state,
    record_upload,
    upload_decision,
)

FIXTURES = Path(__file__).parent / "fixtures"
RAIDERIO = (FIXTURES / "simc" / "shiftheal_raiderio.simc").read_text()
QE = {"raid_difficulty": "Mythic", "mplus_level": 10}
NOW = datetime(2026, 9, 24, 7, 0, tzinfo=UTC)


def test_fingerprint_ignores_header_date_and_item_name_comments():
    later = RAIDERIO.replace("2026-09-22 21:27", "2026-09-30 06:12").replace(
        "# Cosmic Penitent's Truesight (321)", "# renamed (321)"
    )
    assert fingerprint(RAIDERIO, QE, "Mythic") == fingerprint(later, QE, "Mythic")


@pytest.mark.parametrize(
    "change",
    [
        lambda t, q, d: (t.replace("head=,id=271555", "head=,id=271999"), q, d),  # new item
        lambda t, q, d: (t.replace("talents=CEQ", "talents=CEZ"), q, d),  # talents
        lambda t, q, d: (t, {**q, "mplus_level": 12}, d),  # settings
        lambda t, q, d: (t, q, "Heroic"),  # difficulty
    ],
)
def test_fingerprint_changes_with_inputs(change):
    assert fingerprint(RAIDERIO, QE, "Mythic") != fingerprint(*change(RAIDERIO, QE, "Mythic"))


def test_upload_decision():
    state = load_state(None)
    fp = fingerprint(RAIDERIO, QE, "Mythic")

    def decide(fp_=fp, difficulty="Mythic", now=NOW):
        return upload_decision(state, "k", difficulty, fp_, now=now, max_age_days=7)

    assert decide() is None  # never uploaded
    record_upload(state, "k", "Mythic", fp, "abc", now=NOW - timedelta(days=2))
    assert decide()  # unchanged within a week: skip
    assert decide(fp_="other") is None  # something changed
    assert decide(difficulty="Heroic") is None  # other difficulty never uploaded
    assert decide(now=NOW + timedelta(days=6)) is None  # 8 days old: weekly refresh


def test_load_state_tolerates_garbage(tmp_path):
    bad = tmp_path / "s.json"
    bad.write_text("{not json")
    assert load_state(bad) == {"schema": 1, "characters": {}}
    assert load_state(tmp_path / "missing.json")["characters"] == {}


SHIFTHEAL = Character("Shiftheal", "ragnaros", "eu")
CONFIG = Config(characters=(SHIFTHEAL,), qe={"raid_difficulty": ["Heroic", "Mythic"]})


def _harness(monkeypatch):
    uploads = []

    async def generate(profile, qe_settings):
        return "https://questionablyepic.com/live/upgradereport/r" + qe_settings["raid_difficulty"]

    async def upload(url, name):
        uploads.append(url.rsplit("/", 1)[1])

    async def fake_raiderio(character, *, api_key=None):
        return cli.parse_simc_text(RAIDERIO)

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)

    async def run(state, *, simc=None, force=False):
        return await cli.process_character(
            SHIFTHEAL,
            config=CONFIG,
            secrets=Secrets(wowaudit_api_key=None),
            simc_override=simc,
            generate_report=generate,
            upload=upload,
            upload_method="login session",
            upload_state=state,
            force_upload=force,
        )

    return uploads, run


async def test_second_unchanged_run_skips_uploads_but_still_makes_reports(monkeypatch):
    uploads, run = _harness(monkeypatch)
    state = load_state(None)
    first = await run(state)
    assert uploads == ["rHeroic", "rMythic"]
    assert all(o.uploaded_via for o in first)
    second = await run(state)
    assert uploads == ["rHeroic", "rMythic"]  # nothing new uploaded
    assert all(o.report_url and o.upload_skipped and o.last_uploaded_at for o in second)
    assert all(o.error is None for o in second)


async def test_force_and_pasted_simc_always_upload(monkeypatch):
    uploads, run = _harness(monkeypatch)
    state = load_state(None)
    await run(state)
    await run(state, force=True)
    assert len(uploads) == 4
    addon = (FIXTURES / "simc" / "shiftheal_addon.simc").read_text()
    await run(state, simc=addon)
    assert len(uploads) == 6


def test_publish_scrubs_upload_fields_and_never_publishes_state(tmp_path):
    sample = json.loads((FIXTURES / "dashboard" / "run_sample.json").read_text())
    legacy = json.loads(json.dumps(sample))
    legacy["run"].update(
        id="8", started_at="2026-09-23T07:00:00+00:00", upload_method="login session"
    )
    for r in legacy["characters"][0]["reports"]:
        r.update(uploaded_via="login session", upload_skipped=None, last_uploaded_at=None)
    (tmp_path / "runs").mkdir(parents=True)
    (tmp_path / "runs" / "8.json").write_text(json.dumps(legacy))
    (tmp_path / "upload-state.json").write_text("{}")  # from an older version

    sample["run"].update(id="9", started_at="2026-09-24T07:00:00+00:00")
    publish(sample, tmp_path)

    assert not (tmp_path / "upload-state.json").exists()
    for name in ("runs/8.json", "runs/9.json", "index.json", "latest.json"):
        text = (tmp_path / name).read_text()
        for key in ("uploaded_via", "upload_skipped", "last_uploaded_at", "upload_method"):
            assert key not in text, (name, key)


def test_save_upload_state_round_trips(tmp_path):
    state = load_state(None)
    record_upload(state, "k", "Mythic", "fp", "rid", now=NOW)
    path = tmp_path / "cache" / "upload-state.json"
    cli.save_upload_state(path, state)
    assert load_state(path) == state


async def test_only_listed_difficulties_are_uploaded(monkeypatch):
    uploads, _ = _harness(monkeypatch)

    async def generate(profile, qe_settings):
        return "https://questionablyepic.com/live/upgradereport/r" + qe_settings["raid_difficulty"]

    async def upload(url, name):
        uploads.append(url.rsplit("/", 1)[1])

    config = Config(
        characters=(SHIFTHEAL,),
        qe={"raid_difficulty": ["Heroic", "Mythic"]},
        upload_difficulties=("Mythic",),
    )
    heroic, mythic = await cli.process_character(
        SHIFTHEAL,
        config=config,
        secrets=Secrets(wowaudit_api_key=None),
        simc_override=None,
        generate_report=generate,
        upload=upload,
        upload_method="login session",
        upload_state=load_state(None),
    )
    assert uploads == ["rMythic"]
    assert heroic.report_url and heroic.uploaded_via is None and heroic.error is None
    assert mythic.uploaded_via == "login session"


def test_upload_difficulties_config(tmp_path):
    cfg = tmp_path / "w.toml"
    base = '[[characters]]\nname = "A"\nrealm = "b"\n'
    cfg.write_text('upload_difficulties = "Mythic"\n' + base)
    assert Config.load(cfg).upload_difficulties == ("Mythic",)
    cfg.write_text(base)
    assert Config.load(cfg).upload_difficulties is None
    cfg.write_text("upload_difficulties = [1]\n" + base)
    with pytest.raises(Exception, match="upload_difficulties"):
        Config.load(cfg)
