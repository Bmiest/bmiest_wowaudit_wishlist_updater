import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.async_api import Error as PlaywrightError

from wishlist_updater import wowaudit_web
from wishlist_updater.wowaudit_web import (
    UploadTarget,
    WowAuditSessionExpired,
    WowAuditWebError,
    extract_csrf_token,
    find_character,
    find_team_id,
    job_result,
    qe_report_id,
    report_on_wishlist,
    resolve_upload_target,
    upload_report_via_web,
)

FIXTURES = Path(__file__).parent / "fixtures" / "wowaudit"
TEAM_URL = "https://wowaudit.com/guild/eu/draenor/kelderklasse/teams/main"
REPORT_URL = "https://questionablyepic.com/live/upgradereport/lcxtxzulnhiq"
CSRF = "placeholder-csrf-token-for-tests"
WISHLIST_PATH = "/api/teams/66817/character_wishlists/4294788"


def fixture(name):
    path = FIXTURES / name
    return path.read_text() if path.suffix == ".html" else json.loads(path.read_text())


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status = status
        self.ok = 200 <= status < 300
        self._body = body

    async def json(self):
        if isinstance(self._body, str):
            raise ValueError("not JSON")
        return self._body

    async def text(self):
        return self._body if isinstance(self._body, str) else json.dumps(self._body)


class FakeAPI:
    """Routes (method, path) to canned responses; a list is served in order, the last repeating."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def fetch(self, url, *, method, headers, data, max_redirects, timeout):
        assert url.startswith("https://wowaudit.com/"), url
        assert max_redirects == 0
        path = url.removeprefix("https://wowaudit.com")
        self.calls.append(SimpleNamespace(method=method, path=path, headers=headers, data=data))
        route = self.routes[(method, path)]
        if isinstance(route, Exception):
            raise route
        if isinstance(route, list):
            return route.pop(0) if len(route) > 1 else route[0]
        return route


def happy_routes():
    return {
        ("GET", "/api/user/page_info"): FakeResponse(body=fixture("page_info.json")),
        ("GET", "/api/teams/66817"): FakeResponse(body=fixture("team.json")),
        ("GET", "/api/teams/66817/droptimizer_configurations"): FakeResponse(
            body=fixture("droptimizer_configurations.json")
        ),
        ("GET", "/guild/eu/draenor/kelderklasse/teams/main/loot/characters"): FakeResponse(
            body=fixture("characters_page.html")
        ),
        ("PUT", WISHLIST_PATH): FakeResponse(body={"job_id": "job-1"}),
        ("GET", "/api/jobs/job-1"): [
            FakeResponse(body=fixture("job_working.json")),
            FakeResponse(body=fixture("job_completed.json")),
        ],
        ("GET", f"{WISHLIST_PATH}?season_id=18"): FakeResponse(body=fixture("wishlist.json")),
    }


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(wowaudit_web, "JOB_POLL_INTERVAL_S", 0)


@pytest.fixture(autouse=True)
def empty_target_cache():
    wowaudit_web._TARGET_CACHE.clear()
    yield
    wowaudit_web._TARGET_CACHE.clear()


LOOKUPS = {
    "/api/user/page_info",
    "/api/teams/66817",
    "/api/teams/66817/droptimizer_configurations",
}


async def upload(api):
    await upload_report_via_web(
        SimpleNamespace(request=api), REPORT_URL, team_url=TEAM_URL, character_name="Shiftheal"
    )


async def test_upload_replays_wowaudits_go_button_and_verifies():
    api = FakeAPI(happy_routes())
    await upload(api)

    [put] = [call for call in api.calls if call.method == "PUT"]
    assert put.data == {
        "report_id": "lcxtxzulnhiq",
        "droptimizer_configuration_id": 65057,
        "replace_manual_edits": True,
    }
    assert put.headers["X-CSRF-Token"] == CSRF
    assert all("X-CSRF-Token" not in call.headers for call in api.calls if call.method == "GET")
    assert [call.path for call in api.calls].count("/api/jobs/job-1") == 2
    assert api.calls[-1].path == f"{WISHLIST_PATH}?season_id=18"


async def test_second_upload_reuses_the_resolved_target():
    api = FakeAPI(happy_routes())
    await upload(api)  # e.g. the Heroic report
    first = len(api.calls)
    await upload(api)  # then the Mythic one, in the same run
    second = [call.path for call in api.calls[first:]]
    assert not LOOKUPS & set(second)
    # The CSRF page (which also catches a logged-out session), PUT, job and read-back still happen.
    assert second[0].endswith("/loot/characters")
    assert [call.method for call in api.calls[first:]].count("PUT") == 1
    assert second[-1] == f"{WISHLIST_PATH}?season_id=18"


async def test_failed_upload_forgets_the_resolved_target():
    routes = happy_routes()
    routes[("GET", "/api/jobs/job-1")] = FakeResponse(body=fixture("job_failed.json"))
    api = FakeAPI(routes)
    with pytest.raises(WowAuditWebError):
        await upload(api)
    assert not wowaudit_web._TARGET_CACHE
    routes[("GET", "/api/jobs/job-1")] = FakeResponse(body=fixture("job_completed.json"))
    first = len(api.calls)
    await upload(api)
    assert {call.path for call in api.calls[first:]} >= LOOKUPS


async def test_upload_warns_when_wowaudit_copies_to_other_teams(caplog):
    await upload(FakeAPI(happy_routes()))  # job_completed.json reports teamsUploaded=2
    assert "also copied lcxtxzulnhiq to 1 other team(s)" in caplog.text


def test_team_view_drops_everything_but_members_and_the_lock():
    team = {**fixture("team.json"), "privateKey": "admin-only", "readonlyKey": "admin-only"}
    assert set(wowaudit_web._upload_view(team)) == {"name", "settings", "members"}
    assert "admin-only" not in json.dumps(wowaudit_web._upload_view(team))


async def test_upload_page_request_asks_for_html():
    api = FakeAPI(happy_routes())
    await upload(api)
    [page] = [call for call in api.calls if call.path.endswith("/loot/characters")]
    assert page.headers["Accept"] == "text/html"


async def test_resolve_upload_target():
    api = FakeAPI(happy_routes())
    target = await resolve_upload_target(api, team_url=TEAM_URL + "/", character_name="shiftheal")
    assert target == UploadTarget(66817, 4294788, "Shiftheal", 65057, 18)
    assert {call.method for call in api.calls} == {"GET"}


@pytest.mark.parametrize(
    "route, response",
    [
        (("GET", "/api/user/page_info"), FakeResponse(body={"user": None, "currentSeason": {}})),
        (("GET", "/api/teams/66817"), FakeResponse(status=401, body={"error": "unauthorized"})),
        (("PUT", WISHLIST_PATH), FakeResponse(status=403)),
        (("GET", "/api/jobs/job-1"), FakeResponse(status=302)),
        (
            ("GET", "/guild/eu/draenor/kelderklasse/teams/main/loot/characters"),
            FakeResponse(body="<html><p>Log in to continue</p></html>"),
        ),
    ],
)
async def test_logged_out_raises_session_expired(route, response):
    routes = happy_routes()
    routes[route] = response
    with pytest.raises(WowAuditSessionExpired, match="--wowaudit-login"):
        await upload(FakeAPI(routes))


async def test_failed_job_reports_wowaudits_error_and_the_step():
    routes = happy_routes()
    routes[("GET", "/api/jobs/job-1")] = FakeResponse(body=fixture("job_failed.json"))
    with pytest.raises(WowAuditWebError, match="while waiting.*different character"):
        await upload(FakeAPI(routes))


async def test_job_that_never_finishes_times_out(monkeypatch):
    monkeypatch.setattr(wowaudit_web, "JOB_TIMEOUT_S", 0)
    routes = happy_routes()
    routes[("GET", "/api/jobs/job-1")] = FakeResponse(body=fixture("job_working.json"))
    with pytest.raises(WowAuditWebError, match="still running"):
        await upload(FakeAPI(routes))


async def test_report_missing_from_wishlist_fails_verification():
    routes = happy_routes()
    wishlist = fixture("wishlist.json")
    wishlist["items"][1]["wishes"][0]["report_url"] = (
        "https://questionablyepic.com/live/upgradereport/mnwczunrxpob"
    )
    routes[("GET", f"{WISHLIST_PATH}?season_id=18")] = FakeResponse(body=wishlist)
    with pytest.raises(WowAuditWebError, match="while verifying"):
        await upload(FakeAPI(routes))


async def test_server_error_includes_only_the_json_message():
    routes = happy_routes()
    routes[("PUT", WISHLIST_PATH)] = FakeResponse(status=422, body={"message": "Invalid report"})
    with pytest.raises(WowAuditWebError, match="HTTP 422: Invalid report"):
        await upload(FakeAPI(routes))


async def test_playwright_errors_never_leak_the_csrf_token():
    routes = happy_routes()
    routes[("PUT", WISHLIST_PATH)] = PlaywrightError(
        f"Request timed out {CSRF}\nCall log:\n"
        f"  - x-csrf-token: {CSRF}\n  - cookie: _user_session=x"
    )
    with pytest.raises(WowAuditWebError) as info:
        await upload(FakeAPI(routes))
    message = str(info.value)
    assert "while uploading the report" in message
    assert CSRF not in message and "cookie" not in message and "Call log" not in message
    assert info.value.__cause__ is None and info.value.__suppress_context__


async def test_rejects_non_qe_urls_and_non_wowaudit_teams_before_any_request():
    api = FakeAPI({})
    context = SimpleNamespace(request=api)
    with pytest.raises(WowAuditWebError, match="QE Live upgrade report"):
        await upload_report_via_web(
            context, "https://example.com/x", team_url=TEAM_URL, character_name="Shiftheal"
        )
    with pytest.raises(WowAuditWebError, match="WoWAudit team URL"):
        await upload_report_via_web(
            context, REPORT_URL, team_url="https://evil.example/teams/x", character_name="Shiftheal"
        )
    assert api.calls == []


@pytest.mark.parametrize(
    "url, report_id",
    [
        (REPORT_URL, "lcxtxzulnhiq"),
        (REPORT_URL + "/", "lcxtxzulnhiq"),
        (" https://www.questionablyepic.com/live/upgradereport/abc-DEF_1 ", "abc-DEF_1"),
    ],
)
def test_qe_report_id(url, report_id):
    assert qe_report_id(url) == report_id


@pytest.mark.parametrize(
    "url",
    [
        "https://questionablyepic.com/live/upgradefinder",
        "https://raidbots.com/simbot/report/abc",
        "http://questionablyepic.com/live/upgradereport/abc",
        "https://questionablyepic.com/live/upgradereport/abc?x=1",
    ],
)
def test_qe_report_id_rejects(url):
    with pytest.raises(WowAuditWebError):
        qe_report_id(url)


def test_find_team_id():
    user = fixture("page_info.json")["user"]
    assert find_team_id(user, TEAM_URL.upper() + "/") == 66817
    with pytest.raises(WowAuditWebError, match="not a member"):
        find_team_id(user, "https://wowaudit.com/guild/eu/draenor/other/teams/main")


def test_find_character_refuses_other_users_characters():
    with pytest.raises(WowAuditWebError, match="another WoWAudit user"):
        find_character(fixture("team.json"), 1001, "Someoneelse")


@pytest.mark.parametrize(
    "change, error",
    [
        (lambda team: team["settings"]["wishlistLocked"].update(value=True), "locked"),
        (lambda team: team["members"][0]["teamRank"].update(wishlist_visibility=False), "rank"),
        (lambda team: team["members"].append(copy.deepcopy(team["members"][0])), "More than one"),
        (lambda team: team["members"].pop(0), "not in team"),
    ],
)
def test_find_character_rejects(change, error):
    team = fixture("team.json")
    change(team)
    with pytest.raises(WowAuditWebError, match=error):
        find_character(team, 1001, "Shiftheal")


def test_extract_csrf_token():
    assert extract_csrf_token(fixture("characters_page.html")) == CSRF
    assert extract_csrf_token('<meta content="abc" name="csrf-token">') == "abc"
    with pytest.raises(WowAuditWebError, match="No CSRF token"):
        extract_csrf_token("<html></html>")


def test_job_result():
    assert job_result(fixture("job_working.json")) is None
    assert job_result({"status": "queued"}) is None
    assert job_result(fixture("job_completed.json"))["teamsUploaded"] == 2
    with pytest.raises(WowAuditWebError, match="interrupted"):
        job_result({"status": "interrupted"})
    with pytest.raises(WowAuditWebError, match="without uploading"):
        job_result({"status": "completed", "content": '{"teamsUploaded": 0}'})


def test_report_on_wishlist():
    wishlist = fixture("wishlist.json")
    assert report_on_wishlist(wishlist, "lcxtxzulnhiq")
    assert not report_on_wishlist(wishlist, "mnwczunrxpob")
    assert not report_on_wishlist({"items": []}, "lcxtxzulnhiq")


@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("WOWAUDIT_SESSION_FILE"), reason="needs WOWAUDIT_SESSION_FILE (read-only)"
)
async def test_resolve_upload_target_live():
    """Read-only: resolves the real team/character with the user's session. Never uploads."""
    from playwright.async_api import async_playwright

    from wishlist_updater.wowaudit_session import load_session

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(storage_state=load_session())
            target = await resolve_upload_target(
                context.request, team_url=TEAM_URL, character_name="Shiftheal"
            )
        finally:
            await browser.close()
    assert (target.team_id, target.character_name) == (66817, "Shiftheal")
