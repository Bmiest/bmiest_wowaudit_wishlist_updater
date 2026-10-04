---
name: bmiest gear upgrades
description: The public run dashboard for the daily QE Live upgrade reports, laid out as a raid-night plan (design language v2, operate mode).
colors:
  ink-900: "#0a0b0d"
  ink-850: "#0e1014"
  ink-800: "#131519"
  ink-750: "#171a1f"
  ink-700: "#1e2228"
  ink-600: "#2a2f37"
  ink-400: "#5b6470"
  ink-300: "#818b98"
  ink-200: "#a8b1bc"
  paper: "#eef1f5"
  paper-dim: "#c9d0d8"
  jade: "#3fd9a4"
  jade-deep: "#1f8d68"
  jade-ghost: "rgba(63,217,164,.13)"
  gold: "#d8b263"
  rose: "#d98b8b"
  live-red: "#c93339"
  track: "rgba(238,241,245,.08)"
typography:
  title:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "32px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-.01em"
  headline:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "clamp(26px, 2.6vw, 32px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-.01em"
  headline-sub:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-.01em"
  character:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    letterSpacing: "-.01em"
  status:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "20px"
    fontWeight: 700
  fold:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 700
  lead:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  body:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  caption:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  bug:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 800
    letterSpacing: ".1em"
  control:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 800
    letterSpacing: ".12em"
  label:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: ".14em"
  label-wide:
    fontFamily: "'Outfit', 'Segoe UI', system-ui, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: ".18em"
  numeric-stat:
    fontFamily: "'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  numeric:
    fontFamily: "'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  none: "0px"
spacing:
  wrap: "1320px"
  gutter: "24px"
  gutter-phone: "16px"
  page-stack: "28px"
  section: "40px"
  rail: "340px"
  rail-stack: "28px"
  tile-gap: "6px"
  row-gap: "8px"
components:
  bug-brand:
    backgroundColor: "{colors.ink-900}"
    textColor: "{colors.paper}"
    typography: "{typography.bug}"
    rounded: "{rounded.none}"
    padding: "0 20px 0 16px"
    height: "40px"
  bug-status-ok:
    backgroundColor: "{colors.jade}"
    textColor: "{colors.ink-900}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  bug-status-fail:
    backgroundColor: "{colors.live-red}"
    textColor: "{colors.paper}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  bug-updated:
    backgroundColor: "{colors.ink-750}"
    textColor: "{colors.ink-200}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "40px"
  lang-block:
    backgroundColor: "{colors.ink-900}"
    textColor: "{colors.ink-300}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0 14px"
    height: "40px"
  lang-block-active:
    backgroundColor: "{colors.jade}"
    textColor: "{colors.ink-900}"
  tab:
    backgroundColor: "{colors.ink-850}"
    textColor: "{colors.ink-200}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0 20px"
    height: "40px"
  tab-active:
    backgroundColor: "{colors.jade}"
    textColor: "{colors.ink-900}"
  pill:
    backgroundColor: "{colors.ink-750}"
    textColor: "{colors.ink-200}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "7px 16px 7px 12px"
  pill-filter-on:
    backgroundColor: "{colors.jade}"
    textColor: "{colors.ink-900}"
  pill-action:
    backgroundColor: "{colors.ink-750}"
    textColor: "{colors.jade}"
  tag:
    backgroundColor: "{colors.ink-750}"
    textColor: "{colors.ink-200}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "3px 11px 3px 8px"
  tag-ok:
    backgroundColor: "{colors.ink-750}"
    textColor: "{colors.jade}"
  tag-fail:
    backgroundColor: "{colors.live-red}"
    textColor: "{colors.paper}"
  boss-tile:
    backgroundColor: "{colors.ink-850}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
  boss-tile-head:
    backgroundColor: "{colors.ink-800}"
    padding: "10px"
  boss-thumb:
    backgroundColor: "{colors.ink-750}"
    rounded: "{rounded.none}"
    size: "52px"
  item-icon:
    backgroundColor: "{colors.ink-750}"
    rounded: "{rounded.none}"
    size: "20px"
  ribbon:
    backgroundColor: "{colors.ink-800}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    height: "44px"
  ribbon-outline:
    backgroundColor: "{colors.ink-600}"
  ribbon-rank:
    backgroundColor: "{colors.ink-600}"
    textColor: "{colors.paper}"
    width: "44px"
  ribbon-rank-best:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.ink-900}"
  meter:
    backgroundColor: "{colors.track}"
    rounded: "{rounded.none}"
    height: "10px"
  panel:
    backgroundColor: "{colors.ink-800}"
    textColor: "{colors.paper-dim}"
    rounded: "{rounded.none}"
    padding: "14px 16px"
  alert:
    backgroundColor: "{colors.ink-800}"
    textColor: "{colors.paper-dim}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "11px 16px"
  history-row:
    backgroundColor: "{colors.ink-900}"
    textColor: "{colors.paper}"
    typography: "{typography.caption}"
    padding: "9px 10px"
  history-row-active:
    backgroundColor: "{colors.ink-800}"
---

# Design System: bmiest gear upgrades

<!-- Design language v2, recorded from the shipped build of site/index.html on branch design/v2-dashboard
     (finish review: fixes, verdict pass, last item fixed in 578ba26; captures .impeccable/review/).
     Contract: .impeccable/surfaces/site-index-html.md (mock C, raid-night plan, .impeccable/mocks/).
     Family record: Bmiest/bmiest-design DESIGN.md. Sibling: twitch-overlay-v2 DESIGN.md.
     Scope tags: [family] = the shared v2 language, should match the family DESIGN.md;
     [wishlist] = this product only. site/tokens.css is a byte copy of an earlier overlay tokens.css;
     --live-red and --track live on :root in site/style.css. -->

## Overview

**Creative North Star: "The Raid-Night Plan"**

What matters this week comes first: the next raid night and what each of its bosses can drop. The page opens on a broadcast bug bar (bmiest, the run status, when it ran, GitHub, EN|NL), a title with the character line, then "Tonight 20:00" with its countdown, Heroic|Mythic tabs and the raid's bosses as tiles in kill order, each listing its upgrades; the tile holding the best upgrade is framed in gold. The week's best M+ dungeons follow as ranked ribbons beside the crests worth spending, and the full report, the gear and the how-it-works notes sit folded below. A right rail carries the run status, the changes since the previous run and the run history.

It speaks the family's v2 language in operate mode: the world lends type, palette, density and its slanted marks, while tabs, filters, tables and links stay standard controls. Colour is a state: jade is OK and active, gold is the single best upgrade, red is a failed run, rose is a warning.

Confirmed rejection (contract thesis): the generic KPI-cards-over-a-table dashboard. Every function of the old page stays, one fold away.

**Key Characteristics:**
- [family] Flat ink scale, Outfit + JetBrains Mono, from tokens.css.
- [family] Right-edge slant on ribbons, pills, tags, bars, boss heads and section caps; flush square blocks for the bug, the language switch and the tabs.
- [wishlist] Colour as run state: jade = OK/active, gold = best upgrade, red = failed run, rose = warning or stale.
- [wishlist] The raid night as a grid of boss tiles, the signature.
- [wishlist] Operate mode: standard controls dressed in the world's type and palette.

## Colors

The family's near-black ink ramp with jade as the healthy state, one gold for the best upgrade, rose for warnings and a darkened red for failure.

### Primary
- **Mistweaver Jade** (jade): [family] OK and active. The OK status block, the active tab, active filter pills and language block, the brand mark in the bug, section-head caps, upgrade percentages, the "Tonight" time, meter fills on the M+ list and crests, links, the fold chevron, the "no changes" check, sort arrows on the sorted column, focus rings (2px outline, 3px offset). Its ghost (jade-ghost) only for link underlines and text selection.
- **Deep Jade** (jade-deep): [wishlist use] the 1px inset ring on the history row being viewed: present but quieter than jade. (The meter's unmodified fallback fill also reads it; every shipped meter sets jade or gold.)

### Secondary
- **Podium Gold** (gold): [wishlist] the single best upgrade in view: the boss tile that holds it (2px gold frame), its item and percentage, the top-ranked dungeon ribbon (gold outline and rank block, ink text, gold meter), the best row in the full report.

### Tertiary
- **Failed Red** (live-red): [wishlist value, diverges from family] a failed run: the FAILED status block in the bug, the FAILED tag in history, the run-status panel's border when failed, the error alert's border and icon. Value is the family red darkened so paper text on it reaches 4.6:1 (the family's value gives about 3.4:1); as a border or icon on ink it holds 3.5:1.
- **Faded Rose** (rose): [wishlist] warnings and staleness: the Raider.IO staleness alert border and icon, a stale "as of" date on the character card, the date of a failed run in history, a failed report link.

### Neutral
- **Raid Night Black** (ink-900): page ground, the bug's brand block, inactive language blocks, ink text on jade and gold.
- **Table Ink** (ink-850): the top bar, boss-tile bodies, inactive tabs, the changes panel, history row hover and nested rows.
- **Panel Ink** (ink-800): boss-tile heads, ribbon bodies, alerts, the status panel, crest cards, the character card, the viewed history row.
- **Raised Ink** (ink-750): pills, tags, the bug's status and update blocks, item-icon and boss-head grounds.
- **Rule Ink** (ink-700): every 1px border and hairline: panels, tiles, tabs, table rules, history rows, folds, footer.
- **Outline Ink** (ink-600): the ribbon's slanted outline and rank block, dashed empty states, the scrollbar thumb.
- **Muted Ink** (ink-400): a boss's initial when it has no head, "nothing here" in a tile, idle sort arrows.
- **Caption Grey** (ink-300): captions, meta lines, table heads, raid group heads, fold hints, inactive language, footer.
- **Soft Grey** (ink-200): rail headings, pill and tag text, the update block, report links in history.
- **Paper** (paper): primary text; never pure white.
- **Faded Paper** (paper-dim): the lead, alert body, the raid line, slots, secondary item names.
- **Track** (track): [family value] the unfilled part of a meter, paper at 8%.

### Named Rules
**The Gold Is the Best Upgrade Rule.** [wishlist] Gold marks the one best upgrade in a view (tile, dungeon, table row) and nothing else: not a hover, not a tag colour, not a heading.

**The Red Means a Failed Run Rule.** [wishlist, diverges from family "Red Means On Air"] Red appears only where a run failed or errored. The dashboard is never live, so it carries no LIVE block; its red is a state, not a broadcast mark.

**The Jade Is Healthy Rule.** [wishlist] Jade is OK, active and gain; a warning is rose, never jade or gold.

## Typography

**Display Font:** Outfit (with Segoe UI, system-ui), weights 400 to 800, loaded once from index.html
**Label/Mono Font:** JetBrains Mono (with Cascadia Mono, Consolas), tabular figures
**Character:** One geometric sans from the 32px caps title down to 11px labels; the mono carries every figure the operator compares.

### Hierarchy
- **Title** (title): [wishlist] "Gear upgrades", once, uppercase; 28px under 720px. Beside it the character line at 16px (name 700 paper, meta ink-200) and a Raider.IO link.
- **Headline** (headline): [wishlist] the raid-night date ("Tonight 20:00"), uppercase, the time in jade tabular figures.
- **Headline sub** (headline-sub): [family] section heads ("Best M+ dungeons this week", "Spend crests now"), uppercase, behind an 11px slanted jade cap, a 13px caption 6px below.
- **Character** (character): [wishlist] the name on the gear fold's character card.
- **Status** (status): [wishlist] the "1 day ago" line in the run-status panel.
- **Fold** (fold): [family] folded section titles, jade on hover, followed by a 14px ink-300 hint.
- **Lead** (lead): the one-line page lead, max 72ch, paper-dim.
- **Body** (body): the page base; boss names and dungeon names at 14px/600.
- **Caption** (caption): captions, meta lines, history rows, alert actions, report links.
- **Bug** (bug): [family] the brand block, uppercase; 13px under 900px.
- **Control** (control): [wishlist] the status block, tabs and the language switch, uppercase; 12px for the bug blocks under 480px.
- **Label** (label): pills, tags and rail headings ("Run status", "Changes · Mythic", "Run history"), uppercase.
- **Label wide** (label-wide): raid group heads above the tiles and table heads, uppercase.
- **Numeric stat** (numeric-stat): [wishlist] the item level on the character card.
- **Numeric** (numeric): upgrade percentages, dates and times, the countdown, rank and level ranges; 11px for boss order numbers.

### Named Rules
**The Poster Voice Rule.** [family] Headings are Outfit 800 uppercase with tight tracking; only the bug and the control blocks share that weight.

**The Figure Is Mono Rule.** [family] A number the operator reads as a value (a percentage, an item level, a date, a countdown) is JetBrains Mono with tabular figures.

## Layout

[wishlist] One container, 1320px max, 24px gutters (16px under 900px). The top bar spans the viewport on ink-850 with a 1px ink-700 bottom rule; the page below stacks title, alerts and the grid 28px apart (24px under 900px).

The grid is a main column and a 340px right rail, 40px apart; under 1180px the rail drops below the main column and lays its blocks side by side (auto-fit, 280px minimum). In the main column, sections stack 40px apart: the raid night, then the M+ list and crests side by side (1.2fr / 1fr, 40px gap; one column under 900px), then the folds. Boss tiles fill an auto-fill grid with a 176px minimum and a 6px gap; under 720px each tile becomes a row (a 150px head beside its list), and under 480px a stacked card. The gear fold puts the 260px character card beside the gear table, stacking under 1280px; under 600px the gear table becomes one card per slot. Everything works at 360px; under 480px the bug takes the full width with the update block ellipsed.

## Elevation & Depth

[family] Flat. No drop shadows, no blur, no gradients. Depth comes from the ink ramp (ink-900 ground, ink-850 tile bodies and the bar, ink-800 tile heads and panels, ink-750 chips) and 1px ink-700 lines. `box-shadow` appears only as a drawn inset line: the gold frame doubling the best tile's border, the jade-deep ring on the viewed history row, and the 1px ink-700 outline on a boss head used as an item source; none is elevation.

### Named Rules
**The Flat Ink Rule.** [family] Surfaces separate by tone and 1px rules, never by shadow or blur.

## Shapes

[family] Corners are square. The signature is the right-edge slant, `clip-path: polygon(0 0, 100% 0, calc(100% - N) 100%, 0 100%)`: N is 11px on the dungeon ribbon, 9px on its rank block, 6px on pills, meters and 40-52px boss heads, 5px on tags, 4px on 28px boss heads and the section-head cap. Ribbons draw their 1px outline as a slanted outer clip one pixel larger than the inner one. The fold chevron is drawn (7px, two 2px jade strokes, -45deg closed, 45deg open). Empty states use a 1px dashed ink-600 border; every other border is solid. The bug, the language switch and the tabs are flush, square, gapless blocks. Icons are drawn SVG in one stroke family (2px, round caps).

### Named Rules
**The One Slant Rule.** [family] Slants go down and to the right, on the trailing edge only, and a slanted element never also gets rounded corners.

## Components

### Broadcast bug [family form, wishlist content]
Flush square blocks at 40px (34px under 900px): "bmiest" on ink-900 with the drawn broadcast mark in jade, the run status (jade with a check and ink text when OK, Failed Red with paper text when failed, ink-750 while unknown), and "Updated 1 day ago" on ink-750. GitHub link and EN|NL sit at the bar's right end.

### Language switch [family]
EN | NL as two flush blocks at the bug's height in control type; the active one solid jade with ink text, the other ink-900 with ink-300 text (paper on hover).

### Tabs [wishlist]
Heroic | Mythic as flush 40px blocks inside a 1px ink-700 frame, control type; selected is solid jade with ink text, the rest ink-850 with ink-200 text (ink-800 and paper on hover). Real tablist semantics.

### Boss tile [wishlist, the signature]
A square ink-850 cell with a 1px ink-700 border: a head strip on ink-800 (52px slanted boss head, order number in 11px mono ink-300, the name at 14px/600 clamped to two lines) over the upgrade list (20px item icon, item name with an ellipsis, percentage in mono jade). The best upgrade turns its item and percentage gold and frames its tile in gold. More than the shown items folds behind a small "+N more" link. A boss without upgrades keeps its place in kill order with a dashed ink-600 border on no fill; a boss without art shows its initial in ink-400.

### Boss head [family]
A boss portrait cropped to the top square on ink-750, slanted 6px (4px at 28px). Heads come from the race site's cut-outs; provenance is recorded in site/bossart.js.

### Ribbon [family]
The overlay's ribbon at 44px: a 1px slanted ink-600 outline around an ink-800 body, a square mono rank block (ink-600, paper) on the left, the dungeon name (14px/600) over a 13px ink-300 line. Beside it a 150px meter-and-percentage cell. The top dungeon takes the gold outline and a gold rank block with ink text.

### Meter [family]
A 10px slanted bar: track paper at 8%, fill jade, gold on the best dungeon.

### Pills and tags [family]
Pills: slanted ink-750 chips in label type; filter pills turn solid jade with ink text when on and carry a count; the action pill ("Show all 24") has jade text. Tags: smaller slanted chips for OK (jade text), Failed (Failed Red with paper text) and muted states.

### Section head [family]
Headline-sub type behind a slanted jade cap (11px wide, 0.9em tall), then a one-line 13px ink-300 caption.

### Panels [family]
Square ink-800 panels with a 1px ink-700 border: alerts (rose border for a warning, Failed Red for an error, drawn warning icon, bold paper title, action link at the end), the run-status panel (Failed Red border when failed), crest cards (36px icon, item, meta, meter), the character card (centred name, spec, mono item level, "as of" in rose when stale). The changes panel is the same on ink-850.

### Run history [wishlist]
Rows between 1px ink-700 rules: date and time in mono, the trigger in ink-300, the status tag at the end, the Heroic/Mythic report links below (jade when updated, rose when failed), GitHub at the right. Hover turns the row ink-850; the row being viewed is ink-800 with a 1px jade-deep inset ring. Runs with identical results collapse behind a jade "+N runs" fold.

### Folds [family]
Full-width folds between 1px ink-700 hairlines: the drawn jade chevron, the fold title (jade on hover) and its ink-300 hint. Inside: the full report as a sortable table (label-wide heads, mono percentages, a drawn sort arrow that turns jade on the sorted column), the gear, and how-this-works notes (max 64ch).

## Do's and Don'ts

### Do:
- **Do** take colours, fonts and spacing from tokens.css and the two `:root` additions in style.css.
- **Do** keep jade for OK, active and gain; gold for the single best upgrade; red for a failed run; rose for warnings and staleness.
- **Do** show the next raid night first, its bosses in kill order, every boss present even without upgrades.
- **Do** keep tabs, filters, tables and links as standard, accessible controls; the world only dresses them.
- **Do** slant the trailing edge of ribbons, pills, tags, meters, boss heads and caps; keep the bug, the language switch and the tabs flush and square.
- **Do** ship every string in English and Dutch (i18n.js); game names are never translated.
- **Do** build every node with textContent and validate every data-driven href or src.
- **Do** stop transitions under reduced motion.

### Don't:
- **Don't** put a coloured side stripe on cards, tiles or rows.
- **Don't** use text glyphs (★, ✓, ▸, emoji) as icons or disclosure marks; icons are drawn SVG.
- **Don't** add drop shadows, rounded cards, gradients or blur.
- **Don't** put a small caps label above a heading; rail and raid-group labels are the headings themselves.
- **Don't** use gold for more than one best in a view, or red for anything but a failure.
- **Don't** lead with KPI cards over a table; the full report stays one fold away.
