"""The dashboard in site/: its JS unit tests (node) and a render in headless Chromium.

Both skip when their tool isn't installed (node / Playwright's Chromium). The render test
serves site/ with a small summary-v2 data set and blocks every external request, so it runs
offline.
"""

from __future__ import annotations

import copy
import functools
import http.server
import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SITE = ROOT / "site"
XSS = '<img src=x onerror="window.__pwned=1">'


def test_dashboard_js_unit_tests():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    tests = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.mjs"))
    proc = subprocess.run([node, "--test", *tests], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]


def _result(item, pct, boss, loc="Raid", name=None, slot="Head"):
    return {
        "item": item,
        "level": 289,
        "dropType": "drop",
        "dropLoc": loc,
        "dropDifficulty": 3 if loc == "Raid" else 7,
        "percDiff": pct,
        "score": 0,
        "dropSource": boss,
        "slot": slot,
        "name": name or f"Item named {item}",
        "icon": "inv_helm_01",
    }


def _summary(run_id: str, ok: bool = True) -> dict:
    results = [
        _result(1, 1.57, "Ula'tek", name="Jan'thrazet, the Soul Fang"),
        _result(2, 0.74, "Nek'zali", name=XSS),
        _result(3, 0.37, "Nek'zali / Entombed Sentinels"),
        _result(4, 0.70, "Temple of Sethraliss", loc="Dungeon", slot="Finger"),
        _result(5, 0, "Ula'tek"),
    ]
    # The same items at bonus-roll level, for the "Best bonus roll" block.
    results += [
        {**r, "dropType": "bonus", "level": 344, "percDiff": r["percDiff"] and r["percDiff"] + 0.1}
        for r in copy.deepcopy(results)
    ]
    return {
        "schema": 2,
        "run": {
            "id": run_id,
            "url": f"https://github.com/o/r/actions/runs/{run_id}",
            "trigger": "schedule",
            "started_at": "2026-10-03T06:33:48+00:00",
            "finished_at": "2026-10-03T06:34:11+00:00",
            "ok": ok,
        },
        "characters": [
            {
                "name": "Shiftheal",
                "realm": "ragnaros",
                "region": "eu",
                "class": "Priest",
                "spec": "Holy",
                "gear_as_of": "2026-09-30T10:00:00+00:00",
                "gear": [
                    {"slot": "head", "item_id": 9, "name": "Old Cowl", "ilvl": 280, "icon": "x_1"}
                ],
                "warnings": [
                    "Raider.io last read this character 2.9 days ago, so recent gear changes "
                    "may be missing. Paste a /simc export for an up-to-date run."
                ],
                "skipped": None,
                "error": None if ok else f"ValueError: {XSS}",
                "reports": [
                    {
                        "difficulty": d,
                        "report_id": d.lower(),
                        "report_url": f"https://questionablyepic.com/live/upgradereport/{d}",
                        "uploaded": False,
                        "error": None,
                        "results": copy.deepcopy(results),
                    }
                    for d in ("Heroic", "Mythic")
                ],
                "crest_report": None,
                "crest_upgrades": [],
            }
        ],
        "raids": [
            {
                "id": 1320,
                "name": "The Venomous Abyss",
                "bosses": [
                    {"id": 2888, "name": "Nek'zali"},
                    {"id": 2874, "name": "Entombed Sentinels"},
                    {"id": 2895, "name": "Ula'tek"},
                ],
            }
        ],
        "raid_night": {
            "days": ["Wednesday", "Sunday"],
            "start": "20:00",
            "end": "23:00",
            "timezone": "Europe/Brussels",
        },
    }


def _site(tmp_path: Path, ok: bool) -> Path:
    from wishlist_updater.dashboard import publish

    root = tmp_path / ("ok" if ok else "fail")
    shutil.copytree(SITE, root)
    publish(_summary("2"), root / "data")
    if not ok:
        failed = _summary("3", ok=False)
        failed["run"]["started_at"] = "2026-10-04T06:00:00+00:00"
        publish(failed, root / "data")
    return root


@pytest.fixture
def server(tmp_path):
    _site(tmp_path, ok=True)
    _site(tmp_path, ok=False)
    handler = functools.partial(
        type("Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}),
        directory=str(tmp_path),
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _render(base: str, path: str, width: int = 1440):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # no browser downloaded
            pytest.skip(f"Chromium unavailable: {exc}")
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.route(
            "**/*",
            lambda route: (
                route.continue_() if route.request.url.startswith(base) else route.abort()
            ),
        )
        page.goto(base + path)
        page.wait_for_selector(".rn")
        state = page.evaluate(
            """() => ({
              title: document.querySelector('.ph__title').textContent,
              status: document.querySelector('.bug__status').className + ' ' +
                      document.querySelector('.bug__status').textContent,
              tiles: [...document.querySelectorAll('.rnb')].map(t => [
                t.querySelector('.rnb__name').textContent, t.classList.contains('is-best'),
                t.querySelectorAll('.rnb__it').length]),
              when: document.querySelector('.rn__date').textContent,
              bonus: [...document.querySelectorAll('[aria-labelledby="brH"] .dg__name b')]
                .map(b => b.textContent),
              alerts: [...document.querySelectorAll('.alert')].map(a => a.textContent),
              heads: [...document.querySelectorAll('.rnb .boss-thumb img')]
                .map(i => i.getAttribute('src')),
              pwned: window.__pwned === 1,
              injected: document.querySelectorAll('img[src="x"]').length,
              scrollWidth: document.documentElement.scrollWidth,
              text: document.body.textContent,
            })"""
        )
        browser.close()
    real_errors = [e for e in errors if "ERR_FAILED" not in e and "net::" not in e]
    return state, real_errors


def test_dashboard_renders_the_raid_night(server):
    state, errors = _render(server, "/ok/?lang=en")
    assert errors == []
    assert state["title"] == "Gear upgrades"
    assert "is-ok" in state["status"]
    # Kill order from the data, full names and heads from bossart.js, gold on the best only.
    assert state["tiles"] == [
        ["Nek'zali the Soulcoiler", False, 2],
        ["Entombed Sentinels", False, 1],
        ["Ula'tek", True, 1],
    ]
    assert state["heads"] == [
        "img/boss/head-142077.webp",
        "img/boss/head-143437.webp",
        "img/boss/head-140369.webp",
    ]
    assert "20:00" in state["when"]
    # Bonus rolls by average gain over the pool: Ula'tek (1.67 + a miss) / 2 beats the dungeon.
    assert state["bonus"] == [
        "Ula'tek",
        "Temple of Sethraliss",
        "Nek'zali the Soulcoiler",
        "Entombed Sentinels",
    ]
    assert any("Gear may be out of date" in a for a in state["alerts"])
    assert "Jan'thrazet, the Soul Fang" in state["text"]
    # Data strings stay text: the markup in an item name is shown, never parsed.
    assert XSS in state["text"] and not state["pwned"] and state["injected"] == 0


def test_dashboard_in_dutch_on_a_phone(server):
    state, errors = _render(server, "/ok/?lang=nl", width=390)
    assert errors == []
    assert state["title"] == "Gear-upgrades"
    assert any("Gear is mogelijk verouderd" in a and "2,9 dagen" in a for a in state["alerts"])
    assert state["scrollWidth"] <= 390


def test_dashboard_shows_a_failed_run(server):
    state, errors = _render(server, "/fail/?lang=en")
    assert errors == []
    assert "is-fail" in state["status"] and "Run failed" in state["status"]
    assert any("This run failed" in a and XSS in a for a in state["alerts"])
    assert not state["pwned"] and state["injected"] == 0


def test_sample_summary_round_trips_through_publish(tmp_path):
    """The fixture the render tests serve is what dashboard.publish writes."""
    root = _site(tmp_path, ok=True)
    latest = json.loads((root / "data" / "latest.json").read_text())
    assert latest["raids"][0]["bosses"][0]["id"] == 2888
    assert latest["raid_night"]["start"] == "20:00"
