// WoWAudit wishlist updater -- public run dashboard.
//
// Vanilla JS, no build step. Everything is rendered with
// document.createElement()/textContent -- never innerHTML -- because the
// data this page reads (data/*.json) is produced by an automation pipeline
// that relays error strings from external services (WoWAudit, QE Live).
// Those strings are untrusted and must always end up as literal text, never
// as markup.

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

function text(str) {
  return document.createTextNode(str);
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
  // per "charIdx:difficulty" UI state for the reports view
  reportUi: new Map(),
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
    globalError: document.getElementById("globalError"),
    headerMascot: document.getElementById("headerMascot"),
    viewingBanner: document.getElementById("viewingBanner"),
    reportsContainer: document.getElementById("reportsContainer"),
    crestContainer: document.getElementById("crestContainer"),
    gearContainer: document.getElementById("gearContainer"),
    historyContainer: document.getElementById("historyContainer"),
  };
}

// ---------------------------------------------------------------------
// Header (always reflects the true latest run from index.json).
// ---------------------------------------------------------------------
function renderHeader(indexData) {
  clear(els.headerCapsules);
  clear(els.headerStatus);
  clear(els.headerUpdated);

  const runs = Array.isArray(indexData.runs) ? indexData.runs : [];
  const latest = runs[0];
  if (!latest) {
    els.headerStatus.appendChild(h("span", { className: "pill pill--muted", text: "No runs yet" }));
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
  const updated = h("span", {
    className: "updated",
    text: `updated ${relativeTime(when)}`,
    attrs: { title: absoluteTime(when) },
  });
  els.headerUpdated.appendChild(updated);
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
// Run history (view 4).
// ---------------------------------------------------------------------
function renderHistory(indexData) {
  clear(els.historyContainer);
  const runs = Array.isArray(indexData.runs) ? indexData.runs : [];
  if (runs.length === 0) {
    els.historyContainer.appendChild(h("p", { className: "muted-note", text: "No runs recorded yet." }));
    return;
  }
  runs.forEach((run) => {
    els.historyContainer.appendChild(historyRow(run));
  });
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

  const top = h("div", { className: "history-row__top" }, [
    h("span", {
      className: "history-row__time mono",
      text: relativeTime(run.started_at),
      attrs: { title: absoluteTime(run.started_at) },
    }),
    h("span", { className: "pill pill--muted pill--sm", text: triggerLabel(run.trigger) }),
    h("span", {
      className: `pill pill--sm ${run.ok ? "pill--ok" : "pill--fail"}`,
      text: run.ok ? "OK" : "Failed",
    }),
    run.commit ? h("span", { className: "history-row__commit mono", text: run.commit }) : null,
  ]);
  row.appendChild(top);

  const chips = h("div", { className: "history-row__chips" });
  const chars = Array.isArray(run.characters) ? run.characters : [];
  chars.forEach((c) => {
    if (chars.length > 1) {
      chips.appendChild(h("span", { className: "chip chip--name", text: c.name || "?" }));
    }
    (c.reports || []).forEach((r) => {
      chips.appendChild(reportChip(r));
    });
  });
  row.appendChild(chips);

  const ghUrl = isGithubUrl(run.url);
  const footLink = linkOrText(ghUrl, "GitHub run ↗", { className: "history-row__gh" });
  footLink.addEventListener("click", (e) => e.stopPropagation());
  const foot = h("div", { className: "history-row__foot" }, [footLink]);
  row.appendChild(foot);

  return row;
}

function reportChip(report) {
  const url = isReportUrl(report.report_url);
  const chip = linkOrText(url, report.difficulty || "Report", { className: "chip chip--report" });
  if (url) chip.addEventListener("click", (e) => e.stopPropagation());
  if (report.error) chip.classList.add("chip--error");
  else if (report.uploaded_via) chip.classList.add("chip--imported");
  return chip;
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
  els.viewingBanner.appendChild(
    h("span", { text: "Viewing run " }, [])
  );
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
// Reports (view 2) + Gear (view 3), built from a full run summary.
// ---------------------------------------------------------------------
function renderRunData(fullData) {
  clear(els.reportsContainer);
  clear(els.crestContainer);
  clear(els.gearContainer);
  renderMascot(Boolean(fullData.run && fullData.run.ok === true));

  const characters = Array.isArray(fullData.characters) ? fullData.characters : [];
  if (characters.length === 0) {
    els.reportsContainer.appendChild(errorCapsule("This run has no character data."));
    return;
  }

  const showCharHeading = characters.length > 1;

  characters.forEach((character, idx) => {
    if (showCharHeading) {
      els.reportsContainer.appendChild(
        h("h3", { className: "char-heading", text: character.name || `Character ${idx + 1}` })
      );
      els.crestContainer.appendChild(
        h("h3", { className: "char-heading", text: character.name || `Character ${idx + 1}` })
      );
      els.gearContainer.appendChild(
        h("h3", { className: "char-heading", text: character.name || `Character ${idx + 1}` })
      );
    }

    if (character.error) {
      els.reportsContainer.appendChild(errorCapsule(character.error));
    }
    if (character.skipped) {
      const label =
        typeof character.skipped === "string" ? `Skipped: ${character.skipped}` : "Skipped";
      els.reportsContainer.appendChild(h("span", { className: "pill pill--muted", text: label }));
    }
    if (Array.isArray(character.warnings) && character.warnings.length > 0) {
      const warnRow = h("div", { className: "warning-row" });
      character.warnings.forEach((w) => {
        warnRow.appendChild(h("span", { className: "pill pill--warn", text: String(w) }));
      });
      els.reportsContainer.appendChild(warnRow);
    }

    const reports = Array.isArray(character.reports) ? character.reports : [];
    if (reports.length === 0) {
      els.reportsContainer.appendChild(
        h("p", { className: "muted-note", text: "No reports for this character in this run." })
      );
    }
    reports.forEach((report) => {
      const key = `${idx}:${report.difficulty}`;
      els.reportsContainer.appendChild(renderReportCard(report, key));
    });

    els.crestContainer.appendChild(renderCrestPanel(character));
    els.gearContainer.appendChild(renderGearGrid(character));
  });

  refreshWowheadLinks();
}

// ---------------------------------------------------------------------
// Crest planner (view: "Where to spend crests"), built from a full run
// summary's crest_report/crest_upgrades. Both are optional and independent:
// crest_report is {difficulty, report_id, report_url} | null,
// crest_upgrades is a pre-sorted (desc, nulls last) array | null.
// ---------------------------------------------------------------------
function numOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function renderCrestPanel(character) {
  const wrap = h("section", { className: "rcard-wrap" }, [
    h("span", { className: "rcard__cap", text: character.name || "Crests" }),
  ]);
  const inner = h("div", { className: "rcard" }, [h("div", { className: "rcard__in" })]);
  const body = inner.firstChild;
  wrap.appendChild(inner);

  const report = character.crest_report;
  if (report && typeof report === "object") {
    const url = isReportUrl(report.report_url);
    const link = linkOrText(url, "Crest report ↗", { className: "report-card__link" });
    if (typeof report.difficulty === "string" && report.difficulty) {
      link.setAttribute("title", `${report.difficulty} crest report`);
    }
    body.appendChild(h("div", { className: "report-card__head" }, [link]));
  }

  const upgrades = character.crest_upgrades;
  if (upgrades === null || upgrades === undefined) {
    body.appendChild(h("p", { className: "muted-note", text: "No crest estimate for this run." }));
    return wrap;
  }
  if (!Array.isArray(upgrades) || upgrades.length === 0) {
    body.appendChild(h("p", { className: "muted-note", text: "Everything is fully upgraded." }));
    return wrap;
  }

  const maxGain = upgrades.reduce((m, u) => {
    const g = numOrNull(u.gain_pct);
    return g !== null && g > m ? g : m;
  }, 0.0001);

  const rows = h("div", { className: "crest-rows" });
  upgrades.forEach((u) => rows.appendChild(crestRow(u, maxGain)));
  body.appendChild(rows);

  return wrap;
}

function crestRow(u, maxGain) {
  const level = numOrNull(u.level);
  const maxLevel = numOrNull(u.max_level);
  const rank = numOrNull(u.rank);
  const itemIdNum = Number(u.item_id);

  const url = wowheadItemUrl(u.item_id, null, u.level);
  const label =
    typeof u.name === "string" && u.name
      ? u.name
      : Number.isInteger(itemIdNum)
        ? `Item ${itemIdNum}`
        : "Unknown item";
  const link = linkOrText(url, label, { className: "crest-row__item" });

  const meta = h("div", { className: "crest-row__meta" }, [
    link,
    h("span", { className: "crest-row__slot", text: slotLabel(String(u.slot || "").toLowerCase()) }),
  ]);

  const track = typeof u.track === "string" && u.track ? u.track : "?";
  const trackEl = h("span", {
    className: "crest-row__track",
    text: `${track} ${rank === null ? "?" : rank}/6 → 6/6`,
  });

  const levelsEl = h("span", {
    className: "crest-row__levels mono",
    text: `${level === null ? "?" : level} → ${maxLevel === null ? "?" : maxLevel}`,
  });

  const gain = numOrNull(u.gain_pct);
  const kids = [meta, trackEl, levelsEl];
  if (gain === null) {
    kids.push(h("span", { className: "crest-row__no-estimate muted-note", text: "No estimate" }));
  } else {
    const pct = Math.max(2, Math.min(100, (gain / maxGain) * 100));
    const track2 = h("div", { className: "bar-track" });
    const fill = h("div", { className: "bar-fill bar-fill--gold" });
    fill.style.width = `${pct}%`;
    track2.appendChild(fill);
    kids.push(track2);
    kids.push(h("span", { className: "crest-row__pct mono", text: `+${gain.toFixed(2)}%` }));
  }

  return h("div", { className: "crest-row" }, kids);
}

function renderReportCard(report, key) {
  const wrap = h("section", { className: "rcard-wrap" }, [
    h("span", { className: "rcard__cap", text: report.difficulty || "Report" }),
  ]);
  const inner = h("div", { className: "rcard" }, [h("div", { className: "rcard__in" })]);
  const body = inner.firstChild;
  wrap.appendChild(inner);

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
      attrs: { title: `Imported with the ${report.uploaded_via}` }, // "API key" or "login session"
    });
  } else {
    statusPill = h("span", { className: "pill pill--muted", text: "Not imported" });
  }
  headRow.appendChild(statusPill);
  body.appendChild(headRow);

  if (report.error) {
    body.appendChild(h("p", { className: "report-card__error", text: String(report.error) }));
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
      renderBars();
    });
    if (loc === ui.loc) btn.classList.add("is-active");
    filterButtons.set(loc, btn);
    filterRow.appendChild(btn);
  });
  body.appendChild(filterRow);

  const barsContainer = h("div", { className: "bars" });
  body.appendChild(barsContainer);

  const toggleWrap = h("div", { className: "bars-toggle" });
  body.appendChild(toggleWrap);

  function renderBars() {
    clear(barsContainer);
    clear(toggleWrap);
    const filtered =
      ui.loc === "All" ? upgrades : upgrades.filter((u) => u.dropLoc === ui.loc);

    if (filtered.length === 0) {
      barsContainer.appendChild(h("p", { className: "muted-note", text: "No upgrades in this filter." }));
      return;
    }

    const maxPct = filtered.reduce((m, u) => Math.max(m, u.percDiff), 0.0001);
    const shown = ui.expanded ? filtered : filtered.slice(0, 15);
    shown.forEach((u) => barsContainer.appendChild(upgradeBar(u, maxPct)));

    if (filtered.length > 15) {
      const toggleBtn = h("button", {
        className: "pill pill--action",
        text: ui.expanded ? "Show top 15" : `Show all ${filtered.length}`,
        attrs: { type: "button" },
      });
      toggleBtn.addEventListener("click", () => {
        ui.expanded = !ui.expanded;
        renderBars();
      });
      toggleWrap.appendChild(toggleBtn);
    }
  }

  renderBars();
  return wrap;
}

function upgradeBar(upgrade, maxPct) {
  const url = wowheadItemUrl(upgrade.item, null, upgrade.level);
  const link = linkOrText(url, `Item ${upgrade.item}`, { className: "upgrade-bar__item" });

  const pct = Math.max(2, Math.min(100, (upgrade.percDiff / maxPct) * 100));
  const track = h("div", { className: "bar-track" });
  const fill = h("div", { className: "bar-fill" });
  fill.style.width = `${pct}%`;
  track.appendChild(fill);

  return h("div", { className: "upgrade-bar" }, [
    h("div", { className: "upgrade-bar__meta" }, [
      link,
      h("span", { className: "upgrade-bar__source", text: sourceLabel(upgrade.dropLoc, upgrade.dropDifficulty) }),
    ]),
    track,
    h("span", { className: "upgrade-bar__pct mono", text: `+${upgrade.percDiff.toFixed(2)}%` }),
  ]);
}

function renderGearGrid(character) {
  const wrap = h("section", { className: "rcard-wrap" }, [
    h("span", { className: "rcard__cap", text: character.name || "Gear" }),
  ]);
  const inner = h("div", { className: "rcard" }, [h("div", { className: "rcard__in" })]);
  const body = inner.firstChild;
  wrap.appendChild(inner);

  const gear = Array.isArray(character.gear) ? character.gear : [];
  if (gear.length === 0) {
    body.appendChild(h("p", { className: "muted-note", text: "No gear recorded for this run." }));
    return wrap;
  }

  const grid = h("div", { className: "gear-grid" });
  gear.forEach((g) => {
    const url = wowheadItemUrl(g.item_id, g.bonus_ids, g.ilvl);
    const link = linkOrText(url, g.name || `Item ${g.item_id}`, { className: "gear-slot__item" });
    const slot = h("div", { className: "gear-slot" }, [
      h("span", { className: "gear-slot__label", text: slotLabel(g.slot) }),
      link,
      h("span", { className: "gear-slot__ilvl mono", text: Number.isFinite(g.ilvl) ? String(g.ilvl) : "" }),
    ]);
    grid.appendChild(slot);
  });
  body.appendChild(grid);
  return wrap;
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
    clear(els.reportsContainer);
    clear(els.crestContainer);
    clear(els.gearContainer);
    renderMascot(false);
    els.reportsContainer.appendChild(errorCapsule(`Could not load the latest run: ${err.message}`));
  }
}

async function selectRun(id) {
  const url = runDataUrl(id);
  if (!url) {
    clear(els.reportsContainer);
    clear(els.crestContainer);
    clear(els.gearContainer);
    renderMascot(false);
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
    clear(els.reportsContainer);
    clear(els.crestContainer);
    clear(els.gearContainer);
    renderMascot(false);
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
