"""Per-item SimC attributes that Raider.io and the Blizzard API don't expose.

QE's upgrade maths depends on two fields that only the in-game /simc addon knows:

- ``redirected_base_stats``: the original item a catalysed tier piece was made from.
  QE takes the piece's secondary stats from it.
- ``crafted_stats``: the secondary stats chosen when a crafted item was made.

Both are fixed for the life of an item, so they live in wishlist.toml per character and
slot, guarded by the item id. They're extracted once from an addon export and applied
to the generated SimC only while that slot still holds the same item.
"""

from __future__ import annotations

import re

from wishlist_updater.config import ItemOverride

_ITEM_LINE_RE = re.compile(r"^(?P<slot>[a-z_0-9]+)=,(?P<fields>.*)$")


def _parse_fields(fields: str) -> list[tuple[str, str]]:
    return [tuple(f.split("=", 1)) for f in fields.split(",") if "=" in f]


def extract_overrides(simc_text: str) -> dict[str, ItemOverride]:
    """Read overrides from the equipped (uncommented) item lines of an addon export."""
    found: dict[str, ItemOverride] = {}
    for line in simc_text.splitlines():
        m = _ITEM_LINE_RE.match(line.strip())
        if not m:
            continue
        fields = dict(_parse_fields(m["fields"]))
        redirected = fields.get("redirected_base_stats")
        crafted = fields.get("crafted_stats")
        if "id" not in fields or not (redirected or crafted):
            continue
        found[m["slot"]] = ItemOverride(
            item_id=int(fields["id"]),
            redirected_base_stats=int(redirected) if redirected else None,
            crafted_stats=tuple(int(s) for s in crafted.split("/")) if crafted else (),
        )
    return found


def apply_overrides(simc_text: str, overrides: dict[str, ItemOverride]) -> tuple[str, list[str]]:
    """Return (simc_text with overrides applied, warnings about overrides that didn't apply)."""
    pending = dict(overrides)
    warnings: list[str] = []
    out = []
    for line in simc_text.splitlines():
        m = _ITEM_LINE_RE.match(line)
        override = pending.pop(m["slot"], None) if m else None
        if override is None:
            out.append(line)
            continue
        fields = [(k, v) for k, v in _parse_fields(m["fields"])]
        equipped_id = dict(fields).get("id")
        if equipped_id != str(override.item_id):
            warnings.append(
                f"{m['slot']}: override is for item {override.item_id} but {equipped_id} is "
                "equipped. Refresh the overrides from a new /simc export."
            )
            out.append(line)
            continue
        extra = {}
        if override.redirected_base_stats is not None:
            extra["redirected_base_stats"] = str(override.redirected_base_stats)
        if override.crafted_stats:
            extra["crafted_stats"] = "/".join(str(s) for s in override.crafted_stats)
        fields = [(k, v) for k, v in fields if k not in extra]
        # Keep ilevel= last, like the builders emit it.
        tail = [(k, v) for k, v in fields if k == "ilevel"]
        fields = [(k, v) for k, v in fields if k != "ilevel"] + list(extra.items()) + tail
        out.append(f"{m['slot']}=," + ",".join(f"{k}={v}" for k, v in fields))
    for slot, override in pending.items():
        warnings.append(f"{slot}: override for item {override.item_id} but the slot is empty.")
    trailing = "\n" if simc_text.endswith("\n") else ""
    return "\n".join(out) + trailing, warnings


def to_toml(overrides: dict[str, ItemOverride]) -> str:
    lines = ["[characters.item_overrides]"]
    for slot, o in overrides.items():
        parts = [f"id = {o.item_id}"]
        if o.redirected_base_stats is not None:
            parts.append(f"redirected_base_stats = {o.redirected_base_stats}")
        if o.crafted_stats:
            parts.append(f"crafted_stats = [{', '.join(str(s) for s in o.crafted_stats)}]")
        lines.append(f"{slot} = {{ {', '.join(parts)} }}")
    return "\n".join(lines) + "\n"


ADDON_MARKER = "# SimC Addon"
_TABLE_HEADER_RE = re.compile(r"^\s*\[")
_NAME_RE = re.compile(r'^\s*name\s*=\s*"(?P<name>[^"]*)"')


def is_addon_export(simc_text: str) -> bool:
    """Only the in-game addon sees item-link modifiers (catalyst origin, crafted stats).
    Raider.io / Warcraft Logs / Armory exports lack them and would wipe good overrides."""
    return any(line.startswith(ADDON_MARKER) for line in simc_text.splitlines()[:10])


def replace_item_overrides(
    toml_text: str, character_name: str, overrides: dict[str, ItemOverride]
) -> str:
    """Rewrite one character's [characters.item_overrides] table, keeping everything else
    (comments, other characters, formatting) as it was."""
    lines = toml_text.splitlines()
    # Split into [[characters]] blocks: (start, end) line ranges.
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[characters]]"]
    bounds = list(zip(starts, starts[1:] + [len(lines)], strict=True))
    for start, end in bounds:
        names = [m["name"] for line in lines[start:end] if (m := _NAME_RE.match(line))]
        if not names or names[0].casefold() != character_name.casefold():
            continue
        body = to_toml(overrides).splitlines()[1:]
        header = next(
            (i for i in range(start, end) if lines[i].strip() == "[characters.item_overrides]"),
            None,
        )
        if header is None:
            insert_at = end
            while insert_at > start and not lines[insert_at - 1].strip():
                insert_at -= 1
            new = ["", "[characters.item_overrides]", *body]
            lines[insert_at:insert_at] = new
        else:
            stop = header + 1
            while stop < end and not _TABLE_HEADER_RE.match(lines[stop]):
                stop += 1
            # Keep trailing blank lines/comments that belong to what follows.
            keep_from = stop
            while keep_from > header + 1 and (
                not lines[keep_from - 1].strip() or lines[keep_from - 1].lstrip().startswith("#")
            ):
                keep_from -= 1
            lines[header + 1 : keep_from] = body
        return "\n".join(lines) + ("\n" if toml_text.endswith("\n") else "")
    raise ValueError(f"No [[characters]] entry named {character_name!r} in the config")
