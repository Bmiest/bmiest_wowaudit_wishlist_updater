import json

import httpx
import pytest

from wishlist_updater.wowaudit import (
    WISHLISTS_URL,
    WowAuditError,
    report_id_from_url,
    upload_report,
)

REPORT_URL = "https://questionablyepic.com/live/upgradereport/aB3dE5fG7h"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "value, expected",
    [
        (REPORT_URL, "aB3dE5fG7h"),
        (REPORT_URL + "?foo=bar", "aB3dE5fG7h"),
        ("  aB3dE5fG7h\n", "aB3dE5fG7h"),
    ],
)
def test_report_id_from_url(value, expected):
    assert report_id_from_url(value) == expected


@pytest.mark.parametrize("value", ["https://example.com/x/y", "not a report!", ""])
def test_report_id_from_url_rejects_garbage(value):
    with pytest.raises(WowAuditError):
        report_id_from_url(value)


async def test_upload_sends_expected_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"created": True})

    async with _client(handler) as client:
        result = await upload_report(
            REPORT_URL, "secret-key", character_name="Shiftheal", client=client
        )

    assert result == {"created": True}
    assert seen["url"] == WISHLISTS_URL
    assert seen["auth"] == "secret-key"
    assert seen["body"] == {
        "report_id": "aB3dE5fG7h",
        "configuration_name": "Single Target",
        "replace_manual_edits": True,
        "clear_conduits": True,
        "character_name": "Shiftheal",
    }


@pytest.mark.parametrize(
    "body, fragment",
    [
        ({"created": False, "base": ["Report not found"]}, "Report not found"),
        ({"created": False, "error": "Character not in team"}, "Character not in team"),
        ({"created": False, "error:": "Weird key"}, "Weird key"),
    ],
)
async def test_upload_surfaces_api_errors(body, fragment):
    async with _client(lambda r: httpx.Response(200, json=body)) as client:
        with pytest.raises(WowAuditError, match=fragment):
            await upload_report(REPORT_URL, "k", client=client)


async def test_upload_bad_key_does_not_leak_key():
    async with _client(lambda r: httpx.Response(401, json={"error": "nope"})) as client:
        with pytest.raises(WowAuditError) as exc:
            await upload_report(REPORT_URL, "super-secret-key", client=client)
    assert "super-secret-key" not in str(exc.value)
    assert "401" in str(exc.value)
