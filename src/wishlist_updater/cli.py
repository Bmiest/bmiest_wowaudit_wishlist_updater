"""Command line entry point: character -> SimC -> QE Live report -> WoWAudit wishlist."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from wishlist_updater.config import DEFAULT_CONFIG_PATH, Character, Config, ConfigError, Secrets
from wishlist_updater.simc_source import (
    HEALER_SPECS,
    SimcProfile,
    fetch_simc_from_blizzard,
    parse_simc_text,
)
from wishlist_updater.wowaudit import upload_report

log = logging.getLogger("wishlist_updater")

# (simc, qe_settings) -> report URL. Injected so the pipeline is testable without a browser.
ReportGenerator = Callable[[SimcProfile, dict[str, object]], Awaitable[str]]


@dataclass
class Outcome:
    character: Character
    report_url: str | None = None
    uploaded: bool = False
    skipped: str | None = None
    error: str | None = None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wishlist-updater", description=__doc__)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--character", help="Only process this character name (case-insensitive).")
    p.add_argument(
        "--simc-file",
        type=Path,
        help="Use this SimC export instead of the Blizzard API ('-' reads stdin). "
        "Requires exactly one character (use --character).",
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
    character: Character, secrets: Secrets, simc_override: str | None
) -> SimcProfile:
    if simc_override is not None:
        profile = parse_simc_text(simc_override)
        if profile.name.lower() != character.name.lower():
            raise ConfigError(f"SimC export is for {profile.name!r}, not {character.name!r}")
        return profile
    secrets.require("blizzard_client_id", "blizzard_client_secret")
    return await fetch_simc_from_blizzard(
        character, secrets.blizzard_client_id, secrets.blizzard_client_secret
    )


async def process_character(
    character: Character,
    *,
    config: Config,
    secrets: Secrets,
    simc_override: str | None,
    generate_report: ReportGenerator,
    dry_run: bool,
) -> Outcome:
    outcome = Outcome(character)
    try:
        profile = await get_simc(character, secrets, simc_override)
        if (profile.class_token, profile.spec_token) not in HEALER_SPECS:
            outcome.skipped = (
                f"{profile.spec_token} {profile.class_token} is not a healer spec "
                "(QE Live only supports healers)"
            )
            return outcome

        log.info("%s: generating QE Live report", character.label)
        outcome.report_url = await generate_report(profile, config.qe)
        log.info("%s: report %s", character.label, outcome.report_url)

        if dry_run:
            return outcome
        await upload_report(
            outcome.report_url, secrets.wowaudit_api_key, character_name=profile.name
        )
        outcome.uploaded = True
        log.info("%s: imported into WoWAudit", character.label)
    except Exception as exc:  # one character failing must not stop the others
        log.exception("%s: failed", character.label)
        outcome.error = f"{type(exc).__name__}: {exc}"
    return outcome


async def _playwright_report_generator(headed: bool):
    """Return (generate, close): one browser, with a fresh context per report."""
    from playwright.async_api import async_playwright

    from wishlist_updater import qe

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=not headed)

    async def generate(profile: SimcProfile, qe_settings: dict[str, object]) -> str:
        # A fresh context per character keeps QE's localStorage (saved characters,
        # settings) from leaking between runs.
        context = await browser.new_context(viewport={"width": 1600, "height": 1000})
        try:
            page = await context.new_page()
            return await qe.generate_upgrade_report(
                page, profile.text, qe.QESettings(**qe_settings)
            )
        finally:
            await context.close()

    async def close() -> None:
        await browser.close()
        await pw.stop()

    return generate, close


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
        elif o.uploaded:
            result = "✅ imported"
        else:
            result = "🧪 dry run"
        report = f"[link]({o.report_url})" if o.report_url else ""
        rows.append(f"| {o.character.label} | {result.replace('|', '/')} | {report} |")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("## WoWAudit wishlist update\n\n" + "\n".join(rows) + "\n")


async def run(args: argparse.Namespace) -> int:
    config = Config.load(args.config)
    characters = select_characters(config, args.character)
    secrets = Secrets.from_env()
    if not args.dry_run:
        secrets.require("wowaudit_api_key")

    simc_override = None
    if args.simc_file is not None:
        if len(characters) != 1:
            raise ConfigError("--simc-file needs exactly one character; pass --character")
        simc_override = (
            sys.stdin.read() if str(args.simc_file) == "-" else args.simc_file.read_text()
        )

    generate, close = await _playwright_report_generator(args.headed)
    try:
        outcomes = [
            await process_character(
                c,
                config=config,
                secrets=secrets,
                simc_override=simc_override,
                generate_report=generate,
                dry_run=args.dry_run,
            )
            for c in characters
        ]
    finally:
        await close()

    write_step_summary(outcomes)
    for o in outcomes:
        status = o.error or o.skipped or ("imported" if o.uploaded else "dry run")
        print(f"{o.character.label}: {status} {o.report_url or ''}".rstrip())
    return 1 if any(o.error for o in outcomes) else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
