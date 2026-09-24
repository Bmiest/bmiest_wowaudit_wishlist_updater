import pathlib

import pytest

from wishlist_updater.config import Config, ConfigError, Secrets, realm_slug


@pytest.mark.parametrize(
    "realm, slug",
    [("Ragnaros", "ragnaros"), ("Twisting Nether", "twisting-nether"), ("Kel'Thuzad", "kelthuzad")],
)
def test_realm_slug(realm, slug):
    assert realm_slug(realm) == slug


def test_load(tmp_path):
    cfg = tmp_path / "w.toml"
    cfg.write_text(
        '[qe]\nmplus_level = 10\n[[characters]]\nname = "Shiftheal"\nrealm = "Ragnaros"\n'
    )
    config = Config.load(cfg)
    assert config.characters[0].realm == "ragnaros"
    assert config.characters[0].region == "eu"
    assert config.qe == {"mplus_level": 10}


def test_load_defaults_to_raiderio_and_validates_source(tmp_path):
    cfg = tmp_path / "w.toml"
    cfg.write_text('[[characters]]\nname = "A"\nrealm = "b"\n')
    assert Config.load(cfg).simc_source == "raiderio"
    cfg.write_text('simc_source = "wcl"\n[[characters]]\nname = "A"\nrealm = "b"\n')
    with pytest.raises(ConfigError, match="simc_source"):
        Config.load(cfg)


def test_load_rejects_empty(tmp_path):
    cfg = tmp_path / "w.toml"
    cfg.write_text("[qe]\n")
    with pytest.raises(ConfigError, match="no \\[\\[characters\\]\\]"):
        Config.load(cfg)


def test_secrets_require(monkeypatch):
    monkeypatch.setenv("WOWAUDIT_API_KEY", "k")
    monkeypatch.delenv("BLIZZARD_CLIENT_ID", raising=False)
    secrets = Secrets.from_env()
    secrets.require("wowaudit_api_key")
    with pytest.raises(ConfigError, match="BLIZZARD_CLIENT_ID"):
        secrets.require("blizzard_client_id")


def test_item_overrides_validation(tmp_path):
    cfg = tmp_path / "w.toml"
    base = '[[characters]]\nname = "A"\nrealm = "b"\n[characters.item_overrides]\n'
    cfg.write_text(base + "wasit = { id = 1, crafted_stats = [40] }\n")
    with pytest.raises(ConfigError, match="unknown slot 'wasit'"):
        Config.load(cfg)
    cfg.write_text(base + "waist = { id = 1, crafted_stat = [40] }\n")
    with pytest.raises(ConfigError, match="unknown key"):
        Config.load(cfg)
    cfg.write_text(base + "waist = { crafted_stats = [40] }\n")
    with pytest.raises(ConfigError, match="needs at least an id"):
        Config.load(cfg)


def _load(tmp_path, text):
    cfg = tmp_path / "w.toml"
    cfg.write_text(text)
    return Config.load(cfg)


CHAR = '[[characters]]\nname = "A"\nrealm = "b"\n'


def test_unknown_settings_are_errors_with_a_hint(tmp_path):
    with pytest.raises(ConfigError, match="did you mean 'upload_difficulties'"):
        _load(tmp_path, 'upload_difficulty = "Mythic"\n' + CHAR)
    with pytest.raises(ConfigError, match="unknown \\[\\[characters\\]\\] key 'realms'"):
        _load(tmp_path, '[[characters]]\nname = "A"\nrealms = "b"\n')
    with pytest.raises(ConfigError, match=r"unknown \[qe\] setting 'mplus_levle'"):
        _load(tmp_path, "[qe]\nmplus_levle = 10\n" + CHAR)


@pytest.mark.parametrize("value", ["[]", '""', "[1]", "7"])
def test_raid_difficulty_must_be_names(tmp_path, value):
    with pytest.raises(ConfigError, match="qe.raid_difficulty"):
        _load(tmp_path, f"[qe]\nraid_difficulty = {value}\n" + CHAR)


def test_upload_difficulties_are_normalised_to_the_raid_spelling_and_order(tmp_path):
    config = _load(
        tmp_path,
        'upload_difficulties = ["mythic", "HEROIC"]\n[qe]\nraid_difficulty = ["Heroic", "Mythic"]\n'
        + CHAR,
    )
    assert config.upload_difficulties == ("Heroic", "Mythic")
    assert _load(tmp_path, CHAR).upload_difficulties is None


@pytest.mark.parametrize("value", ['["Mytic"]', "[]", '"Heroic"'])
def test_upload_difficulties_that_match_nothing_fail_loudly(tmp_path, value):
    with pytest.raises(ConfigError, match="upload_difficulties"):
        _load(tmp_path, f'upload_difficulties = {value}\n[qe]\nraid_difficulty = "Mythic"\n' + CHAR)


def test_repo_config_loads():
    config = Config.load(pathlib.Path(__file__).parent.parent / "wishlist.toml")
    assert config.upload_difficulties == ("Mythic",)


def test_upload_days(tmp_path):
    config = _load(tmp_path, 'upload_days = ["sunday", "Wednesday", "WEDNESDAY"]\n' + CHAR)
    assert config.upload_weekdays == (2, 6)
    assert _load(tmp_path, CHAR).upload_weekdays is None
    with pytest.raises(ConfigError, match="upload_days"):
        _load(tmp_path, 'upload_days = ["Wensday"]\n' + CHAR)
    with pytest.raises(ConfigError, match="upload_days"):
        _load(tmp_path, "upload_days = []\n" + CHAR)
