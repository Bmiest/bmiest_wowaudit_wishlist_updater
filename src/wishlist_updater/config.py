"""Runtime configuration.

Non-secret settings (which characters to process) live in a TOML file that is
committed to the repo. Secrets only ever come from environment variables, which
the GitHub Actions workflow populates from repository secrets.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("wishlist.toml")
SIMC_SOURCES = ("raiderio", "blizzard")


class ConfigError(RuntimeError):
    pass


def realm_slug(realm: str) -> str:
    """'Twisting Nether' / "Azjol-Nerub" / "Kel'Thuzad" -> Blizzard API slug."""
    return realm.strip().lower().replace("'", "").replace(" ", "-")


@dataclass(frozen=True)
class ItemOverride:
    """SimC item attributes the gear APIs don't expose; see overrides.py."""

    item_id: int
    redirected_base_stats: int | None = None
    crafted_stats: tuple[int, ...] = ()


@dataclass(frozen=True)
class Character:
    name: str
    realm: str
    region: str = "eu"
    item_overrides: dict[str, ItemOverride] = field(default_factory=dict, hash=False, compare=False)

    @property
    def label(self) -> str:
        return f"{self.name}-{self.realm} ({self.region.upper()})"


@dataclass(frozen=True)
class Secrets:
    wowaudit_api_key: str | None
    blizzard_client_id: str | None = None
    blizzard_client_secret: str | None = None
    raiderio_api_key: str | None = None  # optional; only raises Raider.io's rate limit

    @classmethod
    def from_env(cls) -> Secrets:
        return cls(
            wowaudit_api_key=os.environ.get("WOWAUDIT_API_KEY") or None,
            blizzard_client_id=os.environ.get("BLIZZARD_CLIENT_ID") or None,
            blizzard_client_secret=os.environ.get("BLIZZARD_CLIENT_SECRET") or None,
            raiderio_api_key=os.environ.get("RAIDERIO_API_KEY") or None,
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
    simc_source: str = "raiderio"

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
                    realm=realm_slug(c["realm"]),
                    region=c.get("region", "eu").lower(),
                    item_overrides=_parse_item_overrides(c.get("item_overrides", {})),
                )
                for c in chars
            )
        except KeyError as exc:
            raise ConfigError(f"{path}: character entry missing key {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{path}: {exc}") from exc

        simc_source = raw.get("simc_source", "raiderio")
        if simc_source not in SIMC_SOURCES:
            raise ConfigError(f"{path}: simc_source must be one of {', '.join(SIMC_SOURCES)}")

        # QE settings are passed through to qe.QESettings(**qe) so the QE module
        # stays the single owner of which knobs exist.
        return cls(characters=characters, qe=dict(raw.get("qe", {})), simc_source=simc_source)


def _parse_item_overrides(table: dict) -> dict[str, ItemOverride]:
    from wishlist_updater.simc_source import SLOT_ORDER  # lazy: simc_source imports config

    overrides = {}
    for slot, entry in table.items():
        if slot not in SLOT_ORDER:
            raise ValueError(f"item_overrides: unknown slot {slot!r}")
        if not isinstance(entry, dict) or "id" not in entry:
            raise ValueError(f"item_overrides.{slot}: needs at least an id")
        unknown = set(entry) - {"id", "redirected_base_stats", "crafted_stats"}
        if unknown:
            raise ValueError(f"item_overrides.{slot}: unknown key(s) {sorted(unknown)}")
        redirected = entry.get("redirected_base_stats")
        overrides[slot] = ItemOverride(
            item_id=int(entry["id"]),
            redirected_base_stats=int(redirected) if redirected is not None else None,
            crafted_stats=tuple(int(s) for s in entry.get("crafted_stats", ())),
        )
    return overrides
