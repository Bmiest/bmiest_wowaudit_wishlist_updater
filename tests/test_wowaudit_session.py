import json
import stat

import pytest

from wishlist_updater import wowaudit_session as ws

BATTLE_NET_AND_WOWAUDIT = {
    "cookies": [
        {"name": "_user_session", "value": "s3cr3t", "domain": ".wowaudit.com", "path": "/"},
        {"name": "other", "value": "x", "domain": "wowaudit.com", "path": "/"},
        {"name": "BA-tassadar", "value": "bnet", "domain": ".battle.net", "path": "/"},
        {"name": "evil", "value": "x", "domain": "notwowaudit.com", "path": "/"},
    ],
    "origins": [
        {"origin": "https://wowaudit.com", "localStorage": []},
        {"origin": "https://account.battle.net", "localStorage": []},
    ],
}


def test_restrict_to_wowaudit_drops_other_sites():
    state = ws.restrict_to_wowaudit(BATTLE_NET_AND_WOWAUDIT)
    assert [c["name"] for c in state["cookies"]] == ["_user_session", "other"]
    assert [o["origin"] for o in state["origins"]] == ["https://wowaudit.com"]


def test_write_session_is_owner_only_and_filtered(tmp_path):
    path = ws.write_session(BATTLE_NET_AND_WOWAUDIT, tmp_path / "sub" / "s.json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    saved = json.loads(path.read_text())
    assert all("battle.net" not in c["domain"] for c in saved["cookies"])


def test_write_session_tightens_existing_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{}")
    path.chmod(0o644)
    ws.write_session(BATTLE_NET_AND_WOWAUDIT, path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_session_requires_login_cookie(tmp_path):
    with pytest.raises(ws.WowAuditSessionError, match="not logged in"):
        ws.write_session({"cookies": [], "origins": []}, tmp_path / "s.json")


def test_state_from_cookie_value():
    state = ws.state_from_cookie_value("  abc \n")
    assert state["cookies"][0]["value"] == "abc"
    assert state["cookies"][0]["domain"] == ".wowaudit.com"


def test_load_session_from_env_and_file(tmp_path, monkeypatch):
    monkeypatch.delenv("WOWAUDIT_SESSION", raising=False)
    monkeypatch.delenv("WOWAUDIT_SESSION_FILE", raising=False)
    assert ws.load_session() is None

    path = ws.write_session(BATTLE_NET_AND_WOWAUDIT, tmp_path / "s.json")
    monkeypatch.setenv("WOWAUDIT_SESSION_FILE", str(path))
    assert ws.load_session()["cookies"][0]["name"] == "_user_session"

    monkeypatch.setenv("WOWAUDIT_SESSION", json.dumps(BATTLE_NET_AND_WOWAUDIT))
    assert len(ws.load_session()["cookies"]) == 2


def test_load_session_bad_json_does_not_echo_value(monkeypatch):
    monkeypatch.setenv("WOWAUDIT_SESSION", "not-json s3cr3t")
    with pytest.raises(ws.WowAuditSessionError) as exc:
        ws.load_session()
    assert "s3cr3t" not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
