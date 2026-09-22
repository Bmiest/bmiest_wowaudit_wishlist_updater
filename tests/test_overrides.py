import json
from datetime import datetime
from pathlib import Path

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
