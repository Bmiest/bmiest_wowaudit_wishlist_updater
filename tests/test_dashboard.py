import copy
import json
from pathlib import Path

import pytest

from wishlist_updater.dashboard import main, publish, results_digest, run_header

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "dashboard" / "run_sample.json").read_text()
)


def _summary(run_id: str, started: str) -> dict:
    s = copy.deepcopy(SAMPLE)
    s["run"].update(id=run_id, started_at=started)
    return s


def test_publish_builds_index_newest_first(tmp_path):
    publish(_summary("1", "2026-09-20T06:00:00+00:00"), tmp_path)
    index = publish(_summary("2", "2026-09-21T06:00:00+00:00"), tmp_path)
    assert [r["id"] for r in index] == ["2", "1"]
    on_disk = json.loads((tmp_path / "index.json").read_text())
    assert on_disk["schema"] == 1 and [r["id"] for r in on_disk["runs"]] == ["2", "1"]
    assert json.loads((tmp_path / "latest.json").read_text())["run"]["id"] == "2"
    assert (tmp_path / "runs" / "1.json").exists()


def test_index_headers_are_light(tmp_path):
    header = run_header(_summary("1", "2026-09-20T06:00:00+00:00"))
    [char] = header["characters"]
    assert "gear" not in char
    assert all("results" not in r for r in char["reports"])
    assert [r["difficulty"] for r in char["reports"]] == ["Heroic", "Mythic"]


def test_publish_prunes_old_runs(tmp_path):
    for i in range(5):
        publish(_summary(str(i), f"2026-09-2{i}T06:00:00+00:00"), tmp_path, keep=3)
    assert sorted(p.stem for p in (tmp_path / "runs").glob("*.json")) == ["2", "3", "4"]


@pytest.mark.parametrize("bad", ["", "../../etc/passwd", "a/b", None])
def test_publish_rejects_unsafe_run_ids(tmp_path, bad):
    with pytest.raises(ValueError):
        publish(_summary(bad, "2026-09-20T06:00:00+00:00"), tmp_path)


def test_main_without_summary_still_rebuilds(tmp_path, capsys):
    publish(_summary("1", "2026-09-20T06:00:00+00:00"), tmp_path)
    (tmp_path / "index.json").unlink()
    assert main([str(tmp_path / "missing.json"), str(tmp_path)]) == 0
    assert json.loads((tmp_path / "index.json").read_text())["runs"][0]["id"] == "1"
    assert "1 run(s)" in capsys.readouterr().out


def test_digest_ignores_report_ids_and_timestamps():
    a = _summary("1", "2026-09-20T06:00:00+00:00")
    b = _summary("2", "2026-09-21T06:00:00+00:00")
    for r in b["characters"][0]["reports"]:
        r["report_id"] = "other"
        r["report_url"] = "https://questionablyepic.com/live/upgradereport/other"
    assert results_digest(a) == results_digest(b)
    assert run_header(a)["digest"] == results_digest(a)


def test_digest_changes_with_upgrades_and_gear():
    base = _summary("1", "2026-09-20T06:00:00+00:00")
    found = copy.deepcopy(base)
    report = found["characters"][0]["reports"][0]
    report["results"] = list(report.get("results") or []) + [
        {"item": 1, "level": 300, "dropType": "drop", "percDiff": 0.5}
    ]
    geared = copy.deepcopy(base)
    geared["characters"][0]["gear"] = list(geared["characters"][0].get("gear") or []) + [
        {"slot": "head", "item_id": 2, "ilvl": 300}
    ]
    digests = {results_digest(base), results_digest(found), results_digest(geared)}
    assert len(digests) == 3


def test_digest_ignores_non_upgrades():
    base = _summary("1", "2026-09-20T06:00:00+00:00")
    noise = copy.deepcopy(base)
    report = noise["characters"][0]["reports"][0]
    report["results"] = list(report.get("results") or []) + [
        {"item": 1, "level": 300, "dropType": "drop", "percDiff": 0}
    ]
    assert results_digest(base) == results_digest(noise)
