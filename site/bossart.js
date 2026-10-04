// Boss heads for the raid-night tiles, keyed by QE Live's encounter id (the ids in the run
// summary's "raids", from QE's InstanceDB.ts). Kill order and which raids to show come from the
// data; this file only adds what QE doesn't have: the boss's full name and its portrait.
//
// Provenance of img/boss/head-<display id>.webp: Blizzard's NPC renders
// (render.worldofwarcraft.com/eu/npcs/zoom/creature-display-<id>.jpg), cut out by the race
// site's scripts/boss-cutouts.py (Bmiest/racetodutchfirst, site/img/boss/*.png), then cropped
// here to the top square (centred) and scaled to 112x112 WebP. Display ids per boss as in the
// race site's bossart.js (wago.tools DB2 exports). Game art (c) Blizzard Entertainment.
//
// A new tier: add its bosses here with their display id and drop the heads in img/boss/. A boss
// without an entry still gets a tile, with its initial instead of a head.
window.BossArt = {
  // The Venomous Abyss
  2888: { name: "Nek'zali the Soulcoiler", head: 142077 },
  2874: { name: "Entombed Sentinels", head: 143437 },
  2894: { name: "The Lost Explorers", head: 143824 },
  2882: { name: "Vashnik the Malignant", head: 141675 },
  2871: { name: "Sszorak", head: 142788 },
  2887: { name: "The Twin Fangs", head: 140993 },
  2883: { name: "The Coiled Altar", head: 142140 },
  2895: { name: "Ula'tek", head: 140369 },
  // The Tidebound Grotto
  2849: { name: "Nymrissa Wavecaller", head: 137687 },
};
