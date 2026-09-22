"""Drive QE Live's Upgrade Finder headlessly and return the shareable report URL.

QE Live (https://github.com/Voulk/QuestionablyEpic) is a client-side React app: the Upgrade
Finder runs in the browser, the report ID is generated client-side, and the report is saved with
a fire-and-forget ``no-cors`` POST to ``addUpgradeReport.php``. The app navigates to the report
page whether or not that save succeeded, so we never trust the page URL alone. Instead we capture
the save request, check that the settings QE actually used match what was asked for, and poll
``getUpgradeReport.php`` until the report can be read back.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Page, Request, expect

log = logging.getLogger(__name__)

QE_LIVE_URL = "https://questionablyepic.com/live"
UPGRADE_FINDER_URL = f"{QE_LIVE_URL}/upgradefinder"
REPORT_URL_PREFIX = f"{QE_LIVE_URL}/upgradereport/"
SAVE_REPORT_ENDPOINT = "https://questionablyepic.com/api/addUpgradeReport.php"
GET_REPORT_ENDPOINT = "https://questionablyepic.com/api/getUpgradeReport.php"

DEFAULT_TIMEOUT_MS = 30_000
# The Upgrade Finder runs synchronously on the page's main thread; give it plenty of room.
FINDER_TIMEOUT_MS = 180_000
REPORT_SAVE_TIMEOUT_S = 60.0
REPORT_POLL_INTERVAL_S = 2.0
DEFAULT_ARTIFACTS_DIR = Path("screenshots")

# QE rejects SimC strings of 1000+ lines, and only looks for the class line in the first 8.
QE_MAX_SIMC_LINES = 1000
QE_CLASS_LINE_WINDOW = 8

# (SimC class, SimC spec) -> QE Live spec name. QE only supports healers.
QE_SPECS: dict[tuple[str, str], str] = {
    ("druid", "restoration"): "Restoration Druid",
    ("evoker", "preservation"): "Preservation Evoker",
    ("monk", "mistweaver"): "Mistweaver Monk",
    ("paladin", "holy"): "Holy Paladin",
    ("priest", "discipline"): "Discipline Priest",
    ("priest", "holy"): "Holy Priest",
    ("shaman", "restoration"): "Restoration Shaman",
}
SIMC_CLASSES = frozenset(
    {
        "deathknight",
        "demonhunter",
        "druid",
        "evoker",
        "hunter",
        "mage",
        "monk",
        "paladin",
        "priest",
        "rogue",
        "shaman",
        "warlock",
        "warrior",
    }
)

_IMPORT_GEAR_TEXT = re.compile(r"^\s*import gear\s*$", re.IGNORECASE)
_GO_TEXT = re.compile(r"^\s*go!?\s*$", re.IGNORECASE)
_MPLUS_LABEL = re.compile(r"^(?:M|\+)(\d+)(?:/(\d+))?$")
_IMPORT_STATUS_TEXT = re.compile(r"^Import - ")
_REPORT_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class QEError(RuntimeError):
    """QE Live could not produce a saved upgrade report."""


@dataclass(frozen=True)
class QESettings:
    """Upgrade Finder settings. Defaults are the user's chosen settings.

    Button and slider values are matched against the labels QE shows (e.g. "Mythic", "+10",
    "331"). The optional settings take None to leave QE's own default untouched.
    """

    raid_difficulty: str = "Mythic"
    mplus_level: int = 10
    crafted_ilvl: int = 331
    catalyst_limit: int = 4
    show_percent_upgrade: bool = True
    auto_gem: bool = False  # QE's "Auto-add Sockets"; the guild requires sims without sockets
    crafted_stats: str | None = None  # e.g. "Crit / Haste"; None keeps QE's default
    ally_buffs_scaling: int | None = 75
    cosmic_crescendo: int | None = 75
    volatile_void_suffuser: int | None = 85
    trappings_uptime: int | None = 60


@dataclass(frozen=True)
class SimcIdentity:
    """Who a SimC string belongs to, as QE Live will read it."""

    name: str | None  # QE takes the character name from the "# Name - Spec - ..." header line
    simc_class: str
    simc_spec: str
    qe_spec: str
    simc: str  # normalized string that gets pasted into QE


def normalize_simc(simc: str) -> str:
    """Normalize line endings and leading whitespace the way QE's parser needs.

    QE splits on "\\n" and matches whole lines like "### Weekly Reward Choices", so CRLF input
    silently drops the vault section. It also reads the character name from line 0.
    """
    return simc.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def parse_simc_identity(simc: str) -> SimcIdentity:
    """Validate a SimC string against QE Live's import rules, before a browser is involved."""
    normalized = normalize_simc(simc)
    lines = normalized.split("\n")
    if len(lines) >= QE_MAX_SIMC_LINES:
        raise QEError(f"SimC string has {len(lines)} lines; QE rejects {QE_MAX_SIMC_LINES}+")

    simc_class = None
    for line in lines[:QE_CLASS_LINE_WINDOW]:
        key = line.split("=", 1)[0].strip().lower()
        if "=" in line and key in SIMC_CLASSES:
            simc_class = key
            break
    if simc_class is None:
        raise QEError(
            f'No class line (e.g. priest="Name") in the first {QE_CLASS_LINE_WINDOW} lines '
            "of the SimC string; QE Live rejects it otherwise"
        )

    simc_spec = next(
        (line.split("=", 1)[1].strip().lower() for line in lines if line.startswith("spec=")),
        None,
    )
    if simc_spec is None:
        raise QEError("SimC string has no spec= line")

    qe_spec = QE_SPECS.get((simc_class, simc_spec))
    if qe_spec is None:
        raise QEError(f"QE Live only supports healer specs, not {simc_spec} {simc_class}")

    # Mirrors QE's own parsing: lines[0].split("-")[0].replace("#", "").trim()
    name = None
    if lines[0].startswith("#"):
        name = lines[0].split("-", 1)[0].replace("#", "").strip() or None
    if name is None:
        log.warning(
            "SimC string has no '# Name - Spec - ...' header line; "
            "QE will save the report under a placeholder character name"
        )

    return SimcIdentity(name, simc_class, simc_spec, qe_spec, normalized)


def mplus_label_levels(label: str) -> set[int]:
    """Key levels covered by a QE M+ button label: "M0" -> {0}, "+8/9" -> {8, 9}."""
    match = _MPLUS_LABEL.match(label.strip())
    if not match:
        return set()
    return {int(group) for group in match.groups() if group is not None}


def check_saved_report(
    payload: dict[str, Any],
    *,
    qe_spec: str,
    raid_index: int,
    mplus_index: int,
    crafted_index: int,
    auto_gem: bool,
) -> str:
    """Check the report QE posted to its backend and return its ID.

    The payload's ufSettings and autoGem are what the finder actually ran with, so this catches
    UI changes that make a click silently do nothing.
    """
    report_id = payload.get("id")
    if not isinstance(report_id, str) or not _REPORT_ID.match(report_id):
        raise QEError(f"QE posted a report with an unexpected id: {report_id!r}")
    if payload.get("spec") != qe_spec:
        raise QEError(f"QE saved a {payload.get('spec')} report, expected {qe_spec}")

    uf = payload.get("ufSettings") or {}
    expected = {"raid": [raid_index], "dungeon": mplus_index, "craftedLevel": crafted_index}
    actual = {key: uf.get(key) for key in expected}
    if actual != expected:
        raise QEError(f"QE ran with settings {actual}, expected {expected}")
    if payload.get("autoGem") != auto_gem:
        raise QEError(f"QE ran with autoGem={payload.get('autoGem')!r}, expected {auto_gem}")

    if not payload.get("results"):
        raise QEError("QE saved a report with no upgrade results")
    return report_id


async def generate_upgrade_report(
    page: Page,
    simc: str,
    settings: QESettings,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    artifacts_dir: Path | None = DEFAULT_ARTIFACTS_DIR,
) -> str:
    """Import simc into QE Live, apply settings, run the Upgrade Finder,
    and return the absolute https://questionablyepic.com/live/upgradereport/<id> URL.

    Raises QEError on failure. When artifacts_dir is set, a screenshot, the page HTML and a log
    are saved there first so CI failures can be debugged from the uploaded artifacts.
    """
    identity = parse_simc_identity(simc)
    run = _Run(page, timeout_ms)
    page.on("pageerror", run.on_page_error)
    page.on("console", run.on_console)
    try:
        run.step = "opening the Upgrade Finder"
        await run.open_upgrade_finder()

        run.step = f"selecting spec {identity.qe_spec}"
        await run.select_spec(identity.qe_spec)

        run.step = "importing the SimC string"
        await run.import_simc(identity.simc)

        run.step = "applying Upgrade Finder settings"
        raid_index = await run.pick_raid_difficulty(settings.raid_difficulty)
        mplus_index = await run.pick_mplus_level(settings.mplus_level)
        crafted_index = await run.pick_crafted_ilvl(settings.crafted_ilvl)
        if settings.crafted_stats is not None:
            await run.pick_crafted_stats(settings.crafted_stats)

        run.step = "applying optional settings"
        await run.apply_optional_settings(settings)

        run.step = "running the Upgrade Finder"
        payload = await run.run_finder()
        report_id = check_saved_report(
            payload,
            qe_spec=identity.qe_spec,
            raid_index=raid_index,
            mplus_index=mplus_index,
            crafted_index=crafted_index,
            auto_gem=settings.auto_gem,
        )

        run.step = f"confirming report {report_id} was saved"
        await run.wait_until_report_saved(report_id)
    except Exception as exc:
        if artifacts_dir is not None:
            await run.dump_artifacts(artifacts_dir, exc)
        raise QEError(f"QE Live failed while {run.step}: {exc}") from exc
    finally:
        page.remove_listener("pageerror", run.on_page_error)
        page.remove_listener("console", run.on_console)

    report_url = REPORT_URL_PREFIX + report_id
    log.info("QE Live upgrade report for %s: %s", identity.name or identity.qe_spec, report_url)
    return report_url


class _Run:
    """One pass through the Upgrade Finder, with the state needed for error reports."""

    def __init__(self, page: Page, timeout_ms: int) -> None:
        self.page = page
        self.timeout = timeout_ms
        self.step = "starting"
        self.page_errors: list[str] = []

    def on_page_error(self, error: Exception) -> None:
        self.page_errors.append(f"pageerror: {error}")

    def on_console(self, message: Any) -> None:
        if message.type == "error":
            self.page_errors.append(f"console.error: {message.text}")

    async def open_upgrade_finder(self) -> None:
        # Setting labels are matched in English, so pin the language before the app boots.
        await self.page.add_init_script(
            "try { localStorage.setItem('lang', '\"en\"');"
            " localStorage.setItem('i18nextLng', 'en'); } catch (e) {}"
        )
        await self.page.goto(
            UPGRADE_FINDER_URL, wait_until="domcontentloaded", timeout=self.timeout
        )
        await expect(self._spec_select()).to_be_visible(timeout=self.timeout)

    async def select_spec(self, qe_spec: str) -> None:
        spec_select = self._spec_select()
        if (await spec_select.inner_text()).strip() == qe_spec:
            return
        await spec_select.click(timeout=self.timeout)
        option = self.page.get_by_role("option").filter(
            has_text=re.compile(rf"^\s*{re.escape(qe_spec)}\s*$")
        )
        await option.click(timeout=self.timeout)
        await expect(spec_select).to_have_text(qe_spec, timeout=self.timeout)

    async def import_simc(self, simc: str) -> None:
        import_button = self.page.get_by_role("button").filter(has_text=_IMPORT_GEAR_TEXT).first
        await import_button.click(timeout=self.timeout)
        entry = self.page.locator("textarea#simcentry")
        await entry.fill(simc, timeout=self.timeout)
        dialog = self.page.get_by_role("dialog").filter(has=entry)
        await dialog.get_by_role("button", name="Submit", exact=True).click(timeout=self.timeout)

        # On success QE closes the dialog; on a validation failure it fills #SimCError.
        outcome = await self.page.wait_for_function(
            """() => {
                if (!document.querySelector('#simcentry')) return 'ok';
                const error = document.querySelector('#SimCError');
                const text = error && error.textContent.trim();
                return text ? 'error: ' + text : false;
            }""",
            timeout=self.timeout,
        )
        result = await outcome.json_value()
        if result != "ok":
            raise QEError(f"QE rejected the SimC string ({result})")

        # GO stays disabled until QE considers the gear complete ("Import - All Set!").
        try:
            await expect(self._go_button()).to_be_enabled(timeout=self.timeout)
        except AssertionError as exc:
            status = await self.page.get_by_text(_IMPORT_STATUS_TEXT).all_inner_texts()
            raise QEError(f"GO stayed disabled after import; QE status: {status}") from exc

    async def pick_raid_difficulty(self, label: str) -> int:
        buttons = self._section("Raid Difficulty").get_by_role("button")
        labels = [text.strip() for text in await buttons.all_inner_texts()]
        if label not in labels:
            raise QEError(f"No raid difficulty {label!r}; QE offers {labels}")
        index = labels.index(label)
        await self._press_toggle(buttons.nth(index))
        return index

    async def pick_mplus_level(self, level: int) -> int:
        buttons = self._section("Mythic+ Key Level").get_by_role("button")
        labels = [text.strip() for text in await buttons.all_inner_texts()]
        matches = [i for i, label in enumerate(labels) if level in mplus_label_levels(label)]
        if len(matches) != 1:
            raise QEError(f"No single M+ key level button for +{level}; QE offers {labels}")
        await self._press_toggle(buttons.nth(matches[0]))
        return matches[0]

    async def pick_crafted_ilvl(self, ilvl: int) -> int:
        section = self._section("Crafted Gear")
        labels = [
            text.strip() for text in await section.locator(".MuiSlider-markLabel").all_inner_texts()
        ]
        if str(ilvl) not in labels:
            raise QEError(f"No crafted item level {ilvl}; QE offers {labels}")
        target = labels.index(str(ilvl))

        # The slider snaps between marks (step=null), so each arrow press moves one mark.
        slider = section.get_by_role("slider")
        current = int(await slider.get_attribute("aria-valuenow", timeout=self.timeout) or 0)
        key = "ArrowRight" if target > current else "ArrowLeft"
        for _ in range(abs(target - current)):
            await slider.press(key, timeout=self.timeout)
        await expect(slider).to_have_attribute("aria-valuenow", str(target), timeout=self.timeout)
        return target

    async def pick_crafted_stats(self, stats: str) -> None:
        await self._choose(self._section("Crafted Gear"), "Secondaries", stats)

    async def apply_optional_settings(self, settings: QESettings) -> None:
        # QE reuses the id "panel1c-header" for other accordions, so match on the title too.
        header = self.page.locator("#panel1c-header").filter(has_text="Optional Settings")
        if await header.get_attribute("aria-expanded", timeout=self.timeout) != "true":
            await header.click(timeout=self.timeout)
        await expect(header).to_have_attribute("aria-expanded", "true", timeout=self.timeout)
        panel = self.page.locator(".MuiAccordion-root").filter(has=header)

        metric = "Show % Upgrade" if settings.show_percent_upgrade else "Show HPS"
        await self._choose(panel, "Upgrade Finder", metric)
        await self._choose(panel, "Catalyst Limit", str(settings.catalyst_limit))
        await self._choose(panel, "Auto-add Sockets", "true" if settings.auto_gem else "false")

        entries = {
            "Ally Buffs Scaling": settings.ally_buffs_scaling,
            "Cosmic Crescendo": settings.cosmic_crescendo,
            "Volatile Void Suffuser": settings.volatile_void_suffuser,
            "Trappings Uptime": settings.trappings_uptime,
        }
        for title, value in entries.items():
            if value is None:
                continue
            field = panel.get_by_label(title, exact=True)
            await field.fill(str(value), timeout=self.timeout)
            await expect(field).to_have_value(str(value), timeout=self.timeout)

    async def run_finder(self) -> dict[str, Any]:
        """Click GO and return the report payload QE posts to its backend."""
        go = self._go_button()
        async with self.page.expect_request(_is_save_request, timeout=FINDER_TIMEOUT_MS) as info:
            await go.click(timeout=self.timeout)
        request = await info.value

        response = await request.response()
        if response is None:
            raise QEError(f"Saving the report failed: {request.failure or 'no response'}")
        if not response.ok:
            raise QEError(f"Saving the report failed: HTTP {response.status}")

        try:
            payload = request.post_data_json
        except ValueError as exc:
            raise QEError("QE posted a report that isn't JSON") from exc
        if not isinstance(payload, dict):
            raise QEError("QE posted an empty or malformed report")
        return payload

    async def wait_until_report_saved(self, report_id: str) -> None:
        """Poll QE's backend until the report reads back; WoWAudit fetches it from there."""
        deadline = time.monotonic() + REPORT_SAVE_TIMEOUT_S
        last_seen = "no response"
        while True:
            response = await self.page.request.get(
                GET_REPORT_ENDPOINT, params={"reportID": report_id}, timeout=self.timeout
            )
            if response.ok:
                data = await response.json()
                # A saved report comes back as a JSON-encoded string; a miss as {"status": ...}.
                if isinstance(data, str):
                    report = json.loads(data)
                    if isinstance(report, dict) and report.get("id") == report_id:
                        return
                last_seen = str(data)[:200]
            else:
                last_seen = f"HTTP {response.status}"
            if time.monotonic() >= deadline:
                raise QEError(
                    f"Report {report_id} was not readable after {REPORT_SAVE_TIMEOUT_S:.0f}s "
                    f"(last response: {last_seen})"
                )
            await asyncio.sleep(REPORT_POLL_INTERVAL_S)

    async def dump_artifacts(self, artifacts_dir: Path, exc: BaseException) -> None:
        """Save a screenshot, the page HTML and a log. Never masks the original error."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-z0-9]+", "-", self.step.lower()).strip("-")
        stem = artifacts_dir / f"qe-{stamp}-{slug}"
        try:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            details = [
                f"step: {self.step}",
                f"url: {self.page.url}",
                f"error: {exc!r}",
                *self.page_errors,
            ]
            stem.with_suffix(".log").write_text("\n".join(details) + "\n")
            stem.with_suffix(".html").write_text(await self.page.content())
            await self.page.screenshot(path=stem.with_suffix(".png"), full_page=True)
            log.error("QE Live failure artifacts saved to %s.*", stem)
        except Exception:
            log.exception("Could not save QE Live failure artifacts to %s", artifacts_dir)

    def _spec_select(self):
        # The open menu's listbox shares the aria-labelledby, so pin the trigger element.
        return self.page.locator('[aria-haspopup="listbox"][aria-labelledby~="class-select-label"]')

    def _go_button(self):
        return self.page.get_by_role("button", name=_GO_TEXT)

    def _section(self, heading: str):
        """The card (MUI Paper) that holds the given Upgrade Finder heading."""
        return self.page.get_by_text(heading, exact=True).locator(
            "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '),"
            " ' MuiPaper-root ')][1]"
        )

    async def _press_toggle(self, button) -> None:
        if await button.get_attribute("aria-pressed", timeout=self.timeout) != "true":
            await button.click(timeout=self.timeout)
        await expect(button).to_have_attribute("aria-pressed", "true", timeout=self.timeout)

    async def _choose(self, scope, label: str, option: str) -> None:
        """Pick an option in an MUI select (a TextField with select)."""
        # Found via its <label> because the trigger's role differs between MUI versions
        # (button in older ones, combobox in newer ones).
        field_label = self.page.locator("label").filter(
            has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
        )
        select = (
            scope.locator(".MuiFormControl-root")
            .filter(has=field_label)
            .locator('[aria-haspopup="listbox"]')
        )
        if (await select.inner_text(timeout=self.timeout)).strip() == option:
            return
        await select.click(timeout=self.timeout)
        listbox = self.page.get_by_role("listbox")
        await listbox.get_by_role("option", name=option, exact=True).click(timeout=self.timeout)
        await expect(select).to_have_text(option, timeout=self.timeout)


def _is_save_request(request: Request) -> bool:
    return request.method == "POST" and request.url.startswith(SAVE_REPORT_ENDPOINT)
