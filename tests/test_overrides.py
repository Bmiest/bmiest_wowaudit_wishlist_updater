import json
from datetime import datetime
from pathlib import Path

import pytest

from wishlist_updater.config import ItemOverride
from wishlist_updater.overrides import apply_overrides, extract_overrides, to_toml
from wishlist_updater.simc_source import build_simc_from_raiderio

FIXTURES = Path(__file__).parent / "fixtures"
ADDON_SIMC = (FIXTURES / "simc" / "shiftheal_addon.simc").read_text()
RAIDERIO_SIMC = build_simc_from_raiderio(
    json.loads((FIXTURES / "raiderio" / "shiftheal.json").read_text()),
    realm_slug="ragnaros",
    region="eu",
    now=datetime(2026, 9, 22, 21, 27),
).text

COMPARED = {"id", "enchant_id", "gem_id", "bonus_id", "crafted_stats", "redirected_base_stats"}


def _items(text):
    items = {}
    for line in text.splitlines():
        if "=," in line and not line.startswith("#"):
            slot, rest = line.split("=,", 1)
            fields = dict(f.split("=", 1) for f in rest.split(","))
            items[slot] = {k: v for k, v in fields.items() if k in COMPARED}
    return items


def test_extract_from_real_addon_export():
    overrides = extract_overrides(ADDON_SIMC)
    assert overrides == {
        "head": ItemOverride(271555, redirected_base_stats=268242),
        "shoulder": ItemOverride(271553, redirected_base_stats=239031),
        "chest": ItemOverride(271558, redirected_base_stats=268221),
        "waist": ItemOverride(239649, crafted_stats=(40, 36)),
        "legs": ItemOverride(271554, redirected_base_stats=268236),
        "off_hand": ItemOverride(245769, crafted_stats=(32, 40)),
    }


def test_raiderio_plus_overrides_matches_addon_export():
    """The fields QE's maths depends on become identical to the in-game export."""
    fixed, warnings = apply_overrides(RAIDERIO_SIMC, extract_overrides(ADDON_SIMC))
    assert warnings == []
    generated, expected = _items(fixed), _items(ADDON_SIMC)
    expected.pop("tabard")  # Raider.io has no tabard; irrelevant to QE
    assert generated == expected


def test_applied_line_keeps_ilevel_last():
    fixed, _ = apply_overrides(RAIDERIO_SIMC, extract_overrides(ADDON_SIMC))
    head = next(line for line in fixed.splitlines() if line.startswith("head=,"))
    assert head.endswith(",redirected_base_stats=268242,ilevel=321")


def test_stale_override_is_skipped_with_warning():
    stale = {"head": ItemOverride(999, redirected_base_stats=1)}
    fixed, warnings = apply_overrides(RAIDERIO_SIMC, stale)
    assert fixed == RAIDERIO_SIMC
    assert len(warnings) == 1 and "999" in warnings[0] and "271555" in warnings[0]


def test_override_for_empty_slot_warns():
    _, warnings = apply_overrides(RAIDERIO_SIMC, {"tabard": ItemOverride(36941)})
    assert warnings and "tabard" in warnings[0]


def test_commented_bag_lines_are_ignored():
    text = "# head=,id=1,redirected_base_stats=2\nhead=,id=3,ilevel=10\n"
    assert extract_overrides(text) == {}
    fixed, _ = apply_overrides(text, {"head": ItemOverride(3, redirected_base_stats=4)})
    assert fixed.splitlines() == [
        "# head=,id=1,redirected_base_stats=2",
        "head=,id=3,redirected_base_stats=4,ilevel=10",
    ]


def test_toml_round_trips_through_config(tmp_path):
    from wishlist_updater.config import Config

    overrides = extract_overrides(ADDON_SIMC)
    cfg = tmp_path / "w.toml"
    cfg.write_text('[[characters]]\nname = "Shiftheal"\nrealm = "ragnaros"\n' + to_toml(overrides))
    assert Config.load(cfg).characters[0].item_overrides == overrides


# --- refreshing wishlist.toml in place -------------------------------------------

from wishlist_updater import cli  # noqa: E402
from wishlist_updater.config import Config  # noqa: E402
from wishlist_updater.overrides import is_addon_export, replace_item_overrides  # noqa: E402

REPO_CONFIG = Path(__file__).parent.parent / "wishlist.toml"

TWO_CHARS = """# top comment
[qe]
mplus_level = 10

[[characters]]
name = "Shiftheal"
realm = "ragnaros"

# Regenerate after swapping tier/crafted items.
[characters.item_overrides]
head = { id = 1, redirected_base_stats = 2 }

[[characters]]
name = "Otherhealer"
realm = "ragnaros"
"""


def test_is_addon_export():
    assert is_addon_export(ADDON_SIMC)
    assert not is_addon_export(RAIDERIO_SIMC)


def test_replace_keeps_comments_and_other_characters():
    new = {"waist": ItemOverride(239649, crafted_stats=(40, 36))}
    out = replace_item_overrides(TWO_CHARS, "shiftheal", new)
    assert "head = { id = 1" not in out
    assert "waist = { id = 239649, crafted_stats = [40, 36] }" in out
    assert "# Regenerate after swapping tier/crafted items." in out
    assert out.count("[[characters]]") == 2 and 'name = "Otherhealer"' in out
    chars = Config.load_text(out).characters
    assert chars[0].item_overrides == new and chars[1].item_overrides == {}


def test_replace_appends_table_when_missing():
    new = {"head": ItemOverride(5, redirected_base_stats=6)}
    out = replace_item_overrides(TWO_CHARS, "Otherhealer", new)
    chars = Config.load_text(out).characters
    assert chars[1].item_overrides == new
    assert chars[0].item_overrides == {"head": ItemOverride(1, redirected_base_stats=2)}


def test_replace_unknown_character():
    with pytest.raises(ValueError, match="Nobody"):
        replace_item_overrides(TWO_CHARS, "Nobody", {})


def test_refresh_is_idempotent_on_the_real_config(tmp_path):
    """Refreshing twice from the same export changes nothing the second time, and keeps the
    rest of the real wishlist.toml (comments, other settings) intact."""
    cfg = tmp_path / "wishlist.toml"
    cfg.write_text(REPO_CONFIG.read_text())
    simc = tmp_path / "export.txt"
    simc.write_text(ADDON_SIMC)
    assert cli.main(["--config", str(cfg), "--refresh-overrides", str(simc)]) == 0
    once = cfg.read_text()
    assert cli.main(["--config", str(cfg), "--refresh-overrides", str(simc)]) == 0
    assert cfg.read_text() == once
    assert Config.load(cfg).characters[0].item_overrides == extract_overrides(ADDON_SIMC)
    assert "upload_days" in once and "[qe]" in once  # the rest of the file survives


def test_refresh_updates_after_a_swap(tmp_path, capsys):
    cfg = tmp_path / "wishlist.toml"
    cfg.write_text(REPO_CONFIG.read_text())
    simc = tmp_path / "export.txt"
    # Pretend a new catalysed helm (different id and origin) was equipped.
    simc.write_text(
        ADDON_SIMC.replace("head=,id=271555,", "head=,id=271999,").replace(
            "redirected_base_stats=268242", "redirected_base_stats=268111"
        )
    )
    assert cli.main(["--config", str(cfg), "--refresh-overrides", str(simc)]) == 0
    head = Config.load(cfg).characters[0].item_overrides["head"]
    assert head == ItemOverride(271999, redirected_base_stats=268111)
    assert "updated (6 slots)" in capsys.readouterr().out


def test_refresh_refuses_non_addon_exports(tmp_path):
    cfg = tmp_path / "wishlist.toml"
    cfg.write_text(REPO_CONFIG.read_text())
    simc = tmp_path / "wcl.txt"
    simc.write_text(RAIDERIO_SIMC)
    assert cli.main(["--config", str(cfg), "--refresh-overrides", str(simc)]) == 2
    assert cfg.read_text() == REPO_CONFIG.read_text()
