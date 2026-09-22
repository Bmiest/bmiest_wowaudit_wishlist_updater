"""The user's own WoWAudit login session, for importing reports without a team API key.

The session is a Playwright storage state restricted to wowaudit.com. It grants the same
access as being logged in as the user, so it's written with owner-only permissions and in
CI is only ever read from the WOWAUDIT_SESSION secret.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
from pathlib import Path

WOWAUDIT_URL = "https://wowaudit.com/"
SESSION_COOKIE = "_user_session"
DEFAULT_SESSION_PATH = Path("~/.config/wishlist-updater/wowaudit-session.json").expanduser()


class WowAuditSessionError(RuntimeError):
    pass


def _is_wowaudit(domain_or_origin: str) -> bool:
    host = domain_or_origin.split("://")[-1].split("/")[0].lstrip(".")
    return host == "wowaudit.com" or host.endswith(".wowaudit.com")


def restrict_to_wowaudit(state: dict) -> dict:
    """Drop cookies and storage for every site except wowaudit.com (e.g. Battle.net's)."""
    return {
        "cookies": [c for c in state.get("cookies", []) if _is_wowaudit(c.get("domain", ""))],
        "origins": [o for o in state.get("origins", []) if _is_wowaudit(o.get("origin", ""))],
    }


def state_from_cookie_value(value: str) -> dict:
    """Build a storage state from a `_user_session` value copied out of a normal browser."""
    return {
        "cookies": [
            {
                "name": SESSION_COOKIE,
                "value": value.strip(),
                "domain": ".wowaudit.com",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }


def write_session(state: dict, path: Path = DEFAULT_SESSION_PATH) -> Path:
    state = restrict_to_wowaudit(state)
    if not any(c["name"] == SESSION_COOKIE for c in state["cookies"]):
        raise WowAuditSessionError(f"No {SESSION_COOKIE} cookie for wowaudit.com; not logged in?")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.chmod(path, 0o600)  # in case the file already existed with wider permissions
    return path


def load_session() -> dict | None:
    """WOWAUDIT_SESSION (JSON, as stored in the GitHub secret) or WOWAUDIT_SESSION_FILE."""
    raw = os.environ.get("WOWAUDIT_SESSION")
    if not raw and (file := os.environ.get("WOWAUDIT_SESSION_FILE")):
        raw = Path(file).expanduser().read_text(encoding="utf-8")
    if not raw:
        return None
    try:
        state = json.loads(raw)
    except ValueError:
        # Never echo the value (JSONDecodeError keeps the raw document): it's a live login.
        raise WowAuditSessionError("WOWAUDIT_SESSION is not valid JSON") from None
    return restrict_to_wowaudit(state)


async def capture_session_interactively(path: Path = DEFAULT_SESSION_PATH) -> Path:
    """Open a real browser window, let the user log in, then save the wowaudit.com session."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(WOWAUDIT_URL)
        await asyncio.to_thread(
            input,
            "\nLog in to WoWAudit in the browser window that just opened.\n"
            "Once you can see your guild while logged in, come back here and press Enter... ",
        )
        state = await context.storage_state()
        await browser.close()
    return write_session(state, path)


def capture_session_from_cookie(path: Path = DEFAULT_SESSION_PATH) -> Path:
    """Fallback if logging in inside the automated browser doesn't work."""
    value = getpass.getpass(
        "In your normal browser, logged in to wowaudit.com: DevTools > Application > Cookies >\n"
        f"https://wowaudit.com > copy the value of '{SESSION_COOKIE}'. Paste it (hidden): "
    )
    if not value.strip():
        raise WowAuditSessionError("No cookie value entered")
    return write_session(state_from_cookie_value(value), path)
