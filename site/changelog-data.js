// What changed on the dashboard and in the updater, per version, newest first. changelog.html
// turns it into the list; the version that is live comes from version.json (pyproject.toml).
//
// Like changelog.toml on racetodutchfirst.nl: every release that changes something you notice
// gets a block with the version (pyproject's) and the release date (Europe/Brussels), and lines
// in `nl` and `en`: plain language, what you see on the dashboard or in WoWAudit (no code, no
// PR numbers). The Dutch line is the original; the English one says the same. Add the block in
// the "Release x.y.z" PR.
"use strict";

const CHANGELOG = [
  {
    version: "1.3.0", date: "2026-10-04",
    nl: [
      "Het dashboard is een plan voor de raidavond: het opent op de volgende raid, met per boss wat hij voor je kan droppen. De tegel met de beste upgrade krijgt een gouden rand.",
      "Elke boss heeft een portret, en elk item zijn icoon en naam.",
      "Rechts staan de status van de run, wat er sinds de vorige run veranderde en de geschiedenis.",
      "Daaronder de beste M+-dungeons van de week en waar je crests het meest opleveren. Het volledige rapport en je gear staan uitgeklapt onderaan.",
      "Een mislukte run kleurt rozerood; rood is op de bmiest-sites voor live.",
      "Het dashboard in het Nederlands of het Engels.",
    ],
    en: [
      "The dashboard is a raid-night plan: it opens on the next raid, with what each boss can drop for you. The tile with the best upgrade gets a gold frame.",
      "Every boss has a portrait, and every item its icon and name.",
      "On the right: the run's status, what changed since the previous run and the history.",
      "Below that, the week's best M+ dungeons and where your crests pay off most. The full report and your gear are folded at the bottom.",
      "A failed run turns rose; red is for live on the bmiest sites.",
      "The dashboard in Dutch or English.",
    ],
  },
  {
    version: "1.2.0", date: "2026-09-24",
    nl: [
      "Volgt de socketinstelling in WoWAudit.",
      "De geschiedenis toont per run of het rapport naar WoWAudit ging, en een mislukte upload staat er als mislukt.",
    ],
    en: [
      "Follows the socket setting in WoWAudit.",
      "The history shows per run whether the report went to WoWAudit, and a failed upload shows as failed.",
    ],
  },
  {
    version: "1.1.0", date: "2026-09-24",
    nl: [
      "Rapporten gaan alleen op raiddagen naar WoWAudit, met een inhaalrun op de raiddag zelf.",
      "Het dashboard zegt waarom een rapport niet werd geüpload.",
    ],
    en: [
      "Reports only go to WoWAudit on raid days, with a catch-up run on the raid day itself.",
      "The dashboard says why a report was not uploaded.",
    ],
  },
  {
    version: "1.0.1", date: "2026-09-23",
    nl: [
      "Alleen Mythic gaat naar WoWAudit, en een ongewijzigd rapport hoogstens om de dag en een half.",
      "Een verkeerd gespelde instelling stopt de run, met de juiste naam erbij.",
    ],
    en: [
      "Only Mythic goes to WoWAudit, and an unchanged report at most every day and a half.",
      "A misspelled setting stops the run, with the right name suggested.",
    ],
  },
  {
    version: "1.0.0", date: "2026-09-23",
    nl: [
      "Elke dag een QE Live-upgraderapport voor een healer, in een WoWAudit-wishlist gezet, met een dashboard: upgrades voor Heroic en Mythic, waar je crests heen moeten, je gear en de geschiedenis van de runs.",
    ],
    en: [
      "A QE Live upgrade report for a healer every day, put into a WoWAudit wishlist, with a dashboard: Heroic and Mythic upgrades, where to spend crests, your gear and the run history.",
    ],
  },
];
