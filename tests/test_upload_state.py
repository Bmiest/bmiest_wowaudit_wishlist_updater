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


def _harness(monkeypatch, config=CONFIG):
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
            config=config,
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


async def test_only_listed_difficulties_are_uploaded(monkeypatch, tmp_path):
    config = Config(
        characters=(SHIFTHEAL,),
        qe={"raid_difficulty": ["Heroic", "Mythic"]},
        upload_difficulties=("Mythic",),
    )
    uploads, run = _harness(monkeypatch, config)
    state = load_state(None)
    heroic, mythic = await run(state, force=True)
    assert uploads == ["rMythic"]  # force doesn't upload a dashboard-only difficulty
    assert heroic.report_url and heroic.dashboard_only and heroic.uploaded_via is None
    assert heroic.error is None and heroic.upload_error is None
    assert mythic.uploaded_via == "login session" and not mythic.dashboard_only
    assert set(state["characters"]["shiftheal-ragnaros-eu"]) == {"Mythic"}  # no Heroic state

    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    cli.write_step_summary([heroic, mythic])
    text = summary.read_text()
    assert "dashboard only" in text and "paste the link" not in text


# --- raid-day uploads ------------------------------------------------------------

from wishlist_updater.upload_state import raid_day_decision  # noqa: E402

WED = datetime(2026, 9, 23, 7, 30, tzinfo=UTC)  # a Wednesday
RAID_DAYS = (2, 6)  # Wednesday, Sunday


def test_raid_day_decision():
    state = load_state(None)
    fp = fingerprint(RAIDERIO, QE, "Mythic")

    def decide(now, fp_=fp):
        return raid_day_decision(state, "k", "Mythic", fp_, now=now, upload_weekdays=RAID_DAYS)

    assert "Not a raid day" in decide(WED - timedelta(days=1))  # Tuesday
    assert "Wednesday and Sunday" in decide(WED - timedelta(days=1))
    assert decide(WED) is None  # raid day, never uploaded
    record_upload(state, "k", "Mythic", fp, "r1", now=WED)
    assert decide(WED.replace(hour=12)) == "Already uploaded today"  # the catch-up run
    assert decide(WED.replace(hour=12), fp_="changed") is None  # new gear on raid day
    assert decide(WED + timedelta(days=4)) is None  # Sunday: upload again


async def test_raid_days_drive_uploads_end_to_end(monkeypatch):
    today = datetime.now(UTC).weekday()
    raid_today = Config(
        characters=(SHIFTHEAL,), qe={"raid_difficulty": "Mythic"}, upload_weekdays=(today,)
    )
    uploads, run = _harness(monkeypatch, raid_today)
    state = load_state(None)
    [first] = await run(state)
    [second] = await run(state)
    assert uploads == ["rMythic"]  # the catch-up run on the same raid day doesn't re-upload
    assert first.uploaded_via and second.upload_skipped == "Already uploaded today"

    not_today = Config(
        characters=(SHIFTHEAL,),
        qe={"raid_difficulty": "Mythic"},
        upload_weekdays=((today + 1) % 7,),
    )
    uploads2, run2 = _harness(monkeypatch, not_today)
    [skipped] = await run2(load_state(None))
    [forced] = await run2(load_state(None), force=True)
    assert "Not a raid day" in skipped.upload_skipped and skipped.report_url
    assert forced.uploaded_via and uploads2 == ["rMythic"]


# --- WoWAudit socket rejections ---------------------------------------------------

from wishlist_updater.upload_state import preferred_auto_gem  # noqa: E402
from wishlist_updater.wowaudit_web import WowAuditWebError  # noqa: E402

MYTHIC_ONLY = Config(
    characters=(SHIFTHEAL,),
    qe={"raid_difficulty": ["Heroic", "Mythic"], "auto_gem": False},
    upload_difficulties=("Mythic",),
)
KEY = "shiftheal-ragnaros-eu"


def _socket_harness(monkeypatch, wants_sockets, error=None):
    """WoWAudit that accepts only reports whose socket setting is `wants_sockets`."""
    generated, uploads = [], []

    async def generate(profile, qe_settings):
        gem = bool(qe_settings.get("auto_gem"))
        generated.append((qe_settings["raid_difficulty"], gem))
        return f"https://questionablyepic.com/live/upgradereport/{qe_settings['raid_difficulty']}{int(gem)}"

    async def upload(url, name):
        uploads.append(url.rsplit("/", 1)[1])
        has_gems = url.endswith("1")
        if error:
            raise WowAuditWebError(error)
        if has_gems != wants_sockets:
            need = "must contain vault sockets" if wants_sockets else "must not contain sockets"
            raise WowAuditWebError(f"WoWAudit could not import the report: Report items {need}.")

    async def fake_raiderio(character, *, api_key=None):
        return cli.parse_simc_text(RAIDERIO)

    monkeypatch.setattr(cli, "fetch_simc_from_raiderio", fake_raiderio)

    async def run(state):
        return await cli.process_character(
            SHIFTHEAL,
            config=MYTHIC_ONLY,
            secrets=Secrets(wowaudit_api_key=None),
            simc_override=None,
            generate_report=generate,
            upload=upload,
            upload_method="login session",
            upload_state=state,
            force_upload=True,
        )

    return generated, uploads, run


async def test_socket_rejection_retries_with_sockets_and_remembers(monkeypatch):
    generated, uploads, run = _socket_harness(monkeypatch, wants_sockets=True)
    state = load_state(None)
    heroic, mythic = await run(state)
    assert uploads == ["Mythic0", "Mythic1"]  # rejected without sockets, accepted with
    assert mythic.uploaded_via and mythic.upload_error is None
    assert mythic.report_url.endswith("Mythic1")  # the uploaded version is what's reported
    assert "with sockets" in mythic.upload_note
    assert preferred_auto_gem(state, KEY, "Mythic") is True
    assert heroic.dashboard_only and ("Heroic", False) in generated  # Heroic untouched

    generated.clear(), uploads.clear()
    await run(state)  # next run starts with sockets: no wasted, rejected upload
    assert uploads == ["Mythic1"] and ("Mythic", True) in generated


async def test_socket_rejection_works_the_other_way_round(monkeypatch):
    _, uploads, run = _socket_harness(monkeypatch, wants_sockets=False)
    state = load_state(None)
    remember = cli.remember_auto_gem  # start from a remembered "with sockets"
    remember(state, KEY, "Mythic", True)
    _, mythic = await run(state)
    assert uploads == ["Mythic1", "Mythic0"]
    assert mythic.uploaded_via and "without sockets" in mythic.upload_note
    assert preferred_auto_gem(state, KEY, "Mythic") is False


async def test_other_upload_errors_are_not_retried(monkeypatch):
    _, uploads, run = _socket_harness(monkeypatch, wants_sockets=True, error="HTTP 500")
    _, mythic = await run(load_state(None))
    assert uploads == ["Mythic0"]
    assert "HTTP 500" in mythic.upload_error and mythic.upload_note is None


async def test_failed_retry_reports_both_errors(monkeypatch):
    _, uploads, run = _socket_harness(
        monkeypatch, wants_sockets=True, error="Report items must contain vault sockets."
    )
    state = load_state(None)
    _, mythic = await run(state)
    assert uploads == ["Mythic0", "Mythic1"]  # exactly one retry
    assert mythic.upload_error.count("vault sockets") == 2
    assert "retry with sockets" in mythic.upload_error
    assert preferred_auto_gem(state, KEY, "Mythic") is None  # nothing learned from a failure
