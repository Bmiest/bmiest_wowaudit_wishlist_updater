"""Runtime configuration.

Non-secret settings (which characters to process) live in a TOML file that is
committed to the repo. Secrets only ever come from environment variables, which
the GitHub Actions workflow populates from repository secrets.
"""

from __future__ import annotations

import dataclasses
import difflib
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("wishlist.toml")
SIMC_SOURCES = ("raiderio", "blizzard")
_TOP_LEVEL_KEYS = frozenset(
    {
        "characters",
        "qe",
        "simc_source",
        "wowaudit_team_url",
        "crest_planner",
        "raiderio_stale_after_hours",
        "reupload_after_days",
        "upload_difficulties",
    }
)
_CHARACTER_KEYS = frozenset({"name", "realm", "region", "item_overrides"})


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
    wowaudit_team_url: str | None = None
    crest_planner: bool = False
    # Warn when Raider.io last crawled the character longer ago than this.
    raiderio_stale_after_hours: float = 48
    # Re-upload an unchanged report after this many days (QE's numbers move between patches).
    reupload_after_days: float = 7
    # Which raid difficulties get uploaded to WoWAudit; None = all of qe.raid_difficulty.
    # The others are still generated for the dashboard only. Always spelled as in
    # qe.raid_difficulty and in its order (uploads happen in that order).
    upload_difficulties: tuple[str, ...] | None = None

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ConfigError(f"Config file not found: {path}") from exc
        return cls.load_text(text, path)

    @classmethod
    def load_text(cls, text: str, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: {exc}") from exc

        _reject_unknown(raw, _TOP_LEVEL_KEYS, "setting", path)
        chars = raw.get("characters") or []
        for c in chars if isinstance(chars, list) else []:
            if isinstance(c, dict):
                _reject_unknown(c, _CHARACTER_KEYS, "[[characters]] key", path)
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
        team_url = raw.get("wowaudit_team_url")
        if team_url is not None and not str(team_url).startswith("https://wowaudit.com/"):
            raise ConfigError(f"{path}: wowaudit_team_url must be a https://wowaudit.com/ URL")

        qe = dict(raw.get("qe", {}))
        _check_qe_keys(qe, path)
        raid = _difficulty_list(qe.get("raid_difficulty", "Mythic"), "qe.raid_difficulty", path)
        uploads = raw.get("upload_difficulties")
        if uploads is not None:
            uploads = _resolve_upload_difficulties(uploads, raid, path)

        return cls(
            characters=characters,
            qe=qe,
            simc_source=simc_source,
            wowaudit_team_url=team_url,
            crest_planner=bool(raw.get("crest_planner", False)),
            raiderio_stale_after_hours=float(raw.get("raiderio_stale_after_hours", 48)),
            reupload_after_days=float(raw.get("reupload_after_days", 7)),
            upload_difficulties=uploads,
        )


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


def _reject_unknown(table: dict, known: frozenset[str], what: str, path: Path) -> None:
    """A misspelled key must fail, not silently fall back to a default."""
    for key in table:
        if key not in known:
            close = difflib.get_close_matches(key, sorted(known), n=1)
            hint = f" (did you mean {close[0]!r}?)" if close else ""
            raise ConfigError(f"{path}: unknown {what} {key!r}{hint}")


def _check_qe_keys(qe: dict, path: Path) -> None:
    try:  # lazy: qe.py pulls in Playwright
        from wishlist_updater.qe import QESettings
    except ImportError:
        return
    known = frozenset(f.name for f in dataclasses.fields(QESettings))
    _reject_unknown(qe, known, "[qe] setting", path)


def _difficulty_list(value: object, field: str, path: Path) -> tuple[str, ...]:
    """A difficulty name or a non-empty list of them."""
    if isinstance(value, str):
        value = [value]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise ConfigError(f"{path}: {field} must be a difficulty name or a non-empty list of them")
    return tuple(v.strip() for v in value)


def _resolve_upload_difficulties(
    value: object, raid: tuple[str, ...], path: Path
) -> tuple[str, ...]:
    """Match case-insensitively against qe.raid_difficulty; return them in its spelling and
    order. A name that matches nothing would silently upload nothing, so it's an error."""
    wanted = _difficulty_list(value, "upload_difficulties", path)
    by_key = {r.casefold(): r for r in raid}
    for w in wanted:
        if w.casefold() not in by_key:
            raise ConfigError(
                f"{path}: upload_difficulties has {w!r}, which isn't in qe.raid_difficulty "
                f"{list(raid)}"
            )
    chosen = {w.casefold() for w in wanted}
    return tuple(r for r in raid if r.casefold() in chosen)
