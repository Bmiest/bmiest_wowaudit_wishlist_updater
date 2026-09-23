// WoWAudit wishlist updater -- public run dashboard ("command center" layout).
//
// Vanilla JS, no build step. Everything is rendered with
// document.createElement()/textContent -- never innerHTML -- because the
// data this page reads (data/*.json) is produced by an automation pipeline
// that relays error strings from external services (WoWAudit, QE Live).
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
  unknownSpecLabel: "Unknown spec",
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
    : CONFIG.unknownSpecLabel;
}

function parseDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function relativeTime(iso) {
  const d = parseDate(iso);
  if (!d) return "unknown time";
  const diffMs = Math.max(0, Date.now() - d.getTime());
  const sec = Math.round(diffMs / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (sec < 45) return "just now";
  if (min < 60) return `${min} minute${min === 1 ? "" : "s"} ago`;
  if (hr < 24) return `${hr} hour${hr === 1 ? "" : "s"} ago`;
  if (day < 30) return `${day} day${day === 1 ? "" : "s"} ago`;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function absoluteTime(iso) {
  const d = parseDate(iso);
  if (!d) return String(iso);
  return d.toLocaleString(undefined, { dateStyle: "full", timeStyle: "medium" });
}

const TRIGGER_LABELS = {
  schedule: "Scheduled",
  workflow_dispatch: "Manual run",
  local: "Local run",
};

function triggerLabel(trigger) {
  return TRIGGER_LABELS[trigger] || (trigger ? String(trigger) : "Unknown trigger");
}

const SLOT_LABELS = {
  head: "Head",
  neck: "Neck",
  shoulder: "Shoulders",
  back: "Back",
  chest: "Chest",
  shirt: "Shirt",
  tabard: "Tabard",
  wrist: "Wrists",
  hands: "Hands",
  waist: "Waist",
  legs: "Legs",
  feet: "Feet",
  finger1: "Ring 1",
  finger2: "Ring 2",
  trinket1: "Trinket 1",
  trinket2: "Trinket 2",
  main_hand: "Main hand",
  off_hand: "Off hand",
};

function slotLabel(slot) {
  return SLOT_LABELS[slot] || capitalize(String(slot || "").replace(/_/g, " "));
}

// Dungeon dropDifficulty is a Mythic+ key index, per the pipeline's spec.
const DUNGEON_KEY_LABELS = ["M0", "+2/3", "+4", "+5", "+6", "+7", "+8/9", "+10"];

function sourceLabel(dropLoc, dropDifficulty) {
  if (dropLoc === "Raid") {
    if (dropDifficulty === 2) return "Raid · Heroic";
    if (dropDifficulty === 3) return "Raid · Mythic";
    if (dropDifficulty !== null && dropDifficulty !== undefined && dropDifficulty !== "") {
      return `Raid · difficulty ${dropDifficulty}`;
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
  return dropLoc ? String(dropLoc) : "Unknown source";
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

/** Per-difficulty check marks ("H ✓  M ✓"), shared by the LAST RUN tile and
 * the compact history rows. Only difficulties actually present are shown. */
function difficultyChecks(reports) {
  const byDiff = new Map((Array.isArray(reports) ? reports : []).map((r) => [r.difficulty, r]));
  const out = [];
  for (const diff of REPORT_DIFFICULTIES) {
    const r = byDiff.get(diff);
    if (!r) continue;
    const letter = diff.charAt(0);
    let state = "muted";
    let symbol = "–"; // – not imported / report-only
    let title = `${diff}: not imported`;
    if (r.error) {
      state = "fail";
      symbol = "✗"; // ✗
      title = `${diff}: error`;
    } else if (r.uploaded_via) {
      state = "ok";
      symbol = "✓"; // ✓
      title = `${diff}: imported`;
    }
    out.push({ letter, symbol, state, title, url: isReportUrl(r.report_url) });
  }
  return out;
}

function difficultyChecksRow(reports, className) {
  const row = h("span", { className: className || "diff-checks" });
  difficultyChecks(reports).forEach((d) => {
    row.appendChild(
      h("span", {
        className: `diff-check diff-check--${d.state}`,
        text: `${d.letter} ${d.symbol}`,
        attrs: { title: d.title },
      })
    );
  });
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
    els.headerStatus.appendChild(h("span", { className: "pill pill--muted", text: "No runs yet" }));
    els.headerUpdated.textContent = "";
    return;
  }

  const chars = Array.isArray(latest.characters) ? latest.characters : [];
  chars.forEach((c) => {
    els.headerCapsules.appendChild(characterCapsule(c));
  });

  const statusPill = h("span", {
    className: `pill ${latest.ok ? "pill--ok" : "pill--fail"}`,
    text: latest.ok ? "Latest run OK" : "Latest run failed",
  });
  els.headerStatus.appendChild(statusPill);

  const ghUrl = isGithubUrl(latest.url);
  if (ghUrl) {
    els.headerStatus.appendChild(
      linkOrText(ghUrl, "View on GitHub", { className: "pill pill--link" })
    );
  }

  const when = latest.finished_at || latest.started_at;
  els.headerUpdated.textContent = `updated ${relativeTime(when)}`;
  els.headerUpdated.setAttribute("title", absoluteTime(when));
}

function characterCapsule(character) {
  const { name, realm, region } = character;
  const rr = realmRegionLabel(realm, region);
  const parts = [name || "Unknown character", specLabel(character)];
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

function renderHistory(indexData) {
  clear(els.historyContainer);
  clear(els.historyShowMoreWrap);
  const runs = Array.isArray(indexData.runs) ? indexData.runs : [];
  if (runs.length === 0) {
    els.historyContainer.appendChild(h("p", { className: "muted-note", text: "No runs recorded yet." }));
    return;
  }

  const shown = state.historyExpanded ? runs : runs.slice(0, HISTORY_VISIBLE);
  shown.forEach((run) => {
    els.historyContainer.appendChild(historyRow(run));
  });

  if (runs.length > HISTORY_VISIBLE) {
    const btn = h("button", {
      className: "pill pill--action",
      text: state.historyExpanded ? "Show fewer" : `Show all ${runs.length}`,
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

function historyRow(run) {
  const row = h("div", {
    className: "history-row",
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
    h("span", { className: `pill pill--sm ${run.ok ? "pill--ok" : "pill--fail"}`, text: run.ok ? "OK" : "Failed" })
  );

  const chars = Array.isArray(run.characters) ? run.characters : [];
  const allReports = chars.flatMap((c) => (Array.isArray(c.reports) ? c.reports : []));
  row.appendChild(difficultyChecksRow(allReports, "diff-checks diff-checks--sm"));

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
    ? "Latest reports"
    : "Reports from this run";
  if (isLatest) {
    els.viewingBanner.hidden = true;
    return;
  }
  els.viewingBanner.hidden = false;
  els.viewingBanner.appendChild(h("span", { text: "Viewing run " }));
  els.viewingBanner.appendChild(h("b", { className: "mono", text: runId }));
  const backBtn = h("button", {
    className: "pill pill--action",
    text: "Back to latest",
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
      h("p", { className: "muted-note", text: "No character data for this run." })
    );
    return;
  }

  els.tilesContainer.appendChild(tileBestMythic(character));
  els.tilesContainer.appendChild(tileNextCrest(character));
  els.tilesContainer.appendChild(tileAvgIlvl(character));
  els.tilesContainer.appendChild(tileLastRun(fullData.run, character));
}

function tileBestMythic(character) {
  const reports = Array.isArray(character.reports) ? character.reports : [];
  const mythic = reports.find((r) => r.difficulty === "Mythic");
  const upgrades = mythic ? computeUpgrades(mythic.results) : [];
  if (upgrades.length === 0) {
    return tile("Best Mythic upgrade", [h("span", { className: "tile__muted", text: "No upgrades found" })]);
  }
  const top = upgrades[0];
  const url = wowheadItemUrl(top.item, null, top.level);
  const link = linkOrText(url, cachedItemLabel(top.item), { className: "tile__link" });
  const detail = h("div", { className: "tile__detail" }, [
    h("span", { className: "pill pill--ilvl mono", text: Number.isFinite(top.level) ? String(top.level) : "?" }),
    h("span", { className: "tile__pct mono", text: `+${top.percDiff.toFixed(2)}%` }),
  ]);
  return tile("Best Mythic upgrade", [link, detail]);
}

function tileNextCrest(character) {
  const upgrades = character.crest_upgrades;
  if (upgrades === null || upgrades === undefined) {
    return tile("Next crest", [h("span", { className: "tile__muted", text: "No estimate" })]);
  }
  if (!Array.isArray(upgrades) || upgrades.length === 0) {
    return tile("Next crest", [h("span", { className: "tile__muted", text: "All upgraded" })]);
  }
  const u = upgrades[0];
  const url = wowheadItemUrl(u.item_id, null, u.level);
  const label = cachedItemLabel(u.item_id, u.name);
  const link = linkOrText(url, label, { className: "tile__link" });
  const line = h("div", { className: "tile__crest-line" }, [
    h("span", { className: "tile__slot", text: `${slotLabel(String(u.slot || "").toLowerCase())} · ` }),
    link,
  ]);
  const rank = numOrNull(u.rank);
  const gain = numOrNull(u.gain_pct);
  const detail = h("div", { className: "tile__detail" }, [
    h("span", { className: "tile__rank mono", text: `${rank === null ? "?" : rank}/6 → 6/6` }),
    gain === null
      ? h("span", { className: "tile__muted", text: "no estimate" })
      : h("span", { className: "tile__pct tile__pct--gold mono", text: `+${gain.toFixed(2)}%` }),
  ]);
  return tile("Next crest", [line, detail]);
}

function tileAvgIlvl(character) {
  const { avg, count, total } = computeAvgIlvl(character.gear);
  const body = [h("span", { className: "tile__big mono", text: avg === null ? "?" : String(avg) })];
  if (count < total) {
    body.push(h("span", { className: "tile__muted", text: `based on ${count} of ${total} slots` }));
  }
  return tile("Avg ilvl", body);
}

function tileLastRun(run, character) {
  if (!run) return tile("Last run", [h("span", { className: "tile__muted", text: "Unknown" })]);
  const when = run.finished_at || run.started_at;
  const body = [
    h("span", { className: "tile__big", text: relativeTime(when), attrs: { title: absoluteTime(when) } }),
    h("div", { className: "tile__detail" }, [
      h("span", { className: `pill pill--sm ${run.ok ? "pill--ok" : "pill--fail"}`, text: run.ok ? "OK" : "Failed" }),
      difficultyChecksRow(character ? character.reports : []),
    ]),
  ];
  return tile("Last run", body);
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
    const label = typeof character.skipped === "string" ? `Skipped: ${character.skipped}` : "Skipped";
    els.reportsContainer.appendChild(h("span", { className: "pill pill--muted", text: label }));
  }
  if (Array.isArray(character.warnings) && character.warnings.length > 0) {
    const warnRow = h("div", { className: "warning-row" });
    character.warnings.forEach((w) => warnRow.appendChild(h("span", { className: "pill pill--warn", text: String(w) })));
    els.reportsContainer.appendChild(warnRow);
  }

  if (reports.length === 0) {
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: "No reports for this run." }));
    return;
  }

  const byDiff = new Map(reports.map((r) => [r.difficulty, r]));
  const available = REPORT_DIFFICULTIES.filter((d) => byDiff.has(d));
  if (available.length === 0) {
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: "No reports for this run." }));
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

  const tablist = h("div", { className: "tablist", attrs: { role: "tablist", "aria-label": "Report difficulty" } });
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
}

function reportPanelContent(report, key) {
  const frag = h("div", { className: "report-panel" });

  const headRow = h("div", { className: "report-card__head" });
  const url = isReportUrl(report.report_url);
  headRow.appendChild(linkOrText(url, "Open report ↗", { className: "report-card__link" }));

  let statusPill;
  if (report.error) {
    statusPill = h("span", { className: "pill pill--fail", text: "Error" });
  } else if (report.uploaded_via) {
    statusPill = h("span", {
      className: "pill pill--ok",
      text: "Imported to WoWAudit",
      attrs: { title: `Imported with the ${report.uploaded_via}` },
    });
  } else {
    statusPill = h("span", { className: "pill pill--muted", text: "Not imported" });
  }
  headRow.appendChild(statusPill);
  frag.appendChild(headRow);

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
      text: loc,
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

  const rowsContainer = h("div", { className: "upgrade-rows" });
  frag.appendChild(rowsContainer);

  const toggleWrap = h("div", { className: "bars-toggle" });
  frag.appendChild(toggleWrap);

  const TOP_N = 10;

  function renderRows() {
    clear(rowsContainer);
    clear(toggleWrap);
    const filtered = ui.loc === "All" ? upgrades : upgrades.filter((u) => u.dropLoc === ui.loc);

    if (filtered.length === 0) {
      rowsContainer.appendChild(h("p", { className: "muted-note", text: "No upgrades in this filter." }));
      return;
    }

    const maxPct = filtered.reduce((m, u) => Math.max(m, u.percDiff), 0.0001);
    const shown = ui.expanded ? filtered : filtered.slice(0, TOP_N);
    shown.forEach((u) => rowsContainer.appendChild(upgradeRow(u, maxPct)));

    if (filtered.length > TOP_N) {
      const toggleBtn = h("button", {
        className: "pill pill--action",
        text: ui.expanded ? `Show top ${TOP_N}` : `Show all ${filtered.length}`,
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

  return h("div", { className: "upgrade-row" }, [
    link,
    ilvlPill,
    h("span", { className: "upgrade-row__source", text: sourceLabel(upgrade.dropLoc, upgrade.dropDifficulty) }),
    track,
    h("span", { className: "upgrade-row__pct mono", text: `+${upgrade.percDiff.toFixed(2)}%` }),
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
    const link = linkOrText(url, "Crest report ↗", { className: "report-card__link" });
    if (typeof report.difficulty === "string" && report.difficulty) {
      link.setAttribute("title", `${report.difficulty} crest report`);
    }
    els.crestContainer.appendChild(h("div", { className: "report-card__head" }, [link]));
  }

  const upgrades = character.crest_upgrades;
  if (upgrades === null || upgrades === undefined) {
    els.crestContainer.appendChild(h("p", { className: "muted-note", text: "No crest estimate for this run." }));
    return;
  }
  if (!Array.isArray(upgrades) || upgrades.length === 0) {
    els.crestContainer.appendChild(h("p", { className: "muted-note", text: "Everything is fully upgraded." }));
    return;
  }

  const maxGain = upgrades.reduce((m, u) => {
    const g = numOrNull(u.gain_pct);
    return g !== null && g > m ? g : m;
  }, 0.0001);

  const list = h("div", { className: "crest-compact-list" });
  upgrades.forEach((u) => list.appendChild(crestCompactRow(u, maxGain)));
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
    barRow.appendChild(h("span", { className: "muted-note", text: "No estimate" }));
  } else {
    const pct = Math.max(2, Math.min(100, (gain / maxGain) * 100));
    const track2 = h("div", { className: "bar-track" });
    const fill = h("div", { className: "bar-fill bar-fill--gold" });
    fill.style.width = `${pct}%`;
    track2.appendChild(fill);
    barRow.appendChild(track2);
    barRow.appendChild(h("span", { className: "crest-row__pct mono", text: `+${gain.toFixed(2)}%` }));
  }

  return h("div", { className: "crest-compact-row" }, [link, meta, barRow]);
}

// ---------------------------------------------------------------------
// Gear: WoW-style paper doll.
// ---------------------------------------------------------------------
const PAPERDOLL_LEFT = ["head", "neck", "shoulder", "back", "chest", "shirt", "tabard", "wrist"];
const PAPERDOLL_RIGHT = ["hands", "waist", "legs", "feet", "finger1", "finger2", "trinket1", "trinket2"];
const PAPERDOLL_WEAPONS = ["main_hand", "off_hand"];
const DIMMED_SLOTS = new Set(["shirt", "tabard"]);

function paperdollSlot(slot, bySlot) {
  const g = bySlot.get(slot);
  const dimmed = DIMMED_SLOTS.has(slot);
  const classes = ["pd-slot"];
  if (dimmed) classes.push("pd-slot--dim");

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

  return h("div", { className: classes.join(" ") }, [
    h("span", { className: "pd-slot__label", text: slotLabel(slot) }),
    h("div", { className: "pd-slot__main" }, [link, ilvlPill]),
  ]);
}

function renderPaperdoll(character) {
  clear(els.gearContainer);

  const gear = Array.isArray(character.gear) ? character.gear : [];
  const bySlot = new Map(gear.map((g) => [g.slot, g]));

  const idBlock = h("div", { className: "pd-id" }, [
    h("div", { className: "pd-id__name", text: character.name || "Unknown character" }),
    h("div", { className: "pd-id__spec", text: specLabel(character) }),
  ]);
  const { avg, count, total } = computeAvgIlvl(gear);
  const ilvlLine = h("div", { className: "pd-id__ilvl" }, [
    h("span", { text: "Avg ilvl " }),
    h("b", { className: "mono", text: avg === null ? "?" : String(avg) }),
  ]);
  if (count < total) {
    ilvlLine.appendChild(h("span", { className: "pd-id__ilvl-note", text: ` (${count}/${total} slots)` }));
  }
  idBlock.appendChild(ilvlLine);
  // When the gear source last read the character (Raider.io's crawl time). Older runs lack it.
  const profileUrl = raiderioProfileUrl(character);
  document.getElementById("gearSourceLink").setAttribute("href", profileUrl || "https://raider.io");
  if (typeof character.gear_as_of === "string" && character.gear_as_of) {
    const asOf = h("div", {
      className: "pd-id__asof",
      text: `Raider.io read ${relativeTime(character.gear_as_of)}`,
    });
    asOf.setAttribute("title", absoluteTime(character.gear_as_of));
    idBlock.appendChild(asOf);
  }
  // Raider.io's update button is meant for people; this pipeline never presses it (their API
  // terms forbid automating unpublished endpoints), so offer it as a manual link.
  if (profileUrl) {
    idBlock.appendChild(
      linkOrText(profileUrl, "Update on Raider.io ↗", { className: "pill pill--link pill--sm pd-id__update" })
    );
  }

  const leftCol = h(
    "div",
    { className: "pd-col pd-col--left" },
    PAPERDOLL_LEFT.map((slot) => paperdollSlot(slot, bySlot))
  );
  const rightCol = h(
    "div",
    { className: "pd-col pd-col--right" },
    PAPERDOLL_RIGHT.map((slot) => paperdollSlot(slot, bySlot))
  );
  const weapons = h(
    "div",
    { className: "pd-weapons" },
    PAPERDOLL_WEAPONS.map((slot) => paperdollSlot(slot, bySlot))
  );

  const doll = h("div", { className: "paperdoll" }, [idBlock, leftCol, rightCol, weapons]);
  els.gearContainer.appendChild(doll);
}

// ---------------------------------------------------------------------
// Top-level render: tiles + reports + crests + gear, all built from a full
// run summary and all following the displayed run together.
// ---------------------------------------------------------------------
function renderRunData(fullData) {
  clear(els.reportsContainer);
  clear(els.crestContainer);
  clear(els.gearContainer);
  clear(els.tilesContainer);
  renderMascot(Boolean(fullData.run && fullData.run.ok === true));

  const characters = Array.isArray(fullData.characters) ? fullData.characters : [];
  if (characters.length === 0) {
    els.reportsContainer.appendChild(errorCapsule("This run has no character data."));
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
    els.reportsContainer.appendChild(errorCapsule(`Could not load the latest run: ${err.message}`));
  }
}

async function selectRun(id) {
  const url = runDataUrl(id);
  if (!url) {
    clearAllRunViews();
    els.reportsContainer.appendChild(errorCapsule(`"${id}" is not a valid run id.`));
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
    els.reportsContainer.appendChild(errorCapsule(`Could not load run ${id}: ${err.message}`));
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
// Init.
// ---------------------------------------------------------------------
async function init() {
  collectEls();
  setupWowheadTooltips();
  observeWowheadNames();

  // The <h1> is the single source of truth for the page title; the static
  // <title> in the HTML is only the no-JS fallback.
  const titleH1 = document.getElementById("pageTitle");
  if (titleH1 && titleH1.textContent) document.title = titleH1.textContent;

  let indexData;
  try {
    indexData = await fetchJson("data/index.json");
  } catch (err) {
    showGlobalError(`Could not load the run index: ${err.message}`);
    els.headerStatus.appendChild(h("span", { className: "pill pill--fail", text: "Unavailable" }));
    els.historyContainer.appendChild(h("p", { className: "muted-note", text: "Run history is unavailable." }));
    els.reportsContainer.appendChild(h("p", { className: "muted-note", text: "Reports are unavailable." }));
    return;
  }

  if (!indexData || !Array.isArray(indexData.runs)) {
    showGlobalError("The run index isn't in the expected format.");
    return;
  }

  state.index = indexData;
  renderHeader(indexData);
  renderHistory(indexData);

  window.addEventListener("hashchange", applyHash);
  applyHash();
}

document.addEventListener("DOMContentLoaded", init);
