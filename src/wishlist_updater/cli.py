"""Command line entry point: character -> SimC -> QE Live report -> WoWAudit wishlist."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
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
    report_url: str | None = None
    uploaded_via: str | None = None  # "API key" / "login session"; None = not uploaded
    skipped: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    simc: str | None = None  # the SimC string QE was given (for the run summary/dashboard)

    @property
    def label(self) -> str:
        label = self.character.label
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
    p.add_argument("--dry-run", action="store_true", help="Generate reports but skip WoWAudit.")
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
    for difficulty in raid_difficulties(config.qe):
        outcome = replace(base, difficulty=difficulty, warnings=list(base.warnings))
        outcomes.append(outcome)
        try:
            log.info("%s: generating QE Live report", outcome.label)
            outcome.report_url = await generate_report(
                profile, {**config.qe, "raid_difficulty": difficulty}
            )
            log.info("%s: report %s", outcome.label, outcome.report_url)
            if upload is None:
                continue
            await upload(outcome.report_url, profile.name)
            outcome.uploaded_via = upload_method
            log.info("%s: imported into WoWAudit (%s)", outcome.label, upload_method)
        except Exception as exc:
            log.exception("%s: failed", outcome.label)
            outcome.error = f"{type(exc).__name__}: {exc}"
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
        if o.error:
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
    config = Config.load(args.config)
    characters = select_characters(config, args.character)
    secrets = Secrets.from_env()
    upload_method, session = choose_upload(args, config, secrets)

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
            )

    write_step_summary(outcomes)
    for o in outcomes:
        status = (
            o.error
            or o.skipped
            or (f"imported via {o.uploaded_via}" if o.uploaded_via else "report only")
        )
        print(f"{o.label}: {status} {o.report_url or ''}".rstrip())
    return 1 if any(o.error for o in outcomes) else 0


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
