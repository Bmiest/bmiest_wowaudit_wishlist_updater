// Gear upgrade reports -- public run dashboard ("command center" layout).
//
// Vanilla JS, no build step. Everything is rendered with
// document.createElement()/textContent -- never innerHTML -- because the
// data this page reads (data/*.json) is produced by an automation pipeline
// that relays error strings from the external services it talks to.
// Those strings are untrusted and must always end up as literal text, never
// as markup.
//
// The layout (tiles, reports/crests/history grid, gear paper doll) is built
// around a single primary character -- everything in the design brief is
// phrased in the singular ("the top deduped result", "the equipped slots"),
// and the real data only ever has one. Reports/crests still tolerate a
// second character defensively (no crash), but the tiles and paper doll use
// characters[0].

// ---------------------------------------------------------------------
// Config: things older data does not tell us.
//
// Characters carry "class" and "spec" (e.g. "Priest" / "Holy"). Runs published
// before those fields existed fall back to this per-name spec label.
// ---------------------------------------------------------------------
const CONFIG = {
  characterSpecByName: {
    Shiftheal: "Holy Priest",
  },
};

// ---------------------------------------------------------------------
// Small DOM helpers -- the only way nodes get built on this page.
// ---------------------------------------------------------------------

/**
 * Create an element without ever touching innerHTML.
 * @param {string} tag
 * @param {{className?:string, text?:string, attrs?:Object<string,string>, on?:Object<string,Function>}} [opts]
 * @param {Array<Node|string|null|undefined>} [kids]
 */
function h(tag, opts, kids) {
  const node = document.createElement(tag);
  opts = opts || {};
  if (opts.className) node.className = opts.className;
  if (typeof opts.text === "string") node.textContent = opts.text;
  if (opts.attrs) {
    for (const [k, v] of Object.entries(opts.attrs)) {
      if (v !== null && v !== undefined) node.setAttribute(k, v);
    }
  }
  if (opts.on) {
    for (const [ev, fn] of Object.entries(opts.on)) node.addEventListener(ev, fn);
  }
  (kids || []).forEach((kid) => {
    if (kid === null || kid === undefined) return;
    node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  });
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

// ---------------------------------------------------------------------
// Security-critical validation. Nothing from data/*.json reaches an href
// unless it passes one of these.
// ---------------------------------------------------------------------

function safePrefixedUrl(value, prefix) {
  return typeof value === "string" && value.startsWith(prefix) ? value : null;
}

function isReportUrl(url) {
  return safePrefixedUrl(url, "https://questionablyepic.com/");
}

function isGithubUrl(url) {
  return safePrefixedUrl(url, "https://github.com/");
}

/** The character's Raider.io profile, built from validated parts, never taken from the data. */
function raiderioProfileUrl(character) {
  const region = String(character.region || "").toLowerCase();
  const realm = String(character.realm || "").toLowerCase();
  const name = String(character.name || "");
  if (!/^(us|eu|kr|tw|cn)$/.test(region) || !/^[a-z0-9-]+$/.test(realm)) return null;
  if (!/^\p{L}{2,12}$/u.test(name)) return null;
  return `https://raider.io/characters/${region}/${realm}/${encodeURIComponent(name)}`;
}

/** Build a Wowhead item URL ourselves from validated integer ids -- never
 * from a raw string handed over by the data file. */
function wowheadItemUrl(itemId, bonusIds, ilvl) {
  const id = Number(itemId);
  if (!Number.isInteger(id) || id <= 0) return null;
  let url = `https://www.wowhead.com/item=${id}`;
  const params = [];
  if (Array.isArray(bonusIds) && bonusIds.length > 0) {
    const nums = bonusIds.map(Number);
    if (nums.every((n) => Number.isInteger(n) && n >= 0)) {
      params.push(`bonus=${nums.join(":")}`);
    }
  }
  const lvl = Number(ilvl);
  if (Number.isInteger(lvl) && lvl > 0) params.push(`ilvl=${lvl}`);
  if (params.length) url += `?${params.join("&")}`;
  return url;
}

/**
 * Render a link if `url` is non-null (already validated by the caller),
 * otherwise render the same label as plain text. External links always get
 * target=_blank + rel=noopener noreferrer.
 */
function linkOrText(url, label, opts) {
  opts = opts || {};
  if (url) {
    return h("a", {
      className: opts.className,
      text: label,
      attrs: { href: url, target: "_blank", rel: "noopener noreferrer" },
    });
  }
  return h("span", { className: opts.className, text: label });
}

// ---------------------------------------------------------------------
// Formatting helpers.
// ---------------------------------------------------------------------

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function realmRegionLabel(realm, region) {
  if (!realm && !region) return "";
  const r = realm ? capitalize(String(realm)) : "";
  const g = region ? String(region).toUpperCase() : "";
  return [r, g].filter(Boolean).join(" ");
}

function specLabel(character) {
  const { spec, class: cls, name } = character;
  if (typeof spec === "string" && typeof cls === "string" && spec && cls) return `${spec} ${cls}`;
  // Runs published before the summary carried class/spec. hasOwn, so a character called
  // "constructor" doesn't pick up Object.prototype.
  return Object.hasOwn(CONFIG.characterSpecByName, name)
    ? CONFIG.characterSpecByName[name]
    : t("unknownSpec");
}

function parseDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function relativeTime(iso) {
  const d = parseDate(iso);
  if (!d) return t("unknownTime");
  const diffMs = Math.max(0, Date.now() - d.getTime());
  const sec = Math.round(diffMs / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (sec < 45) return t("justNow");
  const rtf = new Intl.RelativeTimeFormat(locale(), { numeric: "always" });
  if (min < 60) return rtf.format(-min, "minute");
  if (hr < 24) return rtf.format(-hr, "hour");
  if (day < 30) return rtf.format(-day, "day");
  return d.toLocaleDateString(locale(), { year: "numeric", month: "short", day: "numeric" });
}

function absoluteTime(iso) {
  const d = parseDate(iso);
  if (!d) return String(iso);
  return d.toLocaleString(locale(), { dateStyle: "full", timeStyle: "medium" });
}

const TRIGGERS = new Set(["schedule", "workflow_dispatch", "local"]);

function triggerLabel(trigger) {
  if (TRIGGERS.has(trigger)) return t(`trigger_${trigger}`);
  return trigger ? String(trigger) : t("unknownTrigger");
}

const SLOTS = new Set([
  "head", "neck", "shoulder", "back", "chest", "shirt", "tabard", "wrist", "hands", "waist",
  "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand",
]);

function slotLabel(slot) {
  return SLOTS.has(slot) ? t(`slot_${slot}`) : capitalize(String(slot || "").replace(/_/g, " "));
}

// Dungeon dropDifficulty is a Mythic+ key index, per the pipeline's spec.
const DUNGEON_KEY_LABELS = ["M0", "+2/3", "+4", "+5", "+6", "+7", "+8/9", "+10"];

function sourceLabel(dropLoc, dropDifficulty) {
  if (dropLoc === "Raid") {
    if (dropDifficulty === 2) return "Raid · Heroic";
    if (dropDifficulty === 3) return "Raid · Mythic";
    if (dropDifficulty !== null && dropDifficulty !== undefined && dropDifficulty !== "") {
      return t("raidDifficulty", { d: dropDifficulty });
    }
    return "Raid";
  }
  if (dropLoc === "Dungeon") {
    const idx = Number(dropDifficulty);
    if (Number.isInteger(idx) && idx >= 0 && idx < DUNGEON_KEY_LABELS.length) {
      return `Dungeon · ${DUNGEON_KEY_LABELS[idx]}`;
    }
    return "Dungeon";
  }
  if (dropLoc === "Delves") return "Delves";
  if (dropLoc === "Crafted") return "Crafted";
  return dropLoc ? String(dropLoc) : t("unknownSource");
}

// dropSource is the raid boss or dungeon name, from QE's item database (runs
// published before it existed, and Delves/crafted items, have none).
function dropSourceName(upgrade) {
  return typeof upgrade.dropSource === "string" && upgrade.dropSource ? upgrade.dropSource : null;
}

const DROP_LOC_FILTERS = ["All", "Raid", "Dungeon", "Delves", "Crafted"];
const REPORT_DIFFICULTIES = ["Heroic", "Mythic"];

function numOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

// ---------------------------------------------------------------------
// Upgrade computation: percDiff > 0, deduped per item, preferring the
// "max" dropType entry, else the highest percDiff.
// ---------------------------------------------------------------------
function computeUpgrades(results) {
  if (!Array.isArray(results)) return [];
  const byItem = new Map();
  for (const r of results) {
    if (typeof r.percDiff !== "number" || !(r.percDiff > 0)) continue;
    const key = r.item;
    const existing = byItem.get(key);
    if (!existing) {
      byItem.set(key, r);
      continue;
    }
    if (existing.dropType === "max") continue; // already locked in the max entry
    if (r.dropType === "max" || r.percDiff > existing.percDiff) byItem.set(key, r);
  }
  return Array.from(byItem.values()).sort((a, b) => b.percDiff - a.percDiff);
}

// ---------------------------------------------------------------------
// Power to gain: the biggest upgrade in every slot, added up. Rings and
// trinkets count their best two items; weapons count a two-hander or a
// one-hander plus an off-hand, whichever adds more. QE measures each gain
// against the current gear, so the total is an estimate, not a sim of the
// whole set. Results only carry a slot (QE's slot names) since it was added
// to the pipeline, so older runs give null.
// ---------------------------------------------------------------------
const PAIRED_SLOTS = new Set(["Finger", "Trinket"]);
const TWO_HAND_SLOTS = new Set(["2H Weapon"]);
const ONE_HAND_SLOTS = new Set(["1H Weapon", "WeaponMainHand"]);
const OFF_HAND_SLOTS = new Set(["Offhand", "Shield"]);

function computePowerToGain(upgrades) {
  const bySlot = new Map(); // slot -> gains, best first (upgrades come sorted)
  const weapons = { twoHand: [], oneHand: [], offHand: [] };
  for (const u of upgrades) {
    if (typeof u.slot !== "string" || !u.slot) continue;
    if (TWO_HAND_SLOTS.has(u.slot)) weapons.twoHand.push(u.percDiff);
    else if (ONE_HAND_SLOTS.has(u.slot)) weapons.oneHand.push(u.percDiff);
    else if (OFF_HAND_SLOTS.has(u.slot)) weapons.offHand.push(u.percDiff);
    else {
      if (!bySlot.has(u.slot)) bySlot.set(u.slot, []);
      bySlot.get(u.slot).push(u.percDiff);
    }
  }
  const picked = [];
  for (const [slot, gains] of bySlot) picked.push(...gains.slice(0, PAIRED_SLOTS.has(slot) ? 2 : 1));
  const twoHand = weapons.twoHand.slice(0, 1);
  const split = [...weapons.oneHand.slice(0, 1), ...weapons.offHand.slice(0, 1)];
  const sum = (gains) => gains.reduce((a, b) => a + b, 0);
  picked.push(...(sum(twoHand) >= sum(split) ? twoHand : split));
  if (picked.length === 0) return null;
  return { pct: sum(picked), items: picked.length };
}


/** The 16 gear slots that make up "average item level" -- shirt and tabard
 * are cosmetic and don't count. */
const ILVL_SLOTS = [
  "head", "neck", "shoulder", "back", "chest", "wrist", "hands", "waist",
  "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand",
];

function computeAvgIlvl(gear) {
  const bySlot = new Map((Array.isArray(gear) ? gear : []).map((g) => [g.slot, g]));
  const values = [];
  for (const slot of ILVL_SLOTS) {
    const g = bySlot.get(slot);
    const lvl = g ? numOrNull(g.ilvl) : null;
    if (lvl !== null) values.push(lvl);
  }
  if (values.length === 0) return { avg: null, count: 0, total: ILVL_SLOTS.length };
  const avg = Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  return { avg, count: values.length, total: ILVL_SLOTS.length };
}

/** Links to a run's QE reports ("Heroic  Mythic ✓") for the history rows. The check mark
 * marks the report that was uploaded (reports[].uploaded); only uploads get one. A report
 * whose generation failed is shown in the error colour. */
function reportLinksRow(reports, className) {
  const byDiff = new Map((Array.isArray(reports) ? reports : []).map((r) => [r.difficulty, r]));
  const row = h("span", { className: className || "report-links" });
  for (const diff of REPORT_DIFFICULTIES) {
    const r = byDiff.get(diff);
    if (!r) continue;
    const uploaded = r.uploaded === true && !r.error;
    const link = linkOrText(r.error ? null : isReportUrl(r.report_url), diff, {
      className: `report-link${r.error ? " report-link--fail" : ""}${uploaded ? " report-link--up" : ""}`,
    });
    if (uploaded) link.appendChild(h("span", { className: "report-link__check", text: " ✓" }));
    const title = r.error ? "reportError" : uploaded ? "reportTitleUploaded" : "reportTitle";
    link.setAttribute("title", t(title, { diff }));
    link.addEventListener("click", (e) => e.stopPropagation()); // don't also open the run
    row.appendChild(link);
  }
  return row;
}

// ---------------------------------------------------------------------
// Wowhead tooltips: config must exist before the script loads, and we
// inject the script ourselves so there is no inline <script> in the HTML.
// ---------------------------------------------------------------------
function setupWowheadTooltips() {
  window.whTooltips = { colorLinks: true, iconizeLinks: true, renameLinks: true };
  const script = document.createElement("script");
  script.src = "https://wow.zamimg.com/js/tooltips.js";
  script.async = true;
  script.addEventListener("load", refreshWowheadLinks);
  document.head.appendChild(script);
}

function refreshWowheadLinks() {
  if (window.$WowheadPower && typeof window.$WowheadPower.refreshLinks === "function") {
    window.$WowheadPower.refreshLinks();
  }
}

// ---------------------------------------------------------------------
// Wowhead name cache. renameLinks:true rewrites a link's text once its
// tooltip data arrives, asynchronously. Every re-render (a filter chip, a
// tab switch, "show all") rebuilds those links from scratch as plain
// "Item <id>" placeholders, which would otherwise revert an already-known
// name back to the placeholder until Wowhead answers again -- a visible
// flash on every interaction. A MutationObserver watches for Wowhead's own
// text edits and remembers them, so a rebuilt link can use the real name
// immediately instead of the placeholder.
// ---------------------------------------------------------------------
const wowheadNameCache = new Map();
const WOWHEAD_ITEM_ID_RE = /item=(\d+)/;
const PLACEHOLDER_NAME_RE = /^Item \d+$/;

/** The label to use for an item link: the data-provided name if there is
 * one, else a name Wowhead already resolved for this item id, else the
 * "Item <id>" placeholder Wowhead's renameLinks will replace. */
function cachedItemLabel(itemId, providedName) {
  if (typeof providedName === "string" && providedName) return providedName;
  const id = Number(itemId);
  if (Number.isInteger(id) && wowheadNameCache.has(id)) return wowheadNameCache.get(id);
  return Number.isInteger(id) ? `Item ${id}` : "Unknown item";
}

function recordWowheadLinkName(link) {
  if (!link || link.tagName !== "A") return;
  const href = link.getAttribute("href") || "";
  const m = WOWHEAD_ITEM_ID_RE.exec(href);
  if (!m) return;
  const txt = (link.textContent || "").trim();
  if (!txt || PLACEHOLDER_NAME_RE.test(txt) || txt === "Unknown item") return;
  wowheadNameCache.set(Number(m[1]), txt);
}

let wowheadObserver = null;
function observeWowheadNames() {
  if (wowheadObserver || typeof MutationObserver === "undefined") return;
  wowheadObserver = new MutationObserver((records) => {
    records.forEach((rec) => {
      let node = rec.target;
      if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
      if (!node) return;
      if (node.tagName === "A") {
        recordWowheadLinkName(node);
      } else if (typeof node.querySelectorAll === "function") {
        node.querySelectorAll('a[href*="wowhead.com/item="]').forEach(recordWowheadLinkName);
      }
    });
  });
  wowheadObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
}

// ---------------------------------------------------------------------
// Fetching.
// ---------------------------------------------------------------------
async function fetchJson(url) {
  let res;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (err) {
    throw new Error(`Network error loading ${url}`);
  }
  if (!res.ok) throw new Error(`${url} responded ${res.status}`);
  try {
    return await res.json();
  } catch (err) {
    throw new Error(`${url} was not valid JSON`);
  }
}

const RUN_ID_RE = /^[A-Za-z0-9_-]+$/;

function runDataUrl(id) {
  if (typeof id !== "string" || !RUN_ID_RE.test(id)) return null;
  return `data/runs/${id}.json`;
}

// ---------------------------------------------------------------------
// Error capsule -- shown inline, never a blank page.
// ---------------------------------------------------------------------
function errorCapsule(message) {
  return h("div", { className: "error-capsule", attrs: { role: "alert" } }, [
    h("span", { className: "error-capsule__icon", text: "!" }),
    h("span", { text: message }),
  ]);
}

// ---------------------------------------------------------------------
// App state.
// ---------------------------------------------------------------------
const state = {
  index: null,
  activeRunId: null,
  reportUi: new Map(), // "charIdx:difficulty" -> { loc, expanded }
  reportsTab: "Mythic", // shared tab selection for the single reports card
  historyExpanded: false,
  openGroups: new Set(), // history groups (by their newest run id) unfolded by the user
  runData: null, // the displayed run's full summary, kept to re-render on a language switch
  previousRuns: new Map(), // run id -> promise of its full summary (null if it failed to load)
};

function reportUiFor(key) {
  if (!state.reportUi.has(key)) state.reportUi.set(key, { loc: "All", expanded: false });
  return state.reportUi.get(key);
}

// ---------------------------------------------------------------------
// DOM refs (populated on DOMContentLoaded).
// ---------------------------------------------------------------------
let els = {};

function collectEls() {
  els = {
    headerCapsules: document.getElementById("headerCapsules"),
    headerStatus: document.getElementById("headerStatus"),
    headerUpdated: document.getElementById("headerUpdated"),
    headerMascot: document.getElementById("headerMascot"),
    globalError: document.getElementById("globalError"),
    viewingBanner: document.getElementById("viewingBanner"),
    tilesContainer: document.getElementById("tilesContainer"),
    reportsContainer: document.getElementById("reportsContainer"),
    crestContainer: document.getElementById("crestContainer"),
    gearContainer: document.getElementById("gearContainer"),
    historyContainer: document.getElementById("historyContainer"),
    historyShowMoreWrap: document.getElementById("historyShowMoreWrap"),
  };
}

// ---------------------------------------------------------------------
// Header (always reflects the true latest run from index.json).
// ---------------------------------------------------------------------
function renderHeader(indexData) {
  clear(els.headerCapsules);
  clear(els.headerStatus);

  const runs = Array.isArray(indexData.runs) ? indexData.runs : [];
  const latest = runs[0];
  if (!latest) {
    els.headerStatus.appendChild(h("span", { className: "pill pill--muted", text: t("noRuns") }));
    els.headerUpdated.textContent = "";
    return;
  }

  const chars = Array.isArray(latest.characters) ? latest.characters : [];
  chars.forEach((c) => {
    els.headerCapsules.appendChild(characterCapsule(c));
  });

  const statusPill = h("span", {
    className: `pill ${latest.ok ? "pill--ok" : "pill--fail"}`,
    text: latest.ok ? t("latestOk") : t("latestFailed"),
  });
  els.headerStatus.appendChild(statusPill);

  const ghUrl = isGithubUrl(latest.url);
  if (ghUrl) {
    els.headerStatus.appendChild(
      linkOrText(ghUrl, t("viewOnGithub"), { className: "pill pill--link" })
    );
  }

  const when = latest.finished_at || latest.started_at;
  els.headerUpdated.textContent = t("updated", { when: relativeTime(when) });
  els.headerUpdated.setAttribute("title", absoluteTime(when));
}

function characterCapsule(character) {
  const { name, realm, region } = character;
  const rr = realmRegionLabel(realm, region);
  const parts = [name || t("unknownCharacter"), specLabel(character)];
  if (rr) parts.push(rr);
  return h("span", { className: "capsule" }, [
    h("span", { className: "capsule__dot" }),
    h("span", { className: "capsule__text", text: parts.join(" · ") }),
  ]);
}

// ---------------------------------------------------------------------
// Run history: compact list, ~8 visible + "show more". Still the source
// for #run= deep links and click-to-select.
// ---------------------------------------------------------------------
const HISTORY_VISIBLE = 8;

/** Fold runs in a row that found the same (same digest, same OK/failed) into one group,
 * newest first. Runs from before the index carried a digest each stay on their own. */
function groupRuns(runs) {
  const groups = [];
  for (const run of runs) {
    const last = groups[groups.length - 1];
    const head = last && last[0];
    const same =
      head &&
      typeof run.digest === "string" &&
      run.digest === head.digest &&
      Boolean(run.ok) === Boolean(head.ok);
    if (same) last.push(run);
    else groups.push([run]);
  }
  return groups;
}

function renderHistory(indexData) {
  clear(els.historyContainer);
  clear(els.historyShowMoreWrap);
  const runs = Array.isArray(indexData.runs) ? indexData.runs : [];
  if (runs.length === 0) {
    els.historyContainer.appendChild(h("p", { className: "muted-note", text: t("noRunsRecorded") }));
    return;
  }

  const groups = groupRuns(runs);
  const shown = state.historyExpanded ? groups : groups.slice(0, HISTORY_VISIBLE);
  shown.forEach((group) => {
    const [head, ...rest] = group;
    const open = state.openGroups.has(head.id);
    els.historyContainer.appendChild(historyRow(head, rest.length ? { count: rest.length, open } : null));
    if (open) rest.forEach((run) => els.historyContainer.appendChild(historyRow(run, null, true)));
  });

  if (groups.length > HISTORY_VISIBLE) {
    const btn = h("button", {
      className: "pill pill--action",
      text: state.historyExpanded ? t("showFewer") : t("showAll", { n: runs.length }),
      attrs: { type: "button" },
    });
    btn.addEventListener("click", () => {
      state.historyExpanded = !state.historyExpanded;
      renderHistory(indexData);
    });
    els.historyShowMoreWrap.appendChild(btn);
  }

  updateHistorySelectionUI();
}

/** One history row. `fold` ({count, open}) adds the "+N runs with the same results" toggle
 * to a group's newest run; `nested` marks a run shown inside an unfolded group. */
function historyRow(run, fold, nested) {
  const row = h("div", {
    className: `history-row${nested ? " history-row--nested" : ""}`,
    attrs: { tabindex: "0", role: "link", "data-run-id": run.id },
  });
  row.addEventListener("click", () => navigateToRun(run.id));
  row.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      navigateToRun(run.id);
    }
  });

  row.appendChild(h("span", { className: "history-row__dot", attrs: { "aria-hidden": "true" } }));
  row.appendChild(
    h("span", {
      className: "history-row__time mono",
      text: relativeTime(run.started_at),
      attrs: { title: absoluteTime(run.started_at) },
    })
  );
  row.appendChild(h("span", { className: "history-row__trigger", text: triggerLabel(run.trigger) }));
  row.appendChild(
    h("span", { className: `pill pill--sm ${run.ok ? "pill--ok" : "pill--fail"}`, text: run.ok ? t("ok") : t("failed") })
  );

  const chars = Array.isArray(run.characters) ? run.characters : [];
  const allReports = chars.flatMap((c) => (Array.isArray(c.reports) ? c.reports : []));
  row.appendChild(reportLinksRow(allReports));

  if (fold) {
    const toggle = h("button", {
      className: `history-fold${fold.open ? " is-open" : ""}`,
      text: t("sameResults", { n: fold.count }),
      attrs: {
        type: "button",
        "aria-expanded": String(fold.open),
        title: fold.open ? t("sameResultsHide") : null,
      },
    });
    toggle.addEventListener("click", (e) => {
      e.stopPropagation(); // fold/unfold only, don't also open the run
      if (state.openGroups.has(run.id)) state.openGroups.delete(run.id);
      else state.openGroups.add(run.id);
      renderHistory(state.index);
    });
    row.appendChild(toggle);
  }

  const ghUrl = isGithubUrl(run.url);
  const footLink = linkOrText(ghUrl, "GitHub ↗", { className: "history-row__gh" });
  footLink.addEventListener("click", (e) => e.stopPropagation());
  row.appendChild(footLink);

  return row;
}

function updateHistorySelectionUI() {
  const rows = els.historyContainer.querySelectorAll(".history-row");
  rows.forEach((row) => {
    const isSelected = row.getAttribute("data-run-id") === state.activeRunId;
    row.classList.toggle("is-selected", isSelected);
    if (isSelected) row.setAttribute("aria-current", "true");
    else row.removeAttribute("aria-current");
  });
}

// ---------------------------------------------------------------------
// Viewing banner ("viewing run X - back to latest").
// ---------------------------------------------------------------------
function renderViewingBanner(runId, isLatest) {
  clear(els.viewingBanner);
  document.getElementById("reportsHeading").textContent = isLatest
    ? t("latestReports")
    : t("reportsFromRun");
  if (isLatest) {
    els.viewingBanner.hidden = true;
    return;
  }
  els.viewingBanner.hidden = false;
  els.viewingBanner.appendChild(h("span", { text: t("viewingRun") }));
  els.viewingBanner.appendChild(h("b", { className: "mono", text: runId }));
  const backBtn = h("button", {
    className: "pill pill--action",
    text: t("backToLatest"),
    attrs: { type: "button" },
  });
  backBtn.addEventListener("click", navigateToLatest);
  els.viewingBanner.appendChild(backBtn);
}

// ---------------------------------------------------------------------
// Peon mascot -- follows the DISPLAYED run (not necessarily the true
// latest), so it lives outside renderHeader() and is driven from
// renderRunData() and the loader error paths instead.
// ---------------------------------------------------------------------
function renderMascot(runOk) {
  clear(els.headerMascot);
  if (!runOk) {
    els.headerMascot.hidden = true;
    return;
  }
  els.headerMascot.hidden = false;

  const reduceMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let media;
  if (reduceMotion) {
    media = h("img", {
      className: "mascot__media",
      attrs: { src: "assets/peon-jobs-done.webp", alt: "Warcraft III peon: Jobs done" },
    });
  } else {
    media = document.createElement("video");
    media.className = "mascot__media";
    media.setAttribute("poster", "assets/peon-jobs-done.webp");
    media.setAttribute("src", "assets/peon-jobs-done.mp4");
    media.setAttribute("autoplay", "");
    media.setAttribute("loop", "");
    media.setAttribute("muted", "");
    media.setAttribute("playsinline", "");
    media.setAttribute("aria-label", "Warcraft III peon: Jobs done");
    media.setAttribute("role", "img");
    // Chrome only honours autoplay when the *property* is muted too, not
    // just the attribute.
    media.muted = true;
    media.autoplay = true;
    media.loop = true;
    media.playsInline = true;
  }

  els.headerMascot.appendChild(h("div", { className: "mascot-frame" }, [media]));

  if (media.tagName === "VIDEO") {
    const playPromise = media.play();
    if (playPromise && typeof playPromise.catch === "function") playPromise.catch(() => {});
  }
}

// ---------------------------------------------------------------------
// Stat tiles -- follow the displayed run, built from characters[0].
// ---------------------------------------------------------------------
function tile(label, kids) {
  return h("div", { className: "tile" }, [
    h("span", { className: "tile__label", text: label }),
    h("div", { className: "tile__body" }, kids),
  ]);
}

function renderTiles(fullData) {
  clear(els.tilesContainer);
  const character = (fullData.characters || [])[0];
  if (!character) {
    els.tilesContainer.appendChild(
      h("p", { className: "muted-note", text: t("noCharacterData") })
    );
    return;
  }

  els.tilesContainer.appendChild(tileBestMythic(character));
  els.tilesContainer.appendChild(tilePowerToGain(character));
  els.tilesContainer.appendChild(tileNextCrest(character));
  els.tilesContainer.appendChild(tileAvgIlvl(character));
  els.tilesContainer.appendChild(tileLastRun(fullData.run, character));
}

function tileBestMythic(character) {
  const reports = Array.isArray(character.reports) ? character.reports : [];
  const mythic = reports.find((r) => r.difficulty === "Mythic");
  const upgrades = mythic ? computeUpgrades(mythic.results) : [];
  if (upgrades.length === 0) {
    return tile(t("bestMythicUpgrade"), [h("span", { className: "tile__muted", text: t("noUpgrades") })]);
  }
  const top = upgrades[0];
  const url = wowheadItemUrl(top.item, null, top.level);
  const link = linkOrText(url, cachedItemLabel(top.item), { className: "tile__link" });
  const boss = dropSourceName(top);
  const detail = h("div", { className: "tile__detail" }, [
    h("span", { className: "pill pill--ilvl mono", text: Number.isFinite(top.level) ? String(top.level) : "?" }),
    h("span", { className: "tile__pct mono", text: fmtPct(top.percDiff) }),
    boss ? h("span", { className: "tile__rank", text: boss }) : null,
  ]);
  return tile(t("bestMythicUpgrade"), [link, detail]);
}

function tilePowerToGain(character) {
  const label = t("mythicPowerToGain");
  const reports = Array.isArray(character.reports) ? character.reports : [];
  const mythic = reports.find((r) => r.difficulty === "Mythic");
  const upgrades = mythic ? computeUpgrades(mythic.results) : [];
  if (upgrades.length === 0) {
    return tile(label, [h("span", { className: "tile__muted", text: t("noUpgrades") })]);
  }
  const power = computePowerToGain(upgrades);
  if (!power) {
    return tile(label, [h("span", { className: "tile__muted", text: t("notInRunData") })]);
  }
  return tile(label, [
    h("span", {
      className: "tile__big tile__big--jade mono",
      text: fmtPct(power.pct),
      attrs: { title: t("powerHint") },
    }),
    h("span", {
      className: "tile__muted",
      text: t("powerNote", { n: power.items }),
    }),
  ]);
}

/** Crest upgrades worth showing: a gain above zero, or no estimate at all (still unknown).
 * A +0.00% item costs crests for nothing, so it's left out. */
function usefulCrestUpgrades(upgrades) {
  return upgrades.filter((u) => {
    const g = numOrNull(u.gain_pct);
    return g === null || g > 0;
  });
}

function tileNextCrest(character) {
  const label = t("nextCrest");
  const upgrades = character.crest_upgrades;
  if (upgrades === null || upgrades === undefined) {
    return tile(label, [h("span", { className: "tile__muted", text: t("noEstimate") })]);
  }
  if (!Array.isArray(upgrades) || upgrades.length === 0) {
    return tile(label, [h("span", { className: "tile__muted", text: t("allUpgraded") })]);
  }
  const useful = usefulCrestUpgrades(upgrades);
  if (useful.length === 0) {
    return tile(label, [h("span", { className: "tile__muted", text: t("nothingWorthCrest") })]);
  }
  const u = useful[0];
  const url = wowheadItemUrl(u.item_id, null, u.level);
  const link = linkOrText(url, cachedItemLabel(u.item_id, u.name), { className: "tile__link" });
  const line = h("div", { className: "tile__crest-line" }, [
    h("span", { className: "tile__slot", text: `${slotLabel(String(u.slot || "").toLowerCase())} · ` }),
    link,
  ]);
  const rank = numOrNull(u.rank);
  const gain = numOrNull(u.gain_pct);
  const detail = h("div", { className: "tile__detail" }, [
    h("span", { className: "tile__rank mono", text: `${rank === null ? "?" : rank}/6 → 6/6` }),
    gain === null
      ? h("span", { className: "tile__muted", text: t("noEstimateLower") })
      : h("span", { className: "tile__pct tile__pct--gold mono", text: fmtPct(gain) }),
  ]);
  return tile(label, [line, detail]);
}

function tileAvgIlvl(character) {
  const { avg, count, total } = computeAvgIlvl(character.gear);
  const body = [h("span", { className: "tile__big mono", text: avg === null ? "?" : String(avg) })];
  if (count < total) {
    body.push(h("span", { className: "tile__muted", text: t("basedOnSlots", { count, total }) }));
  }
  return tile(t("avgIlvl"), body);
}

function tileLastRun(run, character) {
  if (!run) return tile(t("lastRun"), [h("span", { className: "tile__muted", text: t("unknown") })]);
  const when = run.finished_at || run.started_at;
  const body = [
    h("span", { className: "tile__big", text: relativeTime(when), attrs: { title: absoluteTime(when) } }),
    h("div", { className: "tile__detail" }, [
      h("span", { className: `pill pill--sm ${run.ok ? "pill--ok" : "pill--fail"}`, text: run.ok ? t("ok") : t("failed") }),
    ]),
  ];
  return tile(t("lastRun"), body);
}

// ---------------------------------------------------------------------
// Reports: one card, Heroic/Mythic tab switch (default Mythic).
// ---------------------------------------------------------------------
function renderReportsCard(character, charIdx) {
  clear(els.reportsContainer);
  const reports = Array.isArray(character.reports) ? character.reports : [];

  if (character.error) {
    els.reportsContainer.appendChild(errorCapsule(character.error));
  }
  if (character.skipped) {
    const label = typeof character.skipped === "string" ? t("skippedWhy", { why: character.skipped }) : t("skipped");
    els.reportsContainer.appendChild(h("span", { className: "pill pill--muted", text: label }));
  }
  if (Array.isArray(character.warnings) && character.warnings.length > 0) {
    const warnRow = h("div", { className: "warning-row" });
    character.warnings.forEach((w) => warnRow.appendChild(h("span", { className: "pill pill--warn", text: String(w) })));
    els.reportsContainer.appendChild(warnRow);
  }

  if (reports.length === 0) {
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: t("noReports") }));
    return;
  }

  const byDiff = new Map(reports.map((r) => [r.difficulty, r]));
  const available = REPORT_DIFFICULTIES.filter((d) => byDiff.has(d));
  if (available.length === 0) {
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: t("noReports") }));
    return;
  }
  if (!available.includes(state.reportsTab)) state.reportsTab = available[available.length - 1];

  const wrap = h("section", { className: "rcard-wrap" }, [
    h("span", { className: "rcard__cap", text: character.name || "Reports" }),
  ]);
  const inner = h("div", { className: "rcard" }, [h("div", { className: "rcard__in" })]);
  const body = inner.firstChild;
  wrap.appendChild(inner);

  const tabIds = available.map((d) => `tab-${charIdx}-${d}`);
  const panelIds = available.map((d) => `panel-${charIdx}-${d}`);

  const tablist = h("div", { className: "tablist", attrs: { role: "tablist", "aria-label": t("reportDifficulty") } });
  const tabButtons = [];
  available.forEach((diff, i) => {
    const selected = diff === state.reportsTab;
    const btn = h("button", {
      className: `tab${selected ? " is-selected" : ""}`,
      text: diff,
      attrs: {
        role: "tab",
        type: "button",
        id: tabIds[i],
        "aria-selected": String(selected),
        "aria-controls": panelIds[i],
        tabindex: selected ? "0" : "-1",
      },
    });
    btn.addEventListener("click", () => selectReportsTab(character, charIdx, diff));
    btn.addEventListener("keydown", (e) => onTabKeydown(e, available, i, character, charIdx));
    tabButtons.push(btn);
    tablist.appendChild(btn);
  });
  body.appendChild(tablist);

  available.forEach((diff, i) => {
    const panel = h("div", {
      className: "tabpanel",
      attrs: {
        role: "tabpanel",
        id: panelIds[i],
        "aria-labelledby": tabIds[i],
      },
    });
    panel.hidden = diff !== state.reportsTab;
    panel.appendChild(reportPanelContent(byDiff.get(diff), `${charIdx}:${diff}`));
    body.appendChild(panel);
  });

  els.reportsContainer.appendChild(wrap);
  refreshWowheadLinks(); // a tab switch rebuilds the whole card, links included
}

function onTabKeydown(e, available, i, character, charIdx) {
  let nextIndex = null;
  if (e.key === "ArrowRight") nextIndex = (i + 1) % available.length;
  else if (e.key === "ArrowLeft") nextIndex = (i - 1 + available.length) % available.length;
  else if (e.key === "Home") nextIndex = 0;
  else if (e.key === "End") nextIndex = available.length - 1;
  if (nextIndex === null) return;
  e.preventDefault();
  selectReportsTab(character, charIdx, available[nextIndex]);
  const tabs = Array.from(els.reportsContainer.querySelectorAll('[role="tab"]'));
  tabs[nextIndex]?.focus();
}

function selectReportsTab(character, charIdx, diff) {
  state.reportsTab = diff;
  renderReportsCard(character, charIdx);
  renderPaperdoll(character); // its per-slot upgrades follow the open tab
  refreshWowheadLinks();
}

function reportPanelContent(report, key) {
  const frag = h("div", { className: "report-panel" });

  const headRow = h("div", { className: "report-card__head" });
  const url = isReportUrl(report.report_url);
  headRow.appendChild(linkOrText(url, t("openReport"), { className: "report-card__link" }));

  if (report.error) {
    headRow.appendChild(h("span", { className: "pill pill--fail", text: t("error") }));
  }
  frag.appendChild(headRow);

  if (!report.error) frag.appendChild(changesBlock(report.difficulty));

  if (report.error) {
    frag.appendChild(h("p", { className: "report-card__error", text: String(report.error) }));
  }

  const upgrades = computeUpgrades(report.results);

  const filterRow = h("div", { className: "filter-row" });
  const ui = reportUiFor(key);
  const filterButtons = new Map();
  DROP_LOC_FILTERS.forEach((loc) => {
    const btn = h("button", {
      className: "pill pill--filter",
      text: loc === "All" ? t("filter_All") : loc,
      attrs: { type: "button", "aria-pressed": String(loc === ui.loc) },
    });
    btn.addEventListener("click", () => {
      ui.loc = loc;
      DROP_LOC_FILTERS.forEach((l) => {
        filterButtons.get(l).setAttribute("aria-pressed", String(l === loc));
        filterButtons.get(l).classList.toggle("is-active", l === loc);
      });
      renderRows();
    });
    if (loc === ui.loc) btn.classList.add("is-active");
    filterButtons.set(loc, btn);
    filterRow.appendChild(btn);
  });
  frag.appendChild(filterRow);

  // Follows the tab and the filter: "all Raid upgrades together are worth ...".
  const powerLine = h("p", { className: "power-line", attrs: { title: t("powerHint") } });
  frag.appendChild(powerLine);

  const rowsContainer = h("div", { className: "upgrade-rows" });
  frag.appendChild(rowsContainer);

  const toggleWrap = h("div", { className: "bars-toggle" });
  frag.appendChild(toggleWrap);

  const TOP_N = 10;

  function renderRows() {
    clear(rowsContainer);
    clear(toggleWrap);
    clear(powerLine);
    const filtered = ui.loc === "All" ? upgrades : upgrades.filter((u) => u.dropLoc === ui.loc);

    const power = computePowerToGain(filtered);
    powerLine.hidden = !power;
    if (power) {
      powerLine.append(
        h("span", { className: "power-line__label", text: t("powerToGain") }),
        h("span", { className: "power-line__pct mono", text: fmtPct(power.pct) }),
        h("span", {
          className: "power-line__note",
          text:
            ui.loc === "All"
              ? t("powerNote", { n: power.items })
              : t("powerNoteLoc", { n: power.items, loc: ui.loc }),
        })
      );
    }

    if (filtered.length === 0) {
      rowsContainer.appendChild(h("p", { className: "muted-note", text: t("noUpgradesFilter") }));
      return;
    }

    const maxPct = filtered.reduce((m, u) => Math.max(m, u.percDiff), 0.0001);
    const shown = ui.expanded ? filtered : filtered.slice(0, TOP_N);
    shown.forEach((u) => rowsContainer.appendChild(upgradeRow(u, maxPct)));

    if (filtered.length > TOP_N) {
      const toggleBtn = h("button", {
        className: "pill pill--action",
        text: ui.expanded ? t("showTop", { n: TOP_N }) : t("showAll", { n: filtered.length }),
        attrs: { type: "button" },
      });
      toggleBtn.addEventListener("click", () => {
        ui.expanded = !ui.expanded;
        renderRows();
      });
      toggleWrap.appendChild(toggleBtn);
    }

    // Filter/toggle rebuild these rows as fresh elements. cachedItemLabel()
    // already avoids a flash for names Wowhead resolved before, but the
    // freshly created <a> elements themselves still need this to pick up
    // colour/icon and any name not yet cached.
    refreshWowheadLinks();
  }

  renderRows();
  return frag;
}

function upgradeRow(upgrade, maxPct) {
  const url = wowheadItemUrl(upgrade.item, null, upgrade.level);
  const link = linkOrText(url, cachedItemLabel(upgrade.item), { className: "upgrade-row__item" });
  const ilvlPill = h("span", {
    className: "pill pill--ilvl mono",
    text: Number.isFinite(upgrade.level) ? String(upgrade.level) : "?",
  });

  const pct = Math.max(2, Math.min(100, (upgrade.percDiff / maxPct) * 100));
  const track = h("div", { className: "bar-track" });
  const fill = h("div", { className: "bar-fill" });
  fill.style.width = `${pct}%`;
  track.appendChild(fill);

  const boss = dropSourceName(upgrade);
  const where = sourceLabel(upgrade.dropLoc, upgrade.dropDifficulty);
  const source = h("span", {
    className: "upgrade-row__source",
    attrs: { title: boss ? `${boss} · ${where}` : where },
  }, [
    boss ? h("span", { className: "upgrade-row__boss", text: boss }) : null,
    h("span", { className: "upgrade-row__where", text: where }),
  ]);

  return h("div", { className: "upgrade-row" }, [
    link,
    ilvlPill,
    source,
    track,
    h("span", { className: "upgrade-row__pct mono", text: fmtPct(upgrade.percDiff) }),
  ]);
}

// ---------------------------------------------------------------------
// Crest sidebar: compact rows, built from crest_report/crest_upgrades.
// Both are optional and independent: crest_report is
// {difficulty, report_id, report_url} | null, crest_upgrades is a
// pre-sorted (desc, nulls last) array | null.
// ---------------------------------------------------------------------
function renderCrestSidebar(character) {
  clear(els.crestContainer);

  const report = character.crest_report;
  if (report && typeof report === "object") {
    const url = isReportUrl(report.report_url);
    const link = linkOrText(url, t("crestReport"), { className: "report-card__link" });
    if (typeof report.difficulty === "string" && report.difficulty) {
      link.setAttribute("title", t("crestReportTitle", { diff: report.difficulty }));
    }
    els.crestContainer.appendChild(h("div", { className: "report-card__head" }, [link]));
  }

  const upgrades = character.crest_upgrades;
  if (upgrades === null || upgrades === undefined) {
    els.crestContainer.appendChild(h("p", { className: "muted-note", text: t("noCrestEstimate") }));
    return;
  }
  if (!Array.isArray(upgrades) || upgrades.length === 0) {
    els.crestContainer.appendChild(h("p", { className: "muted-note", text: t("fullyUpgraded") }));
    return;
  }
  const useful = usefulCrestUpgrades(upgrades);
  if (useful.length === 0) {
    els.crestContainer.appendChild(h("p", { className: "muted-note", text: t("noCrestGain") }));
    return;
  }

  const maxGain = useful.reduce((m, u) => {
    const g = numOrNull(u.gain_pct);
    return g !== null && g > m ? g : m;
  }, 0.0001);

  const list = h("div", { className: "crest-compact-list" });
  useful.forEach((u) => list.appendChild(crestCompactRow(u, maxGain)));
  els.crestContainer.appendChild(list);
}

function crestCompactRow(u, maxGain) {
  const level = numOrNull(u.level);
  const maxLevel = numOrNull(u.max_level);
  const rank = numOrNull(u.rank);

  const url = wowheadItemUrl(u.item_id, null, u.level);
  const label = cachedItemLabel(u.item_id, u.name);
  const link = linkOrText(url, label, { className: "crest-compact-row__item" });

  const track = typeof u.track === "string" && u.track ? u.track : "?";
  const metaText = `${slotLabel(String(u.slot || "").toLowerCase())} · ${track} ${rank === null ? "?" : rank}/6 → 6/6 · ${level === null ? "?" : level}→${maxLevel === null ? "?" : maxLevel}`;
  const meta = h("span", { className: "crest-compact-row__meta", text: metaText });

  const gain = numOrNull(u.gain_pct);
  const barRow = h("div", { className: "crest-compact-row__bar-row" });
  if (gain === null) {
    barRow.appendChild(h("span", { className: "muted-note", text: t("noEstimate") }));
  } else {
    const pct = Math.max(2, Math.min(100, (gain / maxGain) * 100));
    const track2 = h("div", { className: "bar-track" });
    const fill = h("div", { className: "bar-fill bar-fill--gold" });
    fill.style.width = `${pct}%`;
    track2.appendChild(fill);
    barRow.appendChild(track2);
    barRow.appendChild(h("span", { className: "crest-row__pct mono", text: fmtPct(gain) }));
  }

  return h("div", { className: "crest-compact-row" }, [link, meta, barRow]);
}

// ---------------------------------------------------------------------
// "Since the previous run": upgrades that appeared or dropped out of this
// report, and gear that changed, against the closest older run with a
// working report for the same difficulty. The older run is fetched once.
// ---------------------------------------------------------------------

/** The closest run older than `runId` in the index with an error-free `difficulty` report. */
function previousRunWith(runId, difficulty) {
  const runs = state.index && Array.isArray(state.index.runs) ? state.index.runs : [];
  const at = runs.findIndex((r) => r.id === runId);
  if (at < 0) return null;
  for (const run of runs.slice(at + 1)) {
    const chars = Array.isArray(run.characters) ? run.characters : [];
    const reports = chars[0] && Array.isArray(chars[0].reports) ? chars[0].reports : [];
    if (reports.some((r) => r.difficulty === difficulty && !r.error)) return run;
  }
  return null;
}

/** The run's full summary, or null if it can't be loaded. Cached as a promise, so both
 * report tabs asking at once share one request. */
function loadPreviousRun(id) {
  if (!state.previousRuns.has(id)) {
    const url = runDataUrl(id);
    state.previousRuns.set(id, url ? fetchJson(url).catch(() => null) : Promise.resolve(null));
  }
  return state.previousRuns.get(id);
}

/** Diff two runs' first character: upgrades by item id (positive gains only) and gear by slot. */
function diffRuns(current, previous, difficulty) {
  const upgradesOf = (character) => {
    const reports = character && Array.isArray(character.reports) ? character.reports : [];
    const report = reports.find((r) => r.difficulty === difficulty);
    return new Map(computeUpgrades(report ? report.results : []).map((u) => [u.item, u]));
  };
  const now = upgradesOf(current);
  const before = upgradesOf(previous);
  const added = [...now.values()].filter((u) => !before.has(u.item));
  const removed = [...before.values()].filter((u) => !now.has(u.item));

  const gearOf = (character) =>
    new Map((character && Array.isArray(character.gear) ? character.gear : []).map((g) => [g.slot, g]));
  const gearNow = gearOf(current);
  const gearBefore = gearOf(previous);
  const gear = [];
  for (const slot of ILVL_SLOTS) {
    const a = gearBefore.get(slot);
    const b = gearNow.get(slot);
    if (!a || !b) continue;
    if (a.item_id !== b.item_id || a.ilvl !== b.ilvl) gear.push({ slot, before: a, after: b });
  }
  return { added, removed, gear };
}

function changesBlock(difficulty) {
  const box = h("div", { className: "changes" });
  const data = state.runData;
  const runId = data && data.run ? data.run.id : null;
  const prev = runId ? previousRunWith(runId, difficulty) : null;
  if (!prev) {
    box.appendChild(h("span", { className: "changes__title", text: t("sincePrevious") }));
    box.appendChild(h("p", { className: "changes__none", text: t("noPrevious") }));
    return box;
  }
  box.appendChild(
    h("span", {
      className: "changes__title",
      text: t("sincePreviousWhen", { when: relativeTime(prev.started_at) }),
      attrs: { title: absoluteTime(prev.started_at) },
    })
  );
  const body = h("div", { className: "changes__body" });
  box.appendChild(body);

  loadPreviousRun(prev.id).then((previous) => {
    // The page may have moved on (another run, another tab) while this loaded.
    if (!box.isConnected) return;
    if (!previous) {
      body.appendChild(h("p", { className: "changes__none", text: t("previousUnavailable") }));
      return;
    }
    const current = (data.characters || [])[0];
    const { added, removed, gear } = diffRuns(current, (previous.characters || [])[0], difficulty);
    if (!added.length && !removed.length && !gear.length) {
      body.appendChild(h("p", { className: "changes__none", text: t("noChanges") }));
      return;
    }
    const itemList = (items, mod) =>
      items.map((u) =>
        h("span", { className: `changes__item changes__item--${mod}` }, [
          linkOrText(wowheadItemUrl(u.item, null, u.level), cachedItemLabel(u.item), {
            className: "changes__link",
          }),
          h("span", { className: "changes__pct mono", text: fmtPct(u.percDiff) }),
        ])
      );
    const line = (label, mod, kids) =>
      h("div", { className: "changes__line" }, [
        h("span", { className: `changes__tag changes__tag--${mod}`, text: label }),
        h("div", { className: "changes__items" }, kids),
      ]);
    if (added.length) body.appendChild(line(t("changesNew"), "new", itemList(added, "new")));
    if (removed.length) body.appendChild(line(t("changesGone"), "gone", itemList(removed, "gone")));
    if (gear.length) {
      body.appendChild(
        line(
          t("changesGear"),
          "gear",
          // Same item: its item level moved. Another item: name it.
          gear.map(({ slot, before, after }) => {
            const ilvls = `${before.ilvl ?? "?"} → ${after.ilvl ?? "?"}`;
            const swapped = before.item_id !== after.item_id;
            return h("span", { className: "changes__item" }, [
              h("span", { className: "changes__slot", text: `${slotLabel(slot)} ` }),
              swapped
                ? h("span", {
                    text: `${cachedItemLabel(before.item_id, before.name)} → ${cachedItemLabel(after.item_id, after.name)}`,
                    attrs: { title: ilvls },
                  })
                : h("span", {
                    className: "mono",
                    text: ilvls,
                    attrs: { title: cachedItemLabel(after.item_id, after.name) },
                  }),
            ]);
          })
        )
      );
    }
    refreshWowheadLinks();
  });
  return box;
}

// ---------------------------------------------------------------------
// Gear: WoW-style paper doll. Shirt and tabard are cosmetic and left out,
// so the columns are rebalanced to seven slots each. Under every slot: the
// best upgrade for it in the report tab that's open (rings and trinkets:
// the best two, in order), the same picks "power to gain" adds up.
// ---------------------------------------------------------------------
const PAPERDOLL_LEFT = ["head", "neck", "shoulder", "back", "chest", "wrist", "hands"];
const PAPERDOLL_RIGHT = ["waist", "legs", "feet", "finger1", "finger2", "trinket1", "trinket2"];
const PAPERDOLL_WEAPONS = ["main_hand", "off_hand"];

// QE's slot names (results[].slot) -> paper-doll slots, in fill order.
const QE_SLOT_TO_GEAR = {
  Head: ["head"],
  Neck: ["neck"],
  Shoulder: ["shoulder"],
  Back: ["back"],
  Chest: ["chest"],
  Wrist: ["wrist"],
  Hands: ["hands"],
  Waist: ["waist"],
  Legs: ["legs"],
  Feet: ["feet"],
  Finger: ["finger1", "finger2"],
  Trinket: ["trinket1", "trinket2"],
  "2H Weapon": ["main_hand"],
  "1H Weapon": ["main_hand"],
  WeaponMainHand: ["main_hand"],
  Offhand: ["off_hand"],
  Shield: ["off_hand"],
};

/** slot -> best upgrade for it in the open report tab. Upgrades come sorted best first.
 * A ring or trinket that's a better copy of one you wear goes under that one. */
function bestUpgradeBySlot(character, gearBySlot) {
  const reports = Array.isArray(character.reports) ? character.reports : [];
  const report = reports.find((r) => r.difficulty === state.reportsTab && !r.error);
  const bySlot = new Map();
  if (!report) return bySlot;
  for (const u of computeUpgrades(report.results)) {
    const targets = Object.hasOwn(QE_SLOT_TO_GEAR, u.slot) ? QE_SLOT_TO_GEAR[u.slot] : [];
    const wearing = (slot) => gearBySlot.get(slot)?.item_id === u.item;
    const ordered = [...targets.filter(wearing), ...targets.filter((slot) => !wearing(slot))];
    const free = ordered.find((slot) => !bySlot.has(slot));
    if (free) bySlot.set(free, u);
  }
  return bySlot;
}

function paperdollSlot(slot, bySlot, best) {
  const g = bySlot.get(slot);
  const classes = ["pd-slot"];

  if (!g) {
    classes.push("pd-slot--empty");
    return h("div", { className: classes.join(" ") }, [
      h("span", { className: "pd-slot__label", text: slotLabel(slot) }),
    ]);
  }

  const url = wowheadItemUrl(g.item_id, g.bonus_ids, g.ilvl);
  const link = linkOrText(url, cachedItemLabel(g.item_id, g.name), { className: "pd-slot__item" });
  const ilvlPill = h("span", {
    className: "pill pill--ilvl mono pd-slot__ilvl",
    text: Number.isFinite(g.ilvl) ? String(g.ilvl) : "?",
  });

  const main = h("div", { className: "pd-slot__main" }, [link, ilvlPill]);
  const up = best.get(slot);
  if (up) {
    main.appendChild(
      h(
        "div",
        {
          className: "pd-slot__up",
          attrs: { title: t("bestForSlot", { diff: state.reportsTab }) },
        },
        [
          h("span", { className: "pd-slot__up-name" }, [
            h("span", { className: "pd-slot__up-arrow", text: "↑ ", attrs: { "aria-hidden": "true" } }),
            linkOrText(wowheadItemUrl(up.item, null, up.level), cachedItemLabel(up.item), {
              className: "pd-slot__up-item",
            }),
          ]),
          h("span", { className: "pd-slot__up-ilvl mono", text: Number.isFinite(up.level) ? String(up.level) : "" }),
          h("span", { className: "pd-slot__up-pct mono", text: fmtPct(up.percDiff) }),
        ]
      )
    );
  }

  return h("div", { className: classes.join(" ") }, [
    h("span", { className: "pd-slot__label", text: slotLabel(slot) }),
    main,
  ]);
}

function renderPaperdoll(character) {
  clear(els.gearContainer);

  const gear = Array.isArray(character.gear) ? character.gear : [];
  const bySlot = new Map(gear.map((g) => [g.slot, g]));
  const best = bestUpgradeBySlot(character, bySlot);

  const idBlock = h("div", { className: "pd-id" }, [
    h("div", { className: "pd-id__name", text: character.name || t("unknownCharacter") }),
    h("div", { className: "pd-id__spec", text: specLabel(character) }),
  ]);
  const { avg, count, total } = computeAvgIlvl(gear);
  const ilvlLine = h("div", { className: "pd-id__ilvl" }, [
    h("span", { text: t("avgIlvlPrefix") }),
    h("b", { className: "mono", text: avg === null ? "?" : String(avg) }),
  ]);
  if (count < total) {
    ilvlLine.appendChild(h("span", { className: "pd-id__ilvl-note", text: t("slotsNote", { count, total }) }));
  }
  idBlock.appendChild(ilvlLine);
  // When the gear source last read the character (Raider.io's crawl time). Older runs lack it.
  // More than a day old turns it gold: QE then measured upgrades against gear that may have
  // changed since.
  const profileUrl = raiderioProfileUrl(character);
  document.getElementById("gearSourceLink").setAttribute("href", profileUrl || "https://raider.io");
  if (typeof character.gear_as_of === "string" && character.gear_as_of) {
    const read = parseDate(character.gear_as_of);
    const stale = read !== null && Date.now() - read.getTime() > DAY_MS;
    const asOf = h("div", {
      className: `pd-id__asof${stale ? " pd-id__asof--stale" : ""}`,
      text: t("raiderioRead", { when: relativeTime(character.gear_as_of) }),
    });
    asOf.setAttribute("title", absoluteTime(character.gear_as_of));
    idBlock.appendChild(asOf);
    if (stale) {
      idBlock.appendChild(
        h("span", {
          className: "pill pill--warn pill--sm pd-id__stale",
          text: t("gearStale"),
          attrs: { title: t("gearStaleTitle") },
        })
      );
    }
  }
  // Raider.io's update button is meant for people; this pipeline never presses it (their API
  // terms forbid automating unpublished endpoints), so offer it as a manual link.
  if (profileUrl) {
    idBlock.appendChild(
      linkOrText(profileUrl, t("updateOnRaiderio"), { className: "pill pill--link pill--sm pd-id__update" })
    );
  }

  const column = (slots, className) =>
    h("div", { className }, slots.map((slot) => paperdollSlot(slot, bySlot, best)));
  const doll = h("div", { className: "paperdoll" }, [
    idBlock,
    column(PAPERDOLL_LEFT, "pd-col pd-col--left"),
    column(PAPERDOLL_RIGHT, "pd-col pd-col--right"),
    column(PAPERDOLL_WEAPONS, "pd-weapons"),
  ]);
  els.gearContainer.appendChild(doll);
}

// ---------------------------------------------------------------------
// Top-level render: tiles + reports + crests + gear, all built from a full
// run summary and all following the displayed run together.
// ---------------------------------------------------------------------
function renderRunData(fullData) {
  state.runData = fullData;
  clear(els.reportsContainer);
  clear(els.crestContainer);
  clear(els.gearContainer);
  clear(els.tilesContainer);
  renderMascot(Boolean(fullData.run && fullData.run.ok === true));

  const characters = Array.isArray(fullData.characters) ? fullData.characters : [];
  if (characters.length === 0) {
    els.reportsContainer.appendChild(errorCapsule(t("runNoCharacterData")));
    return;
  }

  renderTiles(fullData);

  const character = characters[0];
  renderReportsCard(character, 0);
  renderCrestSidebar(character);
  renderPaperdoll(character);

  refreshWowheadLinks();
}

// ---------------------------------------------------------------------
// Loading orchestration.
// ---------------------------------------------------------------------
function showGlobalError(message) {
  clear(els.globalError);
  els.globalError.hidden = false;
  els.globalError.appendChild(errorCapsule(message));
}

function clearGlobalError() {
  els.globalError.hidden = true;
  clear(els.globalError);
}

function clearAllRunViews() {
  state.runData = null;
  clear(els.tilesContainer);
  clear(els.reportsContainer);
  clear(els.crestContainer);
  clear(els.gearContainer);
  renderMascot(false);
}

async function loadLatest() {
  state.activeRunId = state.index && state.index.runs && state.index.runs[0] ? state.index.runs[0].id : null;
  renderViewingBanner(null, true);
  updateHistorySelectionUI();
  try {
    const data = await fetchJson("data/latest.json");
    state.activeRunId = data.run && data.run.id ? data.run.id : state.activeRunId;
    updateHistorySelectionUI();
    clearGlobalError();
    renderRunData(data);
  } catch (err) {
    clearAllRunViews();
    els.reportsContainer.appendChild(errorCapsule(t("couldNotLoadLatest", { msg: err.message })));
  }
}

async function selectRun(id) {
  const url = runDataUrl(id);
  if (!url) {
    clearAllRunViews();
    els.reportsContainer.appendChild(errorCapsule(t("invalidRunId", { id })));
    return;
  }
  const isLatest =
    state.index && state.index.runs && state.index.runs[0] && state.index.runs[0].id === id;
  state.activeRunId = id;
  renderViewingBanner(id, Boolean(isLatest));
  updateHistorySelectionUI();
  try {
    const data = await fetchJson(url);
    clearGlobalError();
    renderRunData(data);
  } catch (err) {
    clearAllRunViews();
    els.reportsContainer.appendChild(errorCapsule(t("couldNotLoadRun", { id, msg: err.message })));
  }
}

function getRunIdFromHash() {
  const m = /^#run=([A-Za-z0-9_-]+)$/.exec(location.hash);
  return m ? m[1] : null;
}

function applyHash() {
  const id = getRunIdFromHash();
  if (id) selectRun(id);
  else loadLatest();
}

function navigateToRun(id) {
  if (location.hash === `#run=${id}`) {
    applyHash();
    return;
  }
  location.hash = `run=${id}`;
}

function navigateToLatest() {
  if (location.hash) {
    history.pushState("", document.title, location.pathname + location.search);
  }
  applyHash();
}

// ---------------------------------------------------------------------
// Language switch (EN | NL). Switching redraws everything from what's
// already loaded; nothing is fetched again.
// ---------------------------------------------------------------------
function applyLanguage() {
  applyStaticText();
  // The <h1> is the single source of truth for the page title; the static
  // <title> in the HTML is only the no-JS fallback.
  const titleH1 = document.getElementById("pageTitle");
  if (titleH1 && titleH1.textContent) document.title = titleH1.textContent;
  document.querySelectorAll("#langSwitch [data-lang]").forEach((btn) => {
    const on = btn.getAttribute("data-lang") === lang();
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-pressed", String(on));
  });
}

function setupLanguageSwitch() {
  document.querySelectorAll("#langSwitch [data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.getAttribute("data-lang");
      if (next === lang()) return;
      setLang(next);
      applyLanguage();
      rerender();
    });
  });
}

function rerender() {
  if (!state.index) return;
  renderHeader(state.index);
  renderHistory(state.index);
  const runs = state.index.runs || [];
  const isLatest = !state.activeRunId || (runs[0] && runs[0].id === state.activeRunId);
  renderViewingBanner(state.activeRunId, isLatest);
  if (state.runData) renderRunData(state.runData);
}

// ---------------------------------------------------------------------
// Init.
// ---------------------------------------------------------------------
async function init() {
  collectEls();
  applyLanguage();
  setupLanguageSwitch();
  setupWowheadTooltips();
  observeWowheadNames();

  let indexData;
  try {
    indexData = await fetchJson("data/index.json");
  } catch (err) {
    showGlobalError(t("couldNotLoadIndex", { msg: err.message }));
    els.headerStatus.appendChild(h("span", { className: "pill pill--fail", text: t("unavailable") }));
    els.historyContainer.appendChild(h("p", { className: "muted-note", text: t("historyUnavailable") }));
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: t("reportsUnavailable") }));
    return;
  }

  if (!indexData || !Array.isArray(indexData.runs)) {
    showGlobalError(t("indexFormat"));
    return;
  }

  state.index = indexData;
  renderHeader(indexData);
  renderHistory(indexData);

  window.addEventListener("hashchange", applyHash);
  applyHash();
}

document.addEventListener("DOMContentLoaded", init);
