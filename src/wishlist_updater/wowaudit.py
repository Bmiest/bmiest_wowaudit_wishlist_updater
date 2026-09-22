"""Upload QE Live / Raidbots reports to a WoWAudit team wishlist.

API: POST https://wowaudit.com/v1/wishlists, authenticated with the team API key
(WoWAudit team settings -> API). The key is sent as the raw Authorization header
value, matching WoWAudit's docs and existing clients.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

WISHLISTS_URL = "https://wowaudit.com/v1/wishlists"

_QE_REPORT_RE = re.compile(r"questionablyepic\.com/live/upgradereport/([A-Za-z0-9_-]+)")
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class WowAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadOptions:
    configuration_name: str = "Single Target"
    replace_manual_edits: bool = True
    clear_conduits: bool = True


DEFAULT_UPLOAD_OPTIONS = UploadOptions()


def report_id_from_url(report: str) -> str:
    """Accept a full QE Live report URL or a bare report ID and return the ID."""
    report = report.strip()
    if m := _QE_REPORT_RE.search(report):
        return m.group(1)
    if _BARE_ID_RE.match(report):
        return report
    raise WowAuditError(f"Not a QE Live report URL or ID: {report!r}")


def _error_messages(body: object) -> list[str]:
    # WoWAudit reports errors under "base", "error", or (per a known bug) "error:".
    if not isinstance(body, dict):
        return [str(body)]
    for key in ("base", "error", "error:", "message"):
        value = body.get(key)
        if value:
            return [str(v) for v in value] if isinstance(value, list) else [str(value)]
    return [str(body)]


async def upload_report(
    report: str,
    api_key: str,
    *,
    character_name: str | None = None,
    options: UploadOptions = DEFAULT_UPLOAD_OPTIONS,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Import a report into the team's wishlists. Raises WowAuditError unless created."""
    payload: dict[str, object] = {
        "report_id": report_id_from_url(report),
        "configuration_name": options.configuration_name,
        "replace_manual_edits": options.replace_manual_edits,
        "clear_conduits": options.clear_conduits,
    }
    if character_name:
        payload["character_name"] = character_name
    headers = {"Authorization": api_key, "Accept": "application/json"}

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=60)
    try:
        resp = await client.post(WISHLISTS_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        # str(exc) never includes request headers, so the key can't leak here.
        raise WowAuditError(f"WoWAudit request failed: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    try:
        body = resp.json()
    except ValueError:
        body = resp.text[:500]

    if resp.status_code in (401, 403):
        raise WowAuditError(f"WoWAudit rejected the API key (HTTP {resp.status_code})")
    if resp.is_success and isinstance(body, dict) and body.get("created") is True:
        return body
    raise WowAuditError(
        f"WoWAudit did not import report {payload['report_id']} "
        f"(HTTP {resp.status_code}): {'; '.join(_error_messages(body))}"
    )
