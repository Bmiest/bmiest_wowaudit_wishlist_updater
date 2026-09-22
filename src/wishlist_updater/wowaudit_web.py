"""Import a QE Live report into a WoWAudit wishlist with the user's own login session.

This makes the same calls as the "Go" button on WoWAudit's wishlist page, as read from WoWAudit's
frontend bundle: a JSON PUT to /api/teams/<team>/character_wishlists/<character> carrying the page's
CSRF token, then polling /api/jobs/<job> until the import finishes. Everything goes through
context.request, which shares the context's session cookies, so no page is needed.

The session is a live login to the user's account. Cookies and the CSRF token never go into log
lines or exception messages, redirects are never followed, and requests only go to wowaudit.com.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from playwright.async_api import APIRequestContext, BrowserContext
from playwright.async_api import Error as PlaywrightError

log = logging.getLogger(__name__)

WOWAUDIT_ORIGIN = "https://wowaudit.com"
RELOGIN_HINT = "Run `wishlist-updater --wowaudit-login` again to refresh the WoWAudit session."

REQUEST_TIMEOUT_MS = 30_000
JOB_TIMEOUT_S = 180.0
JOB_POLL_INTERVAL_S = 1.0  # what WoWAudit's own frontend uses
# WoWAudit's upload form has "replace manual edits" ticked by default.
REPLACE_MANUAL_EDITS = True

_API_HEADERS = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
_CSRF_META = re.compile(
    r'<meta\s+(?:name="csrf-token"\s+content="([^"]+)"|content="([^"]+)"\s+name="csrf-token")'
)
_QE_REPORT_URL = re.compile(
    r"^https://(?:www\.)?questionablyepic\.com/live/upgradereport/([A-Za-z0-9_-]+)/?$"
)
_PENDING_JOB_STATES = frozenset({"queued", "working"})
_FAILED_JOB_STATES = frozenset({"failed", "interrupted"})


class WowAuditWebError(RuntimeError):
    """The report could not be imported into WoWAudit."""


class WowAuditSessionExpired(WowAuditWebError):
    """The saved WoWAudit login no longer works."""


@dataclass(frozen=True)
class UploadTarget:
    """Where a report goes, resolved with read-only requests."""

    team_id: int
    character_id: int
    character_name: str
    configuration_id: int
    season_id: int


def qe_report_id(report_url: str) -> str:
    """The bare report ID WoWAudit expects, e.g. "lcxtxzulnhiq"."""
    match = _QE_REPORT_URL.match(report_url.strip())
    if not match:
        raise WowAuditWebError(f"Not a QE Live upgrade report URL: {report_url!r}")
    return match.group(1)


def find_team_id(user: dict[str, Any], team_url: str) -> int:
    wanted = _normalize_url(team_url)
    for team in user.get("teamReferences") or []:
        if _normalize_url(team.get("fullUrl") or "") == wanted:
            return int(team["id"])
    raise WowAuditWebError(f"The logged-in WoWAudit user is not a member of {team_url}")


def find_character(team: dict[str, Any], user_id: int, character_name: str) -> dict[str, Any]:
    """The team member entry for one of the user's own characters, checked against the rules
    WoWAudit's upload form enforces."""
    settings = team.get("settings") or {}
    if (settings.get("wishlistLocked") or {}).get("value") is True:
        raise WowAuditWebError("The team has locked wishlists, so reports can't be uploaded")

    wanted = character_name.casefold()
    members = [
        member
        for member in team.get("members") or []
        if ((member.get("characterReference") or {}).get("name") or "").casefold() == wanted
    ]
    if not members:
        raise WowAuditWebError(f"{character_name} is not in team {team.get('name', '?')}")
    if len(members) > 1:
        raise WowAuditWebError(f"More than one character named {character_name} in the team")

    member = members[0]
    if member["characterReference"].get("userId") != user_id:
        raise WowAuditWebError(
            f"{character_name} belongs to another WoWAudit user; "
            "only upload for your own characters"
        )
    if not (member.get("teamRank") or {}).get("wishlist_visibility"):
        raise WowAuditWebError(f"{character_name}'s team rank has no wishlist")
    return member


def extract_csrf_token(html: str) -> str:
    match = _CSRF_META.search(html)
    if not match:
        raise WowAuditWebError("No CSRF token on the WoWAudit characters page")
    return match.group(1) or match.group(2)


def job_result(job: dict[str, Any]) -> dict[str, Any] | None:
    """A finished import job's content, or None while the job is still running."""
    status = job.get("status")
    if status in _PENDING_JOB_STATES:
        return None
    if job.get("error"):
        raise WowAuditWebError(f"WoWAudit could not import the report: {job['error']}")
    if status in _FAILED_JOB_STATES:
        raise WowAuditWebError(f"WoWAudit's import job {status} without giving a reason")
    content = job.get("content")
    if isinstance(content, str):
        content = json.loads(content)
    if not isinstance(content, dict) or not content.get("teamsUploaded"):
        raise WowAuditWebError(f"WoWAudit's import job ended ({status}) without uploading anything")
    return content


def report_on_wishlist(wishlist: dict[str, Any], report_id: str) -> bool:
    """Whether any wish on the character's wishlist came from the given QE report."""
    for item in wishlist.get("items") or []:
        for wish in item.get("wishes") or []:
            match = _QE_REPORT_URL.match(wish.get("report_url") or "")
            if match and match.group(1) == report_id:
                return True
    return False


async def resolve_upload_target(
    api: APIRequestContext, *, team_url: str, character_name: str
) -> UploadTarget:
    """Look up the team, character and configuration an upload would use. Read-only."""
    page_info = await _request(api, "GET", "/api/user/page_info")
    user = page_info.get("user")
    if not user:
        raise WowAuditSessionExpired(f"Not logged in to WoWAudit. {RELOGIN_HINT}")

    team_id = find_team_id(user, team_url)
    # The team payload also carries admin-only fields (API keys). Keep only what the upload
    # form checks and drop the rest immediately.
    team = _upload_view(await _request(api, "GET", f"/api/teams/{team_id}"))
    member = find_character(team, user["id"], character_name)

    configurations = await _request(api, "GET", f"/api/teams/{team_id}/droptimizer_configurations")
    if not configurations:
        raise WowAuditWebError("The team has no droptimizer configuration to upload into")

    return UploadTarget(
        team_id=team_id,
        character_id=int(member["characterReference"]["id"]),
        character_name=member["characterReference"]["name"],
        # WoWAudit's upload form defaults to the team's first configuration.
        configuration_id=int(configurations[0]["id"]),
        season_id=int(page_info["currentSeason"]["id"]),
    )


async def upload_report_via_web(
    context: BrowserContext, report_url: str, *, team_url: str, character_name: str
) -> None:
    """Import the QE report into character_name's wishlist in the team at team_url, and verify
    that the wishlist now contains it.

    The context must carry the user's WoWAudit session (storage_state). Raises
    WowAuditSessionExpired if the session no longer works, and WowAuditWebError on any other
    failure.
    """
    report_id = qe_report_id(report_url)
    if not _normalize_url(team_url).startswith(WOWAUDIT_ORIGIN + "/"):
        raise WowAuditWebError(f"Not a WoWAudit team URL: {team_url!r}")

    api = context.request
    step = "looking up the team and character"
    csrf_token = None
    try:
        target = await resolve_upload_target(api, team_url=team_url, character_name=character_name)

        step = "getting a CSRF token"
        page = await _request(api, "GET", _team_path(team_url) + "/loot/characters", text=True)
        if "Log in to continue" in page:
            raise WowAuditSessionExpired(f"Not logged in to WoWAudit. {RELOGIN_HINT}")
        csrf_token = extract_csrf_token(page)

        step = "uploading the report"
        wishlist_path = f"/api/teams/{target.team_id}/character_wishlists/{target.character_id}"
        started = await _request(
            api,
            "PUT",
            wishlist_path,
            body={
                "report_id": report_id,
                "droptimizer_configuration_id": target.configuration_id,
                "replace_manual_edits": REPLACE_MANUAL_EDITS,
            },
            csrf_token=csrf_token,
        )
        job_id = started.get("job_id") if isinstance(started, dict) else None
        if not job_id:
            raise WowAuditWebError("WoWAudit accepted the upload but returned no job to follow")

        step = "waiting for WoWAudit to import the report"
        result = await _wait_for_job(api, job_id)

        step = "verifying the wishlist"
        wishlist = await _request(api, "GET", f"{wishlist_path}?season_id={target.season_id}")
        if not report_on_wishlist(wishlist, report_id):
            raise WowAuditWebError(
                f"The import finished, but {target.character_name}'s wishlist has no wishes "
                f"from report {report_id}"
            )
    except WowAuditWebError as exc:
        raise type(exc)(f"WoWAudit upload failed while {step}: {exc}") from None
    except (PlaywrightError, ValueError, KeyError, TypeError) as exc:
        # Playwright's call logs can list request headers, so keep only the first part of the
        # message and never chain the original exception into tracebacks.
        detail = _redact(str(exc).split("Call log:")[0].strip(), csrf_token)
        raise WowAuditWebError(
            f"WoWAudit upload failed while {step}: {type(exc).__name__}: {detail}"
        ) from None

    teams = result["teamsUploaded"]
    log.info(
        "Imported %s into WoWAudit for %s (%d team(s))", report_id, target.character_name, teams
    )
    if teams > 1:
        # WoWAudit copies uploads to the user's other teams unless they're blacklisted.
        log.warning("WoWAudit also copied %s to %d other team(s)", report_id, teams - 1)


async def _wait_for_job(api: APIRequestContext, job_id: Any) -> dict[str, Any]:
    deadline = time.monotonic() + JOB_TIMEOUT_S
    while True:
        result = job_result(await _request(api, "GET", f"/api/jobs/{job_id}"))
        if result is not None:
            return result
        if time.monotonic() >= deadline:
            raise WowAuditWebError(
                f"WoWAudit's import job was still running after {JOB_TIMEOUT_S:.0f}s"
            )
        await asyncio.sleep(JOB_POLL_INTERVAL_S)


async def _request(
    api: APIRequestContext,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    csrf_token: str | None = None,
    text: bool = False,
) -> Any:
    # WoWAudit answers 406 to page requests that ask for JSON.
    headers = {"Accept": "text/html"} if text else dict(_API_HEADERS)
    if csrf_token is not None:
        headers["X-CSRF-Token"] = csrf_token
    response = await api.fetch(
        WOWAUDIT_ORIGIN + path,
        method=method,
        headers=headers,
        data=body,
        max_redirects=0,  # a redirect means we're logged out, and must never leave wowaudit.com
        timeout=REQUEST_TIMEOUT_MS,
    )
    status = response.status
    if status in (401, 403):
        raise WowAuditSessionExpired(f"WoWAudit answered HTTP {status}. {RELOGIN_HINT}")
    if 300 <= status < 400:
        raise WowAuditSessionExpired(f"WoWAudit redirected (HTTP {status}). {RELOGIN_HINT}")
    if not response.ok:
        raise WowAuditWebError(f"WoWAudit answered HTTP {status}{await _error_detail(response)}")
    return await response.text() if text else await response.json()


async def _error_detail(response: Any) -> str:
    """The error message from a WoWAudit JSON error body. Never the raw body."""
    try:
        body = await response.json()
    except Exception:
        return ""
    if isinstance(body, dict):
        message = body.get("message") or body.get("error") or body.get("errors")
        if message:
            return f": {str(message)[:200]}"
    return ""


def _upload_view(team: dict[str, Any]) -> dict[str, Any]:
    settings = team.get("settings") or {}
    return {
        "name": team.get("name"),
        "settings": {"wishlistLocked": settings.get("wishlistLocked")},
        "members": team.get("members") or [],
    }


def _redact(message: str, secret: str | None) -> str:
    return message.replace(secret, "[redacted]") if secret else message


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def _team_path(team_url: str) -> str:
    return _normalize_url(team_url).removeprefix(WOWAUDIT_ORIGIN)
