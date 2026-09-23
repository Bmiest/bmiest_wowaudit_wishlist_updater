"""Command line entry point: character -> SimC -> QE Live report -> WoWAudit wishlist."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from wishlist_updater.config import DEFAULT_CONFIG_PATH, Character, Config, ConfigError, Secrets
from wishlist_updater.overrides import apply_overrides, extract_overrides, to_toml
from wishlist_updater.simc_source import (
    HEALER_SPECS,
    SimcProfile,
    fetch_simc_from_blizzard,
    fetch_simc_from_raiderio,
    parse_simc_text,
)
from wishlist_updater.upload_state import (
    fingerprint,
    last_uploaded_at,
    load_state,
    record_upload,
    upload_decision,
)
from wishlist_updater.wowaudit import upload_report
from wishlist_updater.wowaudit_session import load_session

log = logging.getLogger("wishlist_updater")

# (simc, qe_settings) -> report URL. Injected so the pipeline is testable without a browser.
ReportGenerator = Callable[[SimcProfile, dict[str, object]], Awaitable[str]]
# (report URL, character name) -> None; raises if the import didn't happen.
Uploader = Callable[[str, str], Awaitable[None]]


@dataclass
class Outcome:
    character: Character
    difficulty: str | None = None
    kind: str = "wishlist"  # or "crest": report-only, gear at its current level
    report_url: str | None = None
    uploaded_via: str | None = None  # "API key" / "login session"; None = not uploaded
    skipped: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    simc: str | None = None  # the SimC string QE was given (for the run summary/dashboard)
    gear_as_of: str | None = None  # when the gear source last read the character
    upload_skipped: str | None = None  # why an unchanged report wasn't re-uploaded
    last_uploaded_at: str | None = None

    @property
    def label(self) -> str:
        label = self.character.label
        if self.kind == "crest":
            return f"{label} · crest planner"
        return f"{label} · {self.difficulty}" if self.difficulty else label


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wishlist-updater", description=__doc__)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--character", help="Only process this character name (case-insensitive).")
    p.add_argument(
        "--simc-file",
        type=Path,
        help="Use this SimC export instead of fetching one ('-' reads stdin). "
        "Requires exactly one character (use --character).",
    )
    p.add_argument(
        "--extract-overrides",
        type=Path,
        metavar="SIMC_FILE",
        help="Print the wishlist.toml item_overrides block for an addon /simc export and exit.",
    )
    p.add_argument(
        "--wowaudit-login",
        nargs="?",
        const="browser",
        choices=["browser", "cookie"],
        help="One-time setup: save your WoWAudit login session for keyless imports "
        "('cookie' pastes the _user_session cookie from your normal browser instead).",
    )
    p.add_argument(
        "--refresh-overrides",
        type=Path,
        metavar="SIMC_FILE",
        help="Update the character's item_overrides in the config from an in-game /simc "
        "export (after catalysing a tier piece or equipping a new crafted item) and exit.",
    )
    p.add_argument("--dry-run", action="store_true", help="Generate reports but skip WoWAudit.")
    p.add_argument(
        "--upload-state",
        type=Path,
        metavar="PATH",
        help="Previous upload state (data/upload-state.json); unchanged reports are skipped.",
    )
    p.add_argument(
        "--force-upload",
        action="store_true",
        help="Upload even when the report's inputs are unchanged since the last upload.",
    )
    p.add_argument(
        "--summary-json",
        type=Path,
        metavar="PATH",
        help="Write a public run summary (gear, report results, status) for the dashboard.",
    )
    p.add_argument("--headed", action="store_true", help="Show the browser (local debugging).")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def select_characters(config: Config, name: str | None) -> tuple[Character, ...]:
    if not name:
        return config.characters
    chosen = tuple(c for c in config.characters if c.name.lower() == name.lower())
    if not chosen:
        raise ConfigError(f"Character {name!r} is not in the config")
    return chosen


async def get_simc(
    character: Character, source: str, secrets: Secrets, simc_override: str | None
) -> SimcProfile:
    if simc_override is not None:
        profile = parse_simc_text(simc_override)
        if profile.name.lower() != character.name.lower():
            raise ConfigError(f"SimC export is for {profile.name!r}, not {character.name!r}")
        return profile
    if source == "blizzard":
        secrets.require("blizzard_client_id", "blizzard_client_secret")
        return await fetch_simc_from_blizzard(
            character, secrets.blizzard_client_id, secrets.blizzard_client_secret
        )
    return await fetch_simc_from_raiderio(character, api_key=secrets.raiderio_api_key)


def staleness_warning(
    gear_as_of: str | None, max_age_hours: float, now: datetime | None = None
) -> str | None:
    """A warning when the gear source's data is older than max_age_hours."""
    if not gear_as_of:
        return None
    try:
        seen = datetime.fromisoformat(gear_as_of.replace("Z", "+00:00"))
    except ValueError:
        return None
    age_h = ((now or datetime.now(UTC)) - seen).total_seconds() / 3600
    if age_h <= max_age_hours:
        return None
    return (
        f"Raider.io last read this character {age_h / 24:.1f} days ago, so recent gear "
        "changes may be missing. Paste a /simc export for an up-to-date run."
    )


def raid_difficulties(qe_settings: dict[str, object]) -> list[str]:
    """wishlist.toml may list several; QE runs one per report, in the listed order."""
    value = qe_settings.get("raid_difficulty", "Mythic")
    return [value] if isinstance(value, str) else [str(v) for v in value]


async def process_character(
    character: Character,
    *,
    config: Config,
    secrets: Secrets,
    simc_override: str | None,
    generate_report: ReportGenerator,
    upload: Uploader | None,
    upload_method: str | None = None,
    upload_state: dict | None = None,
    force_upload: bool = False,
) -> list[Outcome]:
    """One Outcome per raid difficulty (or a single one if the character fails before QE)."""
    base = Outcome(character)
    try:
        profile = await get_simc(character, config.simc_source, secrets, simc_override)
        if simc_override is None and character.item_overrides:
            # A real /simc export already carries these fields; fetched gear needs them.
            text, base.warnings = apply_overrides(profile.text, character.item_overrides)
            profile = replace(profile, text=text)
        for warning in base.warnings:
            log.warning("%s: %s", character.label, warning)
        base.simc = profile.text
        base.gear_as_of = profile.gear_as_of
        if stale := staleness_warning(profile.gear_as_of, config.raiderio_stale_after_hours):
            base.warnings.append(stale)
            log.warning("%s: %s", character.label, stale)
        if (profile.class_token, profile.spec_token) not in HEALER_SPECS:
            base.skipped = (
                f"{profile.spec_token} {profile.class_token} is not a healer spec "
                "(QE Live only supports healers)"
            )
            return [base]
    except Exception as exc:
        log.exception("%s: failed", character.label)
        base.error = f"{type(exc).__name__}: {exc}"
        return [base]

    outcomes = []
    # Each difficulty is its own report and upload; one failing must not stop the rest.
    state_key = f"{character.name}-{character.realm}-{character.region}".lower()
    for difficulty in raid_difficulties(config.qe):
        outcome = replace(base, difficulty=difficulty, warnings=list(base.warnings))
        outcomes.append(outcome)
        try:
            settings = {**config.qe, "raid_difficulty": difficulty}
            log.info("%s: generating QE Live report", outcome.label)
            outcome.report_url = await generate_report(profile, settings)
            log.info("%s: report %s", outcome.label, outcome.report_url)
            if upload is None:
                continue
            fp = fingerprint(profile.text, settings, difficulty)
            # WoWAudit allows this automation on the condition that it uploads less: skip
            # reports whose inputs haven't changed, unless the user asked for this upload.
            if upload_state is not None and not force_upload and simc_override is None:
                now = datetime.now(UTC)
                reason = upload_decision(
                    upload_state,
                    state_key,
                    difficulty,
                    fp,
                    now=now,
                    max_age_days=config.reupload_after_days,
                )
                if reason:
                    outcome.upload_skipped = reason
                    outcome.last_uploaded_at = last_uploaded_at(upload_state, state_key, difficulty)
                    log.info("%s: not re-uploaded: %s", outcome.label, reason)
                    continue
            await upload(outcome.report_url, profile.name)
            outcome.uploaded_via = upload_method
            log.info("%s: imported into WoWAudit (%s)", outcome.label, upload_method)
            if upload_state is not None:
                report_id = outcome.report_url.rstrip("/").rsplit("/", 1)[-1]
                record_upload(
                    upload_state, state_key, difficulty, fp, report_id, now=datetime.now(UTC)
                )
                outcome.last_uploaded_at = last_uploaded_at(upload_state, state_key, difficulty)
        except Exception as exc:
            log.exception("%s: failed", outcome.label)
            outcome.error = f"{type(exc).__name__}: {exc}"

    if config.crest_planner:
        # One more report with the equipped gear at its CURRENT level: QE then scores your
        # own item at max upgrade, which is what spending crests on it would gain. Never
        # uploaded, and a failure here is only a warning.
        difficulty = raid_difficulties(config.qe)[-1]
        crest = replace(base, difficulty=difficulty, kind="crest", warnings=[])
        try:
            crest.report_url = await generate_report(
                profile,
                {**config.qe, "raid_difficulty": difficulty, "upgrade_all_to_max": False},
            )
            log.info("%s: report %s", crest.label, crest.report_url)
            outcomes.append(crest)
        except Exception as exc:
            log.warning("%s: failed: %s", crest.label, exc)
            outcomes[-1].warnings.append(f"Crest planner report failed: {type(exc).__name__}")
    return outcomes


def api_uploader(api_key: str) -> Uploader:
    async def upload(report_url: str, character_name: str) -> None:
        await upload_report(report_url, api_key, character_name=character_name)

    return upload


class Browser:
    """One Chromium for the whole run, with a fresh context per QE report or WoWAudit upload."""

    def __init__(self, headed: bool) -> None:
        self.headed = headed

    async def __aenter__(self) -> Browser:
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=not self.headed)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._browser.close()
        await self._pw.stop()

    async def generate(self, profile: SimcProfile, qe_settings: dict[str, object]) -> str:
        from wishlist_updater import qe

        # A fresh context keeps QE's localStorage (saved characters, settings) from
        # leaking between characters.
        context = await self._browser.new_context(viewport={"width": 1600, "height": 1000})
        try:
            page = await context.new_page()
            return await qe.generate_upgrade_report(
                page, profile.text, qe.QESettings(**qe_settings)
            )
        finally:
            await context.close()

    def session_uploader(self, session: dict, team_url: str) -> Uploader:
        from wishlist_updater.wowaudit_web import upload_report_via_web

        async def upload(report_url: str, character_name: str) -> None:
            # The session only ever lives in this short-lived context, never in the QE ones.
            context = await self._browser.new_context(storage_state=session)
            try:
                await upload_report_via_web(
                    context, report_url, team_url=team_url, character_name=character_name
                )
            finally:
                await context.close()

        return upload


def choose_upload(
    args: argparse.Namespace, config: Config, secrets: Secrets
) -> tuple[str | None, dict | None]:
    """Pick how reports reach WoWAudit: ("API key", None), ("login session", state), or
    (None, None) for report-only."""
    if args.dry_run:
        return None, None
    if secrets.wowaudit_api_key:
        return "API key", None
    session = load_session()
    if session is not None:
        if not config.wowaudit_team_url:
            raise ConfigError("WOWAUDIT_SESSION is set but wishlist.toml has no wowaudit_team_url")
        return "login session", session
    log.warning(
        "Neither WOWAUDIT_API_KEY nor WOWAUDIT_SESSION is set: generating reports only; "
        "paste them into WoWAudit"
    )
    return None, None


def write_step_summary(outcomes: list[Outcome]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    rows = ["| Character | Result | Report |", "|---|---|---|"]
    for o in outcomes:
        if o.kind == "crest":
            result = "🪙 crest estimates (not uploaded)"
        elif o.upload_skipped:
            result = f"⏭️ unchanged, last imported {o.last_uploaded_at or 'earlier'}"
        elif o.error:
            result = f"❌ {o.error}"
        elif o.skipped:
            result = f"⏭️ {o.skipped}"
        elif o.uploaded_via:
            result = f"✅ imported via {o.uploaded_via}"
        else:
            result = "📋 report only: paste the link into WoWAudit"
        if o.warnings:
            result += "<br>⚠️ " + "<br>⚠️ ".join(o.warnings)
        report = f"[link]({o.report_url})" if o.report_url else ""
        rows.append(f"| {o.label} | {result.replace('|', '/')} | {report} |")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("## WoWAudit wishlist update\n\n" + "\n".join(rows) + "\n")


async def run(args: argparse.Namespace) -> int:
    started_at = datetime.now(UTC)
    config = Config.load(args.config)
    characters = select_characters(config, args.character)
    secrets = Secrets.from_env()
    upload_method, session = choose_upload(args, config, secrets)
    upload_state = load_state(args.upload_state) if args.upload_state else None

    simc_override = None
    if args.simc_file is not None:
        if len(characters) != 1:
            raise ConfigError("--simc-file needs exactly one character; pass --character")
        simc_override = (
            sys.stdin.read() if str(args.simc_file) == "-" else args.simc_file.read_text()
        )

    async with Browser(args.headed) as browser:
        if upload_method == "API key":
            upload = api_uploader(secrets.wowaudit_api_key)
        elif upload_method == "login session":
            upload = browser.session_uploader(session, config.wowaudit_team_url)
        else:
            upload = None
        outcomes = []
        for c in characters:
            outcomes += await process_character(
                c,
                config=config,
                secrets=secrets,
                simc_override=simc_override,
                generate_report=browser.generate,
                upload=upload,
                upload_method=upload_method,
                upload_state=upload_state,
                force_upload=args.force_upload,
            )

    write_step_summary(outcomes)
    if args.summary_json:
        from wishlist_updater.summary import build_summary, write_summary

        summary = build_summary(outcomes, started_at=started_at, upload_method=upload_method)
        if upload_state is not None:
            summary["upload_state"] = upload_state  # persisted by the record job
        write_summary(summary, args.summary_json)
    for o in outcomes:
        status = (
            o.error
            or o.skipped
            or (f"imported via {o.uploaded_via}" if o.uploaded_via else "report only")
        )
        if o.kind == "crest":
            status = "crest estimates (not uploaded)"
        elif o.upload_skipped:
            status = f"unchanged, not re-uploaded (last import {o.last_uploaded_at})"
        print(f"{o.label}: {status} {o.report_url or ''}".rstrip())
    return 1 if any(o.error for o in outcomes) else 0


def refresh_overrides(config_path: Path, simc_path: Path) -> int:
    from wishlist_updater.overrides import is_addon_export, replace_item_overrides

    simc_text = simc_path.read_text(encoding="utf-8")
    if not is_addon_export(simc_text):
        log.error(
            "%s is not an in-game SimulationCraft addon export (no '# SimC Addon' header). "
            "Raider.io / Warcraft Logs exports lack the catalyst and crafted stats.",
            simc_path,
        )
        return 2
    name = parse_simc_text(simc_text).name
    overrides = extract_overrides(simc_text)
    config_text = config_path.read_text(encoding="utf-8")
    try:
        updated = replace_item_overrides(config_text, name, overrides)
    except ValueError as exc:
        log.error("%s", exc)
        return 2
    Config.load_text(updated, config_path)  # never write a config that doesn't load
    if updated == config_text:
        print(f"{name}: item overrides already up to date ({len(overrides)} slots)")
        return 0
    config_path.write_text(updated, encoding="utf-8")
    print(f"{name}: item overrides updated ({len(overrides)} slots) in {config_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.wowaudit_login:
        from wishlist_updater import wowaudit_session as ws

        if args.wowaudit_login == "cookie":
            path = ws.capture_session_from_cookie()
        else:
            path = asyncio.run(ws.capture_session_interactively())
        print(f"\nSaved to {path} (readable only by you). To use it in GitHub Actions:")
        repo = "Bmiest/bmiest_wowaudit_wishlist_updater"
        print(f"  gh secret set WOWAUDIT_SESSION -R {repo} < {path}")
        return 0
    if args.refresh_overrides:
        return refresh_overrides(args.config, args.refresh_overrides)
    if args.extract_overrides:
        overrides = extract_overrides(args.extract_overrides.read_text())
        print("# Paste under the matching [[characters]] entry in wishlist.toml")
        print(to_toml(overrides), end="")
        return 0
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(run(args))
    except ConfigError as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
