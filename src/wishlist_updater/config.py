"""Runtime configuration.

Non-secret settings (which characters to process) live in a TOML file that is
committed to the repo. Secrets only ever come from environment variables, which
the GitHub Actions workflow populates from repository secrets.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("wishlist.toml")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Character:
    name: str
    realm: str
    region: str = "eu"

    @property
    def label(self) -> str:
        return f"{self.name}-{self.realm} ({self.region.upper()})"


@dataclass(frozen=True)
class Secrets:
    wowaudit_api_key: str | None
    blizzard_client_id: str | None
    blizzard_client_secret: str | None

    @classmethod
    def from_env(cls) -> Secrets:
        return cls(
            wowaudit_api_key=os.environ.get("WOWAUDIT_API_KEY") or None,
            blizzard_client_id=os.environ.get("BLIZZARD_CLIENT_ID") or None,
            blizzard_client_secret=os.environ.get("BLIZZARD_CLIENT_SECRET") or None,
        )

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            env_names = ", ".join(n.upper() for n in missing)
            raise ConfigError(f"Missing required environment variable(s): {env_names}")


@dataclass(frozen=True)
class Config:
    characters: tuple[Character, ...]
    qe: dict[str, object]

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"Config file not found: {path}") from exc

        chars = raw.get("characters") or []
        if not chars:
            raise ConfigError(f"{path}: no [[characters]] entries")
        try:
            characters = tuple(
                Character(
                    name=c["name"],
                    realm=c["realm"].lower(),
                    region=c.get("region", "eu").lower(),
                )
                for c in chars
            )
        except KeyError as exc:
            raise ConfigError(f"{path}: character entry missing key {exc}") from exc

        # QE settings are passed through to qe.QESettings(**qe) so the QE module
        # stays the single owner of which knobs exist.
        return cls(characters=characters, qe=dict(raw.get("qe", {})))
