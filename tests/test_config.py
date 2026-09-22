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
