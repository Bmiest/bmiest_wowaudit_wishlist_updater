---
version: 1
slug: "site-index-html"
primary_target: "site/index.html"
related_targets: []
---

# Dashboard (site/index.html)

Scope: the dashboard at wishlistupdater.bmiest.be. Visitor mode: Operate. User: the operator, Shiftheal (Holy Priest, Ragnaros EU), deciding what to wish for in raid and M+ and where to spend crests, mostly before raid nights. Product truth lives in Bmiest/bmiest-design PRODUCT.md (not copied here at the user's request); visual system: design language v2 (bmiest-design DESIGN.md).

Chosen from three mockups (A ranked ribbon board, B boss-by-boss loot plan, C raid-night plan): C. Mockups: .impeccable/mocks/ (choice recorded there).

## Direction contract

THESIS: What matters this week comes first: the next raid night and what each of its bosses can drop for you. It refuses the generic KPI-cards-over-a-table dashboard; every function of the old page stays one fold away.

OWN-WORLD: Design language v2 lending type, palette, density and one move: ink grounds, Outfit 800 headings behind the slanted jade cap, mono figures, flush broadcast-bug top bar, slanted pills and bars, jade for OK and active, gold only for the best upgrade, red for a failed run, boss-head tiles from the race site. Standard tabs, filters, tables and links.

STORY: Shiftheal opens it before a raid, sees tonight's bosses with their upgrades and the best one in gold, checks the week's best M+ dungeons and where to spend crests, and confirms the last run was OK.

FIRST VIEWPORT: Top bar (bmiest, run status, updated, GitHub, EN|NL). Title with character line and the Raider.IO staleness warning when stale. Main: "Tonight 20:00" with the countdown, Heroic|Mythic tabs, then the raid's bosses as tiles in kill order listing their upgrades. Right rail: run status, changes since the previous run, run history.

FORM: Raid-night plan, item 7 of the ordered list, dealt by seed 8e4eace6.

SIGNATURE: the raid night as a grid of boss tiles; the tile holding the best upgrade is framed in gold.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
