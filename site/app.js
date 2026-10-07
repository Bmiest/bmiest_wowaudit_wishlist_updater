// Gear upgrades: the public run dashboard, design language v2 ("raid-night plan").
//
// What matters this week comes first: the next raid night and what each of its bosses can drop
// for you (boss tiles in kill order, the best upgrade framed in gold), then the week's best M+
// dungeons, where a bonus roll is worth the most and where to spend crests. The run status, the
// changes since the previous run and the run history sit in the right rail; the full report (filters, sortable table) and the gear are
// one fold away.
//
// Vanilla JS, no build step. Every node is built with createElement/textContent, never
// innerHTML, because data/*.json relays strings from external services (QE, Raider.io, error
// messages). Those strings always end up as literal text. Nothing from the data reaches an
// href or src unless it passes one of the validators below.

// ---------------------------------------------------------------------------------------------
// DOM helpers: the only way nodes get built on this page.
// ---------------------------------------------------------------------------------------------
function h(tag, opts, kids) {
  const node = document.createElement(tag);
  opts = opts || {};
  if (opts.className) node.className = opts.className;
  if (typeof opts.text === "string") node.textContent = opts.text;
  if (opts.attrs) {
    for (const [k, v] of Object.entries(opts.attrs)) {
      if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v === true ? "" : v);
    }
  }
  if (opts.on) for (const [ev, fn] of Object.entries(opts.on)) node.addEventListener(ev, fn);
  if (opts.vars) for (const [k, v] of Object.entries(opts.vars)) node.style.setProperty(k, v);
  (kids || []).forEach((kid) => {
    if (kid === null || kid === undefined || kid === false) return;
    node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  });
  return node;
}
function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

// Drawn icons, one stroke family (2px, round caps). Path data are constants, never data.
const ICONS = {
  check: { vb: "0 0 12 12", d: "M2 6.5 5 9.5 10.5 3", stroke: true },
  ext: { vb: "0 0 12 12", d: "M4.5 2.5h5v5M9.5 2.5 3 9", stroke: true },
  up: { vb: "0 0 12 12", d: "M6 10V2.5M2.8 5.5 6 2.3l3.2 3.2", stroke: true },
  warn: { vb: "0 0 16 16", d: "M8 1.8 15 14H1ZM8 6.2v3.6M8 11.6v.4", stroke: true },
  x: { vb: "0 0 12 12", d: "M3 3l6 6M9 3 3 9", stroke: true },
  plus: { vb: "0 0 12 12", d: "M6 2.5v7M2.5 6h7", stroke: true },
  minus: { vb: "0 0 12 12", d: "M2.5 6h7", stroke: true },
  mark: { vb: "0 0 18 18", d: "M4.2 4.2a6.8 6.8 0 0 0 0 9.6M13.8 4.2a6.8 6.8 0 0 1 0 9.6", stroke: true, dot: true },
  sort: { vb: "0 0 12 12", d: "M3.5 4.5 6 2l2.5 2.5M3.5 7.5 6 10l2.5-2.5", stroke: true },
};
function icon(name, cls) {
  const def = ICONS[name];
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", def.vb);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", `ico ico--${name}${cls ? " " + cls : ""}`);
  if (def.dot) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", "9");
    c.setAttribute("cy", "9");
    c.setAttribute("r", "3");
    c.setAttribute("fill", "currentColor");
    svg.appendChild(c);
  }
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", def.d);
  if (def.stroke) {
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", "currentColor");
    p.setAttribute("stroke-width", name === "mark" ? "1.8" : "2");
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("stroke-linejoin", "round");
  } else {
    p.setAttribute("fill", "currentColor");
  }
  svg.appendChild(p);
  return svg;
}

// ---------------------------------------------------------------------------------------------
// Security-critical validation. Every URL or image path built from data goes through here.
// ---------------------------------------------------------------------------------------------
function safePrefixedUrl(value, prefix) {
  return typeof value === "string" && value.startsWith(prefix) ? value : null;
}
function isReportUrl(url) {
  return safePrefixedUrl(url, "https://questionablyepic.com/");
}
function isGithubUrl(url) {
  return safePrefixedUrl(url, "https://github.com/");
}
function raiderioProfileUrl(character) {
  if (!character) return null;
  const region = String(character.region || "").toLowerCase();
  const realm = String(character.realm || "").toLowerCase();
  const name = String(character.name || "");
  if (!/^(us|eu|kr|tw|cn)$/.test(region) || !/^[a-z0-9-]+$/.test(realm)) return null;
  if (!/^\p{L}{2,12}$/u.test(name)) return null;
  return `https://raider.io/characters/${region}/${realm}/${encodeURIComponent(name)}`;
}
function wowheadItemUrl(itemId, bonusIds, ilvl) {
  const id = Number(itemId);
  if (!Number.isInteger(id) || id <= 0) return null;
  let url = `https://www.wowhead.com/item=${id}`;
  const params = [];
  if (Array.isArray(bonusIds) && bonusIds.length > 0) {
    const nums = bonusIds.map(Number);
    if (nums.every((n) => Number.isInteger(n) && n >= 0)) params.push(`bonus=${nums.join(":")}`);
  }
  const lvl = Number(ilvl);
  if (Number.isInteger(lvl) && lvl > 0) params.push(`ilvl=${lvl}`);
  if (params.length) url += `?${params.join("&")}`;
  return url;
}
// Item icons: a validated icon name onto a fixed CDN path, never taken as a URL.
function wowIconUrl(name) {
  return typeof name === "string" && /^[a-z0-9_-]{1,80}$/.test(name)
    ? `https://wow.zamimg.com/images/wow/icons/medium/${name}.jpg`
    : null;
}
// Boss heads: self-hosted, by an integer display id from bossart.js.
function bossHeadUrl(displayId) {
  return Number.isInteger(displayId) && displayId > 0 ? `img/boss/head-${displayId}.webp` : null;
}
const RUN_ID_RE = /^[A-Za-z0-9_-]+$/;
function runDataUrl(id) {
  return typeof id === "string" && RUN_ID_RE.test(id) ? `data/runs/${id}.json` : null;
}
function linkOrText(url, label, opts) {
  opts = opts || {};
  if (url) {
    return h("a", {
      className: opts.className,
      text: label,
      attrs: { href: url, target: "_blank", rel: "noopener noreferrer", title: opts.title, ...(opts.attrs || {}) },
    }, opts.kids);
  }
  return h("span", { className: opts.className, text: label, attrs: { title: opts.title } }, opts.kids);
}
/** A link with a drawn external-link mark after the label. */
function extLink(url, label, className) {
  if (!url) return h("span", { className, text: label });
  return h("a", { className: `ext ${className || ""}`, attrs: { href: url, target: "_blank", rel: "noopener noreferrer" } }, [
    h("span", { text: label }),
    icon("ext"),
  ]);
}

// ---------------------------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------------------------
function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}
function parseDate(iso) {
  const d = new Date(iso);
  return iso && !Number.isNaN(d.getTime()) ? d : null;
}
const DAY_MS = 86400000;
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
  return d ? d.toLocaleString(locale(), { dateStyle: "full", timeStyle: "medium" }) : String(iso || "");
}
function shortDate(iso) {
  const d = parseDate(iso);
  return d
    ? d.toLocaleString(locale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Brussels" })
    : "?";
}
const TRIGGERS = new Set(["schedule", "workflow_dispatch", "local"]);
function triggerLabel(tr) {
  return TRIGGERS.has(tr) ? t(`trigger_${tr}`) : tr ? String(tr) : t("unknownTrigger");
}
const SLOTS = new Set(["head", "neck", "shoulder", "back", "chest", "shirt", "tabard", "wrist", "hands", "waist",
  "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand"]);
function slotLabel(slot) {
  return SLOTS.has(slot) ? t(`slot_${slot}`) : capitalize(String(slot || "").replace(/_/g, " "));
}
// QE's slot names on the upgrade rows, shown in the page language.
const QE_SLOT_KEYS = { Finger: "qeslot_Finger", Trinket: "qeslot_Trinket", "1H Weapon": "qeslot_1H", "2H Weapon": "qeslot_2H",
  WeaponMainHand: "qeslot_1H", Offhand: "slot_off_hand", Shield: "qeslot_Shield" };
function qeSlotLabel(slot) {
  if (typeof slot !== "string" || !slot) return "?";
  if (Object.hasOwn(QE_SLOT_KEYS, slot)) return t(QE_SLOT_KEYS[slot]);
  const lower = slot.toLowerCase();
  return SLOTS.has(lower) ? slotLabel(lower) : slot;
}
const DUNGEON_KEY_LABELS = ["M0", "+2/3", "+4", "+5", "+6", "+7", "+8/9", "+10"];
// Game terms (Raid, Dungeon, difficulties) stay English in both languages.
function whereLabel(u) {
  if (u.dropLoc === "Raid") return u.dropDifficulty === 3 ? "Raid · Mythic" : u.dropDifficulty === 2 ? "Raid · Heroic" : "Raid";
  if (u.dropLoc === "Dungeon") {
    const i = Number(u.dropDifficulty);
    return Number.isInteger(i) && i >= 0 && i < DUNGEON_KEY_LABELS.length ? `Dungeon · ${DUNGEON_KEY_LABELS[i]}` : "Dungeon";
  }
  return u.dropLoc ? String(u.dropLoc) : t("unknownSource");
}
function dropSourceName(u) {
  return typeof u.dropSource === "string" && u.dropSource ? u.dropSource : null;
}
function numOrNull(v) {
  const n = Number(v);
  return v !== null && v !== undefined && v !== "" && Number.isFinite(n) ? n : null;
}
const DROP_LOC_FILTERS = ["All", "Raid", "Dungeon", "Delves", "Crafted"];
const REPORT_DIFFICULTIES = ["Heroic", "Mythic"];

// ---------------------------------------------------------------------------------------------
// Computation
// ---------------------------------------------------------------------------------------------
/** One row per item: its best result (the max-upgrade row wins), upgrades only, best first. */
function computeUpgrades(results) {
  if (!Array.isArray(results)) return [];
  const byItem = new Map();
  for (const r of results) {
    if (!r || typeof r.percDiff !== "number" || !(r.percDiff > 0)) continue;
    const existing = byItem.get(r.item);
    if (!existing) {
      byItem.set(r.item, r);
      continue;
    }
    if (existing.dropType === "max") continue;
    if (r.dropType === "max" || r.percDiff > existing.percDiff) byItem.set(r.item, r);
  }
  return Array.from(byItem.values()).sort((a, b) => b.percDiff - a.percDiff);
}
const PAIRED_SLOTS = new Set(["Finger", "Trinket"]);
const TWO_HAND_SLOTS = new Set(["2H Weapon"]);
const ONE_HAND_SLOTS = new Set(["1H Weapon", "WeaponMainHand"]);
const OFF_HAND_SLOTS = new Set(["Offhand", "Shield"]);
/** The biggest upgrade in every slot added up (two rings/trinkets; 2H vs 1H + off-hand). */
function computePowerToGain(upgrades) {
  const bySlot = new Map();
  const w = { two: [], one: [], off: [] };
  for (const u of upgrades) {
    if (typeof u.slot !== "string" || !u.slot) continue;
    if (TWO_HAND_SLOTS.has(u.slot)) w.two.push(u.percDiff);
    else if (ONE_HAND_SLOTS.has(u.slot)) w.one.push(u.percDiff);
    else if (OFF_HAND_SLOTS.has(u.slot)) w.off.push(u.percDiff);
    else {
      if (!bySlot.has(u.slot)) bySlot.set(u.slot, []);
      bySlot.get(u.slot).push(u.percDiff);
    }
  }
  const picked = [];
  for (const [slot, gains] of bySlot) picked.push(...gains.slice(0, PAIRED_SLOTS.has(slot) ? 2 : 1));
  const sum = (g) => g.reduce((a, b) => a + b, 0);
  const two = w.two.slice(0, 1);
  const split = [...w.one.slice(0, 1), ...w.off.slice(0, 1)];
  picked.push(...(sum(two) >= sum(split) ? two : split));
  return picked.length ? { pct: sum(picked), items: picked.length } : null;
}
/**
 * What a bonus roll is worth at each boss and dungeon, from QE's "bonus" rows (the item at the
 * level a bonus roll gives, at max upgrade). A roll gives one random item of the loot pool, so
 * like QE's own "Bonus roll chance": chance = share of the pool that is an upgrade, avg = mean
 * gain per roll with the misses counted as 0. An item shared by two bosses ("A / B") is in both
 * pools. Best average first, then chance. `items` is the whole pool, biggest gain first.
 */
function computeBonusRolls(results) {
  if (!Array.isArray(results)) return [];
  const pools = new Map();
  for (const r of results) {
    if (!r || r.dropType !== "bonus" || typeof r.percDiff !== "number" || !Number.isFinite(r.percDiff)) continue;
    const src = dropSourceName(r);
    if (!src || (r.dropLoc !== "Raid" && r.dropLoc !== "Dungeon")) continue;
    for (const name of src.split(" / ").map((s) => s.trim()).filter(Boolean)) {
      const key = `${r.dropLoc}:${name}`;
      if (!pools.has(key)) pools.set(key, { name, dropLoc: r.dropLoc, items: new Map() });
      const items = pools.get(key).items;
      const prev = items.get(r.item);
      if (!prev || r.percDiff > prev.percDiff) items.set(r.item, r);
    }
  }
  return [...pools.values()].map(({ name, dropLoc, items }) => {
    const rows = [...items.values()];
    const best = rows.reduce((a, b) => (b.percDiff > a.percDiff ? b : a));
    return {
      name, dropLoc,
      pool: rows.length,
      upgrades: rows.filter((r) => r.percDiff > 0).length,
      avg: rows.reduce((s, r) => s + Math.max(0, r.percDiff), 0) / rows.length,
      level: Math.max(...rows.map((r) => numOrNull(r.level) || 0)) || null,
      best: best.percDiff > 0 ? best : null,
      items: rows.sort((a, b) => b.percDiff - a.percDiff),
    };
  }).sort((a, b) => b.avg - a.avg || b.upgrades / b.pool - a.upgrades / a.pool);
}
const ILVL_SLOTS = ["head", "neck", "shoulder", "back", "chest", "wrist", "hands", "waist",
  "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand"];
function computeAvgIlvl(gear) {
  const by = new Map((Array.isArray(gear) ? gear : []).map((g) => [g.slot, g]));
  const vals = ILVL_SLOTS.map((s) => (by.get(s) ? numOrNull(by.get(s).ilvl) : null)).filter((v) => v !== null);
  return { avg: vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null, count: vals.length, total: ILVL_SLOTS.length };
}
function usefulCrestUpgrades(list) {
  return list.filter((u) => {
    const g = numOrNull(u.gain_pct);
    return g === null || g > 0;
  });
}
/** Consecutive runs with the same results digest (and the same ok) fold into one group. */
function groupRuns(runs) {
  const groups = [];
  for (const run of runs) {
    const last = groups[groups.length - 1];
    const head = last && last[0];
    if (head && typeof run.digest === "string" && run.digest === head.digest && Boolean(run.ok) === Boolean(head.ok)) last.push(run);
    else groups.push([run]);
  }
  return groups;
}
const QE_SLOT_TO_GEAR = {
  Head: ["head"], Neck: ["neck"], Shoulder: ["shoulder"], Back: ["back"], Chest: ["chest"], Wrist: ["wrist"],
  Hands: ["hands"], Waist: ["waist"], Legs: ["legs"], Feet: ["feet"], Finger: ["finger1", "finger2"],
  Trinket: ["trinket1", "trinket2"], "2H Weapon": ["main_hand"], "1H Weapon": ["main_hand"],
  WeaponMainHand: ["main_hand"], Offhand: ["off_hand"], Shield: ["off_hand"],
};
function bestUpgradeBySlot(character, diff) {
  const gearBySlot = new Map((character.gear || []).map((g) => [g.slot, g]));
  const report = (character.reports || []).find((r) => r.difficulty === diff && !r.error);
  const by = new Map();
  if (!report) return by;
  for (const u of computeUpgrades(report.results)) {
    const targets = Object.hasOwn(QE_SLOT_TO_GEAR, u.slot) ? QE_SLOT_TO_GEAR[u.slot] : [];
    const wearing = (s) => gearBySlot.get(s)?.item_id === u.item;
    const ordered = [...targets.filter(wearing), ...targets.filter((s) => !wearing(s))];
    const free = ordered.find((s) => !by.has(s));
    if (free) by.set(free, u);
  }
  return by;
}

// ---------------------------------------------------------------------------------------------
// Raid nights (summary.raid_night, from wishlist.toml [raid_night]): days, "HH:MM" start/end,
// an IANA time zone. The next one is computed in that zone, whatever the viewer's zone is.
// ---------------------------------------------------------------------------------------------
const WEEKDAY_INDEX = { sunday: 0, monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6 };
const HHMM_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;
function parseRaidNight(cfg) {
  if (!cfg || typeof cfg !== "object" || !Array.isArray(cfg.days)) return null;
  const days = cfg.days.map((d) => WEEKDAY_INDEX[String(d).toLowerCase()]).filter((d) => d !== undefined);
  const s = HHMM_RE.exec(String(cfg.start || ""));
  const e = HHMM_RE.exec(String(cfg.end || ""));
  const tz = typeof cfg.timezone === "string" ? cfg.timezone : "";
  if (!days.length || !s || !e || !tz) return null;
  try {
    new Intl.DateTimeFormat("en-GB", { timeZone: tz });
  } catch (err) {
    return null;
  }
  return { days: new Set(days), start: [Number(s[1]), Number(s[2])], end: [Number(e[1]), Number(e[2])], tz };
}
function tzParts(date, tz) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  const o = {};
  parts.forEach((p) => {
    if (p.type !== "literal") o[p.type] = Number(p.value);
  });
  return o;
}
/** The UTC instant of a wall-clock time in `tz` (two passes, so DST changes land right). */
function zonedToUtc(y, m, d, hh, mm, tz) {
  const want = Date.UTC(y, m - 1, d, hh, mm);
  let guess = want;
  for (let i = 0; i < 2; i++) {
    const p = tzParts(new Date(guess), tz);
    const shown = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
    guess += want - shown;
  }
  return new Date(guess);
}
/** {start, end, live, dayOffset} of the raid night that's on now or comes next, or null. */
function nextRaidNight(cfg, now) {
  if (!cfg) return null;
  const p = tzParts(now, cfg.tz);
  for (let i = -1; i < 8; i++) {
    const day = new Date(Date.UTC(p.year, p.month - 1, p.day + i));
    if (!cfg.days.has(day.getUTCDay())) continue;
    const [y, m, d] = [day.getUTCFullYear(), day.getUTCMonth() + 1, day.getUTCDate()];
    const start = zonedToUtc(y, m, d, cfg.start[0], cfg.start[1], cfg.tz);
    let end = zonedToUtc(y, m, d, cfg.end[0], cfg.end[1], cfg.tz);
    if (end <= start) end = new Date(end.getTime() + DAY_MS); // runs past midnight
    if (now < end) return { start, end, live: now >= start, dayOffset: i };
  }
  return null;
}
function untilText(ms) {
  const min = Math.max(0, Math.ceil(ms / 60000));
  const d = Math.floor(min / 1440);
  const hh = Math.floor((min % 1440) / 60);
  const mm = min % 60;
  const hu = t("hourUnit");
  if (d > 0) return `${d} d ${hh} ${hu}`;
  return hh > 0 ? `${hh} ${hu} ${String(mm).padStart(2, "0")} min` : `${mm} min`;
}

// ---------------------------------------------------------------------------------------------
// Bosses. summary.raids lists each raid with its bosses in kill order (QE's names and encounter
// ids); bossart.js adds the full name and the head. An upgrade's dropSource is the QE name of
// its boss ("Boss A / Boss B" when it drops from several).
// ---------------------------------------------------------------------------------------------
function cleanRaids(raw) {
  if (!Array.isArray(raw)) return [];
  const art = (typeof window !== "undefined" && window.BossArt) || {};
  return raw
    .filter((r) => r && typeof r.name === "string" && Array.isArray(r.bosses))
    .map((r) => ({
      id: r.id,
      name: r.name,
      bosses: r.bosses
        .filter((b) => b && typeof b.name === "string" && b.name)
        .map((b) => {
          const extra = Number.isInteger(b.id) && Object.hasOwn(art, b.id) ? art[b.id] : null;
          return {
            id: b.id,
            qeName: b.name,
            name: extra && typeof extra.name === "string" ? extra.name : b.name,
            head: extra ? extra.head : null,
          };
        }),
    }))
    .filter((r) => r.bosses.length);
}
function normBoss(s) {
  return String(s || "").toLowerCase().replace(/^the\s+/, "").trim();
}
/** The bosses (from `raids`) a dropSource names, matched on QE's or the full name. */
function bossesFor(dropSource, raids) {
  if (!dropSource) return [];
  const wanted = dropSource.split(" / ").map(normBoss).filter(Boolean);
  const hits = [];
  for (const raid of raids) {
    for (const boss of raid.bosses) {
      if (wanted.includes(normBoss(boss.qeName)) || wanted.includes(normBoss(boss.name))) hits.push(boss);
    }
  }
  return hits;
}
/**
 * The raid-night plan: each raid with each boss in kill order and its upgrades (best first),
 * plus "other" for raid upgrades no boss claims (old data, a name QE changed).
 */
function planRaids(upgrades, raids) {
  const raidUps = upgrades.filter((u) => u.dropLoc === "Raid");
  const claimed = new Set();
  const plan = raids.map((raid) => ({
    raid,
    bosses: raid.bosses.map((boss) => {
      const items = raidUps.filter((u) => bossesFor(dropSourceName(u), [raid]).includes(boss));
      items.forEach((u) => claimed.add(u));
      return { boss, items };
    }),
  }));
  const other = new Map();
  raidUps.filter((u) => !claimed.has(u)).forEach((u) => {
    const name = dropSourceName(u) || t("unknownSource");
    if (!other.has(name)) other.set(name, []);
    other.get(name).push(u);
  });
  return {
    plan,
    other: [...other.entries()].map(([name, items]) => ({ boss: { id: null, qeName: name, name, head: null }, items })),
  };
}
function bossHead(boss, cls) {
  const src = boss ? bossHeadUrl(boss.head) : null;
  const initial = String((boss && boss.name) || "?").replace(/^the\s+/i, "").trim()[0] || "?";
  return h("span", { className: `boss-thumb ${cls || ""}`, attrs: { "aria-hidden": "true" } },
    [src ? h("img", { attrs: { src, alt: "", width: "52", height: "52", loading: "lazy" } }) : h("span", { className: "boss-thumb__mono", text: initial })]);
}
/** A source tile for a table row: the boss head for a raid boss, else a mono tile. */
function sourceTile(u, raids, cls) {
  const name = dropSourceName(u);
  if (u.dropLoc === "Raid" && name) {
    const [boss] = bossesFor(name, raids);
    if (boss) return bossHead(boss, cls);
  }
  let mono = "?";
  if (u.dropLoc === "Dungeon" && name) mono = name.replace(/^the\s+/i, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  else if (u.dropLoc === "Delves") mono = "D";
  else if (u.dropLoc === "Crafted") mono = "C";
  return h("span", { className: `boss-thumb boss-thumb--src ${cls || ""}`, attrs: { "aria-hidden": "true" } }, [h("span", { className: "boss-thumb__mono", text: mono })]);
}
function sourceName(u, raids) {
  const n = dropSourceName(u);
  if (n) {
    const hits = u.dropLoc === "Raid" ? bossesFor(n, raids) : [];
    return hits.length ? hits.map((b) => b.name).join(" / ") : n;
  }
  return u.dropLoc === "Crafted" || u.dropLoc === "Delves" ? u.dropLoc : t("unknownSource");
}

// ---------------------------------------------------------------------------------------------
// Item names and icons. Runs since summary v2 carry them (QE's item database); for older runs
// a name seen in any loaded run is reused, then Wowhead's tooltip script fills in the rest
// (renameLinks per link, only where the name is missing).
// ---------------------------------------------------------------------------------------------
const itemMeta = new Map(); // item id -> {name, icon}
function learnItems(data) {
  if (!data || !Array.isArray(data.characters)) return;
  const note = (id, name, ico) => {
    const key = Number(id);
    if (!Number.isInteger(key)) return;
    const cur = itemMeta.get(key) || {};
    itemMeta.set(key, {
      name: cur.name || (typeof name === "string" && name ? name : null),
      icon: cur.icon || (wowIconUrl(ico) ? ico : null),
    });
  };
  data.characters.forEach((c) => {
    (Array.isArray(c.gear) ? c.gear : []).forEach((g) => note(g.item_id, g.name, g.icon));
    (Array.isArray(c.crest_upgrades) ? c.crest_upgrades : []).forEach((u) => note(u.item_id, u.name, u.icon));
    (Array.isArray(c.reports) ? c.reports : []).forEach((r) =>
      (Array.isArray(r.results) ? r.results : []).forEach((x) => note(x.item, x.name, x.icon)));
  });
}
const wowheadNames = new Map(); // names Wowhead filled in, so a re-render doesn't flash "Item 123"
function itemName(id, provided) {
  if (typeof provided === "string" && provided) return provided;
  const key = Number(id);
  const meta = itemMeta.get(key);
  if (meta && meta.name) return meta.name;
  if (wowheadNames.has(key)) return wowheadNames.get(key);
  return Number.isInteger(key) ? `Item ${key}` : t("unknownItem");
}
function itemIcon(id, provided, cls) {
  const meta = itemMeta.get(Number(id));
  const src = wowIconUrl(provided) || (meta ? wowIconUrl(meta.icon) : null);
  return h("span", { className: `ico-tile ${cls || ""}`, attrs: { "aria-hidden": "true" } },
    [src ? h("img", { attrs: { src, alt: "", width: "36", height: "36", loading: "lazy" } }) : null]);
}
function itemLink(id, level, opts) {
  opts = opts || {};
  const label = itemName(id, opts.name);
  const known = !/^Item \d+$/.test(label);
  return linkOrText(wowheadItemUrl(id, opts.bonus, level), label, {
    className: opts.className || "item",
    // Wowhead renames only the links whose name the data doesn't have.
    attrs: { "data-wh-rename-link": known ? "false" : "true" },
  });
}

/** A slanted bar (raid-frame style). share 0..1. */
function meter(share, mod) {
  return h("span", { className: `meter${mod ? " meter--" + mod : ""}`, attrs: { "aria-hidden": "true" } },
    [h("i", { vars: { "--w": `${Math.max(2, Math.min(100, share * 100)).toFixed(1)}%` } })]);
}

// The Raider.io staleness warning, recognised so it reads in the page language.
const STALE_RE = /^Raider\.io last read this character (\d+(?:\.\d+)?) days ago/;
function staleDays(warning) {
  const m = STALE_RE.exec(String(warning));
  return m ? Number(m[1]) : null;
}

// ---------------------------------------------------------------------------------------------
// State + loading
// ---------------------------------------------------------------------------------------------
const S = {
  index: null,
  latest: null,
  data: null, // the displayed run
  tab: "Mythic",
  loc: "All",
  sort: { key: "gain", dir: "desc" },
  folds: new Set(),
  openBosses: new Set(),
  historyExpanded: false,
  openGroups: new Set(),
  prev: new Map(),
  error: null,
  focusTab: null,
  tabChosen: false, // set by a click or ?tab=; until then a failed report gives way to one that worked
};

async function fetchJson(url) {
  let res;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (e) {
    throw new Error(`network error loading ${url}`);
  }
  if (!res.ok) throw new Error(`${url} responded ${res.status}`);
  try {
    return await res.json();
  } catch (e) {
    throw new Error(`${url} was not valid JSON`);
  }
}

function indexRuns() {
  return S.index && Array.isArray(S.index.runs) ? S.index.runs : [];
}
function char() {
  return S.data && Array.isArray(S.data.characters) ? S.data.characters[0] || null : null;
}
function reportFor(diff, c) {
  c = c || char();
  return c && Array.isArray(c.reports) ? c.reports.find((r) => r.difficulty === diff) || null : null;
}
function availableTabs() {
  return REPORT_DIFFICULTIES.filter((d) => reportFor(d));
}
/** Keep S.tab on a report this run has; unless the viewer picked it, prefer one that worked. */
function settleTab() {
  const avail = availableTabs();
  if (!avail.length) return;
  const ok = avail.filter((d) => !reportFor(d).error);
  if (!avail.includes(S.tab)) S.tab = (ok.length ? ok : avail)[(ok.length ? ok : avail).length - 1];
  else if (!S.tabChosen && reportFor(S.tab).error && ok.length) S.tab = ok[ok.length - 1];
}
function upgradesFor(diff) {
  const r = reportFor(diff);
  return r && !r.error ? computeUpgrades(r.results) : [];
}
function filterLoc(list, loc) {
  return loc === "All" ? list : list.filter((u) => u.dropLoc === loc);
}
function isLatest() {
  return Boolean(S.data && S.latest && S.data.run && S.latest.run && S.data.run.id === S.latest.run.id);
}
/** Game data: this run's raids, else the latest run's (older runs predate summary v2). */
function currentRaids() {
  const own = cleanRaids(S.data && S.data.raids);
  return own.length ? own : cleanRaids(S.latest && S.latest.raids);
}
/** The raid-night schedule is today's config, so the latest run's wins. */
function currentRaidNight() {
  return parseRaidNight((S.latest && S.latest.raid_night) || (S.data && S.data.raid_night));
}

function rerender() {
  const app = document.getElementById("app");
  if (!app) return;
  const scrollY = window.scrollY;
  render(app);
  document.documentElement.lang = lang();
  document.title = `${t("title")} · bmiest`;
  if (S.focusTab) {
    const el = document.getElementById(`tab-${S.focusTab}`);
    if (el) el.focus();
    S.focusTab = null;
  }
  window.scrollTo(0, scrollY);
  if (window.$WowheadPower && typeof window.$WowheadPower.refreshLinks === "function") window.$WowheadPower.refreshLinks();
}

async function navigateToRun(id) {
  if (!S.latest || !S.latest.run || id === S.latest.run.id) {
    S.data = S.latest;
    S.error = null;
    if (location.hash) history.replaceState(null, "", location.pathname + location.search);
    rerender();
    return;
  }
  const url = runDataUrl(id);
  if (!url) {
    S.error = t("invalidRunId", { id });
    rerender();
    return;
  }
  try {
    const data = await fetchJson(url);
    if (!data || !data.run) throw new Error(t("indexFormat"));
    S.data = data;
    learnItems(data);
    S.error = null;
    if (location.hash !== `#run=${id}`) history.replaceState(null, "", `#run=${id}`);
  } catch (e) {
    S.error = t("couldNotLoadRun", { id, msg: e.message });
  }
  rerender();
}
function applyHash() {
  const m = /^#run=([A-Za-z0-9_-]+)$/.exec(location.hash);
  if (m) return navigateToRun(m[1]);
  if (S.latest && S.data !== S.latest) return navigateToRun(S.latest.run.id);
  return Promise.resolve();
}

function setupWowheadTooltips() {
  // Hover tooltips. The page styles the links itself; only links without a known name get
  // renamed (data-wh-rename-link="true"; renameLinks must be on for Wowhead to fetch them),
  // and those names are remembered for the next re-render.
  window.whTooltips = { colorLinks: false, iconizeLinks: false, renameLinks: true };
  const s = document.createElement("script");
  s.src = "https://wow.zamimg.com/js/tooltips.js";
  s.async = true;
  document.head.appendChild(s);
  if (typeof MutationObserver === "undefined") return;
  const remember = (a) => {
    const m = /item=(\d+)/.exec(a.getAttribute("href") || "");
    const text = (a.textContent || "").trim();
    if (m && text && !/^Item \d+$/.test(text)) wowheadNames.set(Number(m[1]), text);
  };
  new MutationObserver((records) => {
    records.forEach((rec) => {
      const node = rec.target.nodeType === Node.TEXT_NODE ? rec.target.parentElement : rec.target;
      const a = node && node.closest ? node.closest('a[data-wh-rename-link="true"]') : null;
      if (a) remember(a);
    });
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
}

// The countdown ticks without a full re-render; when a raid night starts or ends, it re-renders.
let countdownTimer = null;
function startCountdown() {
  if (countdownTimer) return;
  countdownTimer = setInterval(() => {
    const el = document.querySelector("[data-until]");
    if (!el) return;
    const at = parseDate(el.getAttribute("data-until"));
    const left = at ? at.getTime() - Date.now() : 0;
    if (left <= 0) rerender();
    else el.textContent = t("inTime", { t: untilText(left) });
  }, 20000);
}

async function boot() {
  setupWowheadTooltips();
  const params = new URLSearchParams(location.search);
  if (REPORT_DIFFICULTIES.includes(params.get("tab"))) {
    S.tab = params.get("tab");
    S.tabChosen = true;
  }
  if (DROP_LOC_FILTERS.includes(params.get("loc"))) S.loc = params.get("loc");
  try {
    const [index, latest] = await Promise.all([fetchJson("data/index.json"), fetchJson("data/latest.json")]);
    if (!index || !Array.isArray(index.runs) || !latest || !latest.run) throw new Error(t("indexFormat"));
    S.index = index;
    S.latest = latest;
    S.data = latest;
    learnItems(latest);
  } catch (e) {
    S.error = t("couldNotLoadLatest", { msg: e.message });
  }
  window.addEventListener("hashchange", applyHash);
  if (S.latest && /^#run=/.test(location.hash)) await applyHash();
  else rerender();
  startCountdown();
}

// ---------------------------------------------------------------------------------------------
// Top of the page
// ---------------------------------------------------------------------------------------------
/** Broadcast top bar: flush blocks bmiest | run status | updated, then GitHub and EN | NL. */
function topBar() {
  const latest = indexRuns()[0];
  const when = latest ? latest.finished_at || latest.started_at : null;
  const bug = h("div", { className: "bug" }, [
    h("span", { className: "bug__brand" }, [icon("mark"), h("span", { text: "bmiest" })]),
    latest
      ? h("span", { className: `bug__status ${latest.ok ? "is-ok" : "is-fail"}` }, [
          latest.ok ? icon("check") : icon("x"),
          h("span", { text: latest.ok ? t("runOk") : t("runFailed") }),
        ])
      : h("span", { className: "bug__status", text: t("noRuns") }),
    // "Updated" is its own span so a phone can drop it and keep just the time.
    when ? h("span", { className: "bug__upd", attrs: { title: absoluteTime(when) } }, [h("span", { className: "bug__upd-pre", text: `${t("updated")} ` }), h("span", { text: relativeTime(when) })]) : null,
  ]);
  const gh = latest ? isGithubUrl(latest.url) : null;
  const langSwitch = h("div", { className: "lang-switch", attrs: { role: "group", "aria-label": t("langLabel") } },
    ["en", "nl"].map((l) => h("button", {
      text: l.toUpperCase(),
      attrs: { type: "button", lang: l, "aria-pressed": String(lang() === l) },
      on: {
        click: () => {
          if (l === lang()) return;
          setLang(l);
          rerender();
        },
      },
    })));
  return h("header", { className: "bar" }, [
    h("div", { className: "bar__in" }, [
      bug,
      h("div", { className: "bar__end" }, [gh ? extLink(gh, t("runOnGithub"), "bar__gh") : null, langSwitch]),
    ]),
  ]);
}

/** Title row: the page name, the character line and the profile link. */
function pageHead() {
  const c = char();
  const kids = [h("h1", { className: "ph__title", text: t("title") })];
  if (c) {
    const spec = c.spec && c.class ? `${c.spec} ${c.class}` : null;
    const rr = [capitalize(String(c.realm || "")), String(c.region || "").toUpperCase()].filter(Boolean).join(" ");
    const prof = raiderioProfileUrl(c);
    kids.push(h("div", { className: "ph__who" }, [
      h("span", { className: "ph__name", text: c.name || t("unknownCharacter") }),
      h("span", { className: "ph__meta", text: [spec, rr].filter(Boolean).join(" · ") }),
      prof ? extLink(prof, "Raider.IO", "ph__link") : null,
    ]));
  }
  return h("div", { className: "ph" }, [h("div", { className: "ph__row" }, kids), h("p", { className: "ph__lead", text: t("lead") })]);
}

/** Load errors, the viewing banner, run errors, skips and the pipeline's warnings. */
function alerts() {
  const out = h("div", { className: "alerts" });
  if (S.error) out.appendChild(h("div", { className: "alert alert--error", attrs: { role: "alert" } }, [icon("warn"), h("span", { text: S.error })]));
  if (S.data && S.latest && !isLatest()) {
    out.appendChild(h("div", { className: "alert alert--view" }, [
      h("span", { text: t("viewing", { when: shortDate(S.data.run.started_at) }) }),
      h("button", { className: "pill pill--action", text: t("back"), attrs: { type: "button" }, on: { click: () => navigateToRun(S.latest.run.id) } }),
    ]));
  }
  const c = char();
  if (c) {
    if (c.error) {
      out.appendChild(h("div", { className: "alert alert--error", attrs: { role: "alert" } }, [
        icon("warn"),
        h("span", { className: "alert__text" }, [h("b", { text: t("runError") }), h("span", { text: String(c.error) })]),
      ]));
    }
    if (c.skipped) out.appendChild(h("div", { className: "alert" }, [h("span", { text: typeof c.skipped === "string" ? t("skippedWhy", { why: c.skipped }) : t("skipped") })]));
    const prof = raiderioProfileUrl(c);
    (Array.isArray(c.warnings) ? c.warnings : []).forEach((w) => {
      const days = staleDays(w);
      const text = days !== null
        ? t("staleText", { days: new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(days) })
        : String(w);
      out.appendChild(h("div", { className: "alert alert--warn", attrs: { role: "status" } }, [
        icon("warn"),
        h("span", { className: "alert__text" }, [h("b", { text: days !== null ? t("staleTitle") : t("warning") }), h("span", { text })]),
        days !== null && prof ? extLink(prof, t("updateRio"), "alert__act") : null,
      ]));
    });
  }
  return out.childNodes.length ? out : null;
}

// ---------------------------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------------------------
/** Heroic | Mythic as flush tab blocks (ARIA tabs, arrow keys). */
function diffTabs(panelId) {
  const avail = availableTabs();
  const list = h("div", { className: "tabs", attrs: { role: "tablist", "aria-label": t("difficulty") } });
  avail.forEach((d, i) => {
    const sel = d === S.tab;
    list.appendChild(h("button", {
      className: "tabs__tab",
      text: d,
      attrs: { type: "button", role: "tab", id: `tab-${d}`, "aria-selected": String(sel), "aria-controls": panelId, tabindex: sel ? "0" : "-1" },
      on: {
        click: () => {
          S.tab = d;
          S.tabChosen = true;
          rerender();
        },
        keydown: (e) => {
          let n = null;
          if (e.key === "ArrowRight") n = (i + 1) % avail.length;
          else if (e.key === "ArrowLeft") n = (i - 1 + avail.length) % avail.length;
          else if (e.key === "Home") n = 0;
          else if (e.key === "End") n = avail.length - 1;
          if (n === null) return;
          e.preventDefault();
          S.tab = avail[n];
          S.tabChosen = true;
          S.focusTab = avail[n];
          rerender();
        },
      },
    }));
  });
  return list;
}

/** Source filters as slanted toggle pills with a count. */
function sourceFilters(ups) {
  const group = h("div", { className: "filters", attrs: { role: "group", "aria-label": t("source") } });
  DROP_LOC_FILTERS.forEach((loc) => {
    const on = loc === S.loc;
    group.appendChild(h("button", {
      className: `pill pill--filter${on ? " is-on" : ""}`,
      attrs: { type: "button", "aria-pressed": String(on) },
      on: {
        click: () => {
          S.loc = loc;
          rerender();
        },
      },
    }, [h("span", { text: loc === "All" ? t("filter_All") : loc }), h("span", { className: "pill__n mono", text: String(filterLoc(ups, loc).length) })]));
  });
  return group;
}

function reportLink(diff, cls) {
  const r = reportFor(diff);
  const url = r && !r.error ? isReportUrl(r.report_url) : null;
  return url ? extLink(url, t("openReport", { diff }), cls || "report-link") : null;
}

function sectionHead(title, caption, id) {
  return h("div", { className: "sh sh--sub" }, [
    h("h2", { className: "sh__title", text: title, attrs: { id } }),
    caption ? h("p", { className: "sh__cap", text: caption }) : null,
  ]);
}

// ---------------------------------------------------------------------------------------------
// Main column: the raid night, then M+ and crests
// ---------------------------------------------------------------------------------------------
function raidNightWhen(night) {
  const cfg = currentRaidNight();
  if (!night) return h("div", { className: "rn__when" }, [h("h2", { className: "rn__date", text: t("raidBosses"), attrs: { id: "rnH" } })]);
  const fmt = (o) => night.start.toLocaleString(locale(), { timeZone: cfg.tz, ...o });
  const tonight = night.live || night.dayOffset <= 0;
  const dayWord = tonight ? t("tonight") : capitalize(fmt({ weekday: "long" }));
  const range = `${fmt({ hour: "2-digit", minute: "2-digit" })}–${night.end.toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit", timeZone: cfg.tz })}`;
  return h("div", { className: "rn__when" }, [
    h("h2", { className: "rn__date", attrs: { id: "rnH" } }, [
      // The heading says when; screen readers also hear what it is.
      h("span", { className: "visually-hidden", text: `${night.live ? t("raidNow") : t("nextRaid")}: ` }),
      h("span", { text: `${dayWord} ` }),
      h("span", { className: "rn__time", text: fmt({ hour: "2-digit", minute: "2-digit" }) }),
    ]),
    h("p", { className: "rn__in" }, [
      // The heading already names the weekday on other days; "Tonight" doesn't.
      h("span", { text: `${capitalize(fmt(tonight ? { weekday: "long", day: "numeric", month: "long" } : { day: "numeric", month: "long" }))} · ` }),
      night.live
        ? h("b", { className: "mono", text: range, attrs: { "data-until": night.end.toISOString() } })
        : h("b", { className: "mono", text: t("inTime", { t: untilText(night.start - Date.now()) }), attrs: { "data-until": night.start.toISOString() } }),
    ]),
  ]);
}

const TILE_SHOW = 3;
function bossTile({ boss, items }, n, best, key) {
  const isBest = Boolean(best && items.some((u) => u.item === best.item));
  const open = S.openBosses.has(key);
  const shown = open ? items : items.slice(0, TILE_SHOW);
  const list = h("ul", { className: "rnb__list" }, items.length
    ? shown.map((u) => {
        const top = best && u.item === best.item;
        return h("li", { className: `rnb__it${top ? " is-best" : ""}` }, [
          itemIcon(u.item, u.icon),
          itemLink(u.item, u.level, { name: u.name }),
          h("span", { className: "pct mono", text: fmtPct(u.percDiff) }),
          top ? h("span", { className: "visually-hidden", text: ` (${t("bestUpgrade")})` }) : null,
        ]);
      })
    : [h("li", { className: "rnb__none", text: t("none") })]);
  if (items.length > TILE_SHOW) {
    list.appendChild(h("li", {}, [h("button", {
      className: "rnb__more",
      text: open ? t("showFewer") : t("more", { n: items.length - TILE_SHOW }),
      attrs: { type: "button", "aria-expanded": String(open) },
      on: {
        click: () => {
          if (open) S.openBosses.delete(key);
          else S.openBosses.add(key);
          rerender();
        },
      },
    })]));
  }
  return h("li", { className: `rnb${isBest ? " is-best" : ""}${items.length ? "" : " rnb--none"}` }, [
    h("div", { className: "rnb__top" }, [
      bossHead(boss),
      h("div", { className: "rnb__id" }, [
        n ? h("span", { className: "rnb__n mono", text: String(n).padStart(2, "0") }) : null,
        h("h4", { className: "rnb__name", text: boss.name }),
      ]),
    ]),
    list,
  ]);
}

function raidNightSection(all) {
  const night = nextRaidNight(currentRaidNight(), new Date());
  const best = all[0];
  const { plan, other } = planRaids(all, currentRaids());
  const sec = h("section", { className: "rn", attrs: { "aria-labelledby": "rnH", id: "panel-plan", role: "tabpanel" } });
  sec.appendChild(h("div", { className: "rn__head" }, [raidNightWhen(night), h("div", { className: "controls" }, [diffTabs("panel-plan"), reportLink(S.tab)])]));
  if (!reportFor(S.tab)) {
    sec.appendChild(h("p", { className: "empty", text: t("noReports") }));
    return sec;
  }
  if (reportFor(S.tab).error) {
    sec.appendChild(h("p", { className: "empty", text: t("reportFailed", { diff: S.tab }) }));
    return sec;
  }
  sec.appendChild(h("p", { className: "sh__cap", text: night && night.dayOffset <= 0 ? t("raidPlanCapTonight") : t("raidPlanCap") }));
  const block = (title, groups, numbered, keyBase) => {
    const count = groups.reduce((n, g) => n + g.items.length, 0);
    return h("div", { className: "rn__raid" }, [
      h("h3", { className: "rn__raidh" }, [h("b", { text: title }), h("span", { text: `${S.tab} · ${t("items", { n: count })}` })]),
      h("ol", { className: "rn__bosses" }, groups.map((g, i) => bossTile(g, numbered ? i + 1 : 0, best, `${keyBase}:${g.boss.id ?? g.boss.name}`))),
    ]);
  };
  plan.forEach(({ raid, bosses }) => sec.appendChild(block(raid.name, bosses, true, raid.id)));
  if (other.length) sec.appendChild(block(plan.length ? t("otherRaidDrops") : "Raid", other, false, "other"));
  if (!plan.length && !other.length) sec.appendChild(h("p", { className: "empty", text: t("noRaidUpgrades", { diff: S.tab }) }));
  return sec;
}

function dungeonWeek(all) {
  const best = all[0];
  const map = new Map();
  all.filter((u) => u.dropLoc === "Dungeon").forEach((u) => {
    const k = dropSourceName(u) || t("unknownSource");
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(u);
  });
  const rows = [...map.entries()].sort((a, b) => b[1][0].percDiff - a[1][0].percDiff).slice(0, 6);
  const max = rows.length ? rows[0][1][0].percDiff : 1;
  const sec = h("section", { attrs: { "aria-labelledby": "dgH" } }, [sectionHead(t("weekM"), t("weekMCap"), "dgH")]);
  if (!rows.length) {
    sec.appendChild(h("p", { className: "muted", text: t("noDungeonUpgrades", { diff: S.tab }) }));
    return sec;
  }
  sec.appendChild(h("ol", { className: "dg" }, rows.map(([name, items], i) => {
    const top = items[0];
    const isBest = Boolean(best && top.item === best.item);
    return h("li", { className: `dg__row${isBest ? " is-best" : ""}` }, [
      h("div", { className: "rib" }, [h("div", { className: "rib__bar" }, [h("div", { className: "rib__in" }, [
        h("span", { className: "rib__acc", text: String(i + 1) }),
        h("span", { className: "dg__name" }, [
          h("b", { text: name }),
          h("span", {}, [h("span", { text: `${t("items", { n: items.length })} · ` }), itemLink(top.item, top.level, { name: top.name })]),
        ]),
      ])])]),
      h("span", { className: "dg__gain" }, [meter(top.percDiff / max, isBest ? "gold" : "jade"), h("span", { className: "pct mono", text: fmtPct(top.percDiff) })]),
    ]);
  })));
  return sec;
}

/** Where a bonus roll is worth the most with this tab's coin: raid bosses and M+ dungeons. */
const BONUS_SHOW = 5;
function bonusRollSection() {
  const r = reportFor(S.tab);
  const rows = computeBonusRolls(r && !r.error ? r.results : null).filter((p) => p.avg > 0).slice(0, BONUS_SHOW);
  const sec = h("section", { attrs: { "aria-labelledby": "brH" } }, [sectionHead(t("bonusRoll"), t("bonusRollCap", { diff: S.tab }), "brH")]);
  if (!rows.length) {
    sec.appendChild(h("p", { className: "muted", text: t("noBonusRoll", { diff: S.tab }) }));
    return sec;
  }
  const raids = currentRaids();
  const max = rows[0].avg;
  const total = computeBonusRolls(r.results).length;
  sec.appendChild(h("ol", { className: "dg dg--tight" }, rows.map((p, i) => h("li", { className: "dg__row" }, [
    h("div", { className: "rib" }, [h("div", { className: "rib__bar" }, [h("div", { className: "rib__in" }, [
      h("span", { className: "rib__acc", text: String(i + 1) }),
      h("span", { className: "dg__name" }, [
        h("b", { text: sourceName({ dropLoc: p.dropLoc, dropSource: p.name }, raids) }),
        h("span", {}, [
          h("span", { text: `${p.dropLoc === "Raid" ? "Raid" : "M+"} ${p.level ?? "?"} · ` }),
          p.best ? itemLink(p.best.item, p.best.level, { name: p.best.name }) : null,
        ]),
      ]),
    ])])]),
    // The chance on its own: a boss with many items you can loot rarely gives the one you want.
    h("span", { className: "br__chance", attrs: { title: t("bonusChance", { up: p.upgrades, n: p.pool }) } }, [
      h("b", { className: "mono", text: fmtShare(p.upgrades / p.pool), attrs: { "aria-hidden": "true" } }),
      h("span", { text: t("bonusChanceShort", { up: p.upgrades, n: p.pool }), attrs: { "aria-hidden": "true" } }),
      h("span", { className: "visually-hidden", text: t("bonusChance", { up: p.upgrades, n: p.pool }) }),
    ]),
    h("span", { className: "dg__gain" }, [
      meter(p.avg / max, "jade"),
      h("span", { className: "pct mono", text: fmtPct(p.avg), attrs: { title: t("bonusAvg") } }),
      h("span", { className: "visually-hidden", text: ` ${t("bonusAvg")}` }),
    ]),
  ]))));
  sec.appendChild(h("button", {
    className: "rnb__more br__all",
    text: t("bonusAll", { n: total }),
    attrs: { type: "button" },
    on: {
      click: () => {
        S.folds.add("bonus");
        rerender();
        const fold = document.getElementById("fold-bonus");
        if (fold) fold.scrollIntoView({ block: "start" });
      },
    },
  }));
  return sec;
}

/** Every boss and dungeon with its whole loot pool: each item's gain and its 1-in-n chance. */
function bonusPoolTable(pools) {
  const raids = currentRaids();
  const share = (up, n) => `${fmtShare(up / n)} · ${up}/${n}`;
  const body = h("tbody", {});
  pools.forEach((p, i) => {
    const src = { dropLoc: p.dropLoc, dropSource: p.name };
    body.appendChild(h("tr", { className: "br-grp" }, [
      h("td", { className: "num mono", text: String(i + 1) }),
      h("th", { attrs: { scope: "rowgroup" } }, [h("span", { className: "gt__it" }, [
        sourceTile(src, raids, "boss-thumb--sm"),
        h("span", {}, [h("span", { className: "br-grp__name", text: sourceName(src, raids) }), h("span", { className: "gt__src", text: ` · ${p.dropLoc === "Raid" ? "Raid" : "M+"} ${p.level ?? "?"}` })]),
      ])]),
      h("td", { className: "gt__slot", text: t("bonusPoolItems", { n: p.pool }) }),
      h("td", { className: "num mono", text: share(p.upgrades, p.pool) }),
      h("td", { className: "num" }, [p.avg > 0 ? h("span", { className: "pct mono", text: fmtPct(p.avg), attrs: { title: t("bonusAvg") } }) : h("span", { className: "muted", text: "–" })]),
    ]));
    p.items.forEach((u) => body.appendChild(h("tr", { className: `br-it${u.percDiff > 0 ? "" : " is-miss"}` }, [
      h("td", {}),
      h("td", {}, [h("span", { className: "gt__it" }, [itemIcon(u.item, u.icon), itemLink(u.item, u.level, { name: u.name })])]),
      h("td", { className: "gt__slot", text: qeSlotLabel(u.slot) }),
      h("td", { className: "num mono", text: share(1, p.pool) }),
      h("td", { className: "num" }, [u.percDiff > 0 ? h("span", { className: "pct mono", text: fmtPct(u.percDiff) }) : h("span", { className: "muted", text: t("bonusMiss") })]),
    ])));
  });
  const head = h("tr", {}, [["#", true], [t("colBonusSource"), false], [t("slot"), false], [t("colChance"), true], [t("gain"), true]]
    .map(([label, num]) => h("th", { className: num ? "num" : "", text: label, attrs: { scope: "col" } })));
  return h("div", { className: "table-wrap", attrs: { tabindex: "0", role: "region", "aria-label": t("bonusAllFold") } },
    [h("table", { className: "gt gt--bonus" }, [h("thead", {}, [head]), body])]);
}

/** Crest rows: item, track rank -> max, item levels, slanted bar. */
function crestSection() {
  const c = char();
  const sec = h("section", { attrs: { "aria-labelledby": "crestH" } }, [sectionHead(t("crestNow"), t("crestCap"), "crestH")]);
  const box = h("div", { className: "crests" });
  sec.appendChild(box);
  const rep = c.crest_report;
  if (rep && typeof rep === "object") box.appendChild(extLink(isReportUrl(rep.report_url), t("crestReport"), "report-link"));
  const list = c.crest_upgrades;
  const note = (key) => box.appendChild(h("p", { className: "muted", text: t(key) }));
  if (list === null || list === undefined) {
    note("noCrestEstimate");
    return sec;
  }
  if (!Array.isArray(list) || !list.length) {
    note("fullyUpgraded");
    return sec;
  }
  const useful = usefulCrestUpgrades(list);
  if (!useful.length) {
    note("noCrestGain");
    return sec;
  }
  const max = useful.reduce((m, u) => Math.max(m, numOrNull(u.gain_pct) || 0), 0.0001);
  useful.forEach((u) => {
    const gain = numOrNull(u.gain_pct);
    const rank = numOrNull(u.rank);
    const lvl = numOrNull(u.level);
    const maxl = numOrNull(u.max_level);
    box.appendChild(h("div", { className: "crest" }, [
      itemIcon(u.item_id, u.icon),
      h("div", { className: "crest__body" }, [
        itemLink(u.item_id, u.level, { name: u.name, className: "item crest__item" }),
        h("span", { className: "crest__meta" }, [
          h("span", { text: `${qeSlotLabel(u.slot)} · ${typeof u.track === "string" ? u.track : "?"} ` }),
          h("span", { className: "mono", text: `${rank ?? "?"}/6 → 6/6 · ${lvl ?? "?"}→${maxl ?? "?"}` }),
        ]),
        gain === null
          ? h("span", { className: "muted", text: t("noEstimate") })
          : h("span", { className: "crest__bar" }, [meter(gain / max, "jade"), h("span", { className: "pct mono", text: fmtPct(gain) })]),
      ]),
    ]));
  });
  const left = list.length - useful.length;
  if (left > 0) box.appendChild(h("p", { className: "muted", text: t("crestLeftOut", { n: left }) }));
  return sec;
}

// ---------------------------------------------------------------------------------------------
// Folds: the full report and the gear
// ---------------------------------------------------------------------------------------------
const COLS = [
  { key: "rank", label: () => "#", num: true },
  { key: "item", label: () => t("item") },
  { key: "source", label: () => t("source") },
  { key: "slot", label: () => t("slot") },
  { key: "ilvl", label: () => t("ilvl"), num: true },
  { key: "gain", label: () => t("gain"), num: true },
];
function sortValue(u, key, all, raids) {
  if (key === "gain") return u.percDiff;
  if (key === "rank") return -all.indexOf(u);
  if (key === "item") return itemName(u.item, u.name);
  if (key === "source") return sourceName(u, raids);
  if (key === "slot") return qeSlotLabel(u.slot);
  if (key === "ilvl") return Number(u.level) || 0;
  return 0;
}
function reportTable(all) {
  const raids = currentRaids();
  const ups = filterLoc(all, S.loc).slice();
  if (!ups.length) {
    return h("div", { className: "empty" }, [
      h("p", { text: t("emptyFilter", { loc: S.loc, diff: S.tab }) }),
      S.loc !== "All"
        ? h("button", { className: "pill pill--action", text: t("emptyFilterAct"), attrs: { type: "button" }, on: { click: () => { S.loc = "All"; rerender(); } } })
        : null,
    ]);
  }
  const { key, dir } = S.sort;
  ups.sort((a, b) => {
    const va = sortValue(a, key, all, raids);
    const vb = sortValue(b, key, all, raids);
    const c = typeof va === "string" ? va.localeCompare(vb, locale()) : va - vb;
    return dir === "asc" ? c : -c;
  });
  const best = all[0];
  const head = h("tr", {}, COLS.map((col) => {
    const active = col.key === key;
    return h("th", { className: col.num ? "num" : "", attrs: { scope: "col", "aria-sort": active ? (dir === "asc" ? "ascending" : "descending") : null } }, [
      h("button", {
        className: "sorter",
        attrs: { type: "button", title: t("sortBy", { col: col.label() }) },
        on: {
          click: () => {
            const textual = col.key === "item" || col.key === "source" || col.key === "slot";
            S.sort = active ? { key, dir: dir === "asc" ? "desc" : "asc" } : { key: col.key, dir: textual ? "asc" : "desc" };
            rerender();
          },
        },
      }, [h("span", { text: col.label() }), icon("sort")]),
    ]);
  }));
  const body = h("tbody", {}, ups.map((u) => h("tr", { className: best && u.item === best.item ? "is-best" : "" }, [
    h("td", { className: "num mono", text: String(all.indexOf(u) + 1) }),
    h("td", {}, [h("span", { className: "gt__it" }, [itemIcon(u.item, u.icon), itemLink(u.item, u.level, { name: u.name })])]),
    h("td", {}, [h("span", { className: "gt__it" }, [sourceTile(u, raids, "boss-thumb--sm"), h("span", {}, [h("span", { text: sourceName(u, raids) }), sourceName(u, raids) === whereLabel(u) ? null : h("span", { className: "gt__src", text: ` · ${whereLabel(u)}` })])])]),
    h("td", { className: "gt__slot", text: qeSlotLabel(u.slot) }),
    h("td", { className: "num mono", text: String(u.level ?? "?") }),
    h("td", { className: "num" }, [h("span", { className: "pct mono", text: fmtPct(u.percDiff) })]),
  ])));
  return h("div", { className: "table-wrap", attrs: { tabindex: "0", role: "region", "aria-label": t("allReports") } }, [h("table", { className: "gt gt--report" }, [h("thead", {}, [head]), body])]);
}

/** The character block above the gear table: name, spec, avg ilvl, Raider.io read time. */
function gearId() {
  const c = char();
  const { avg, count, total } = computeAvgIlvl(c.gear);
  const kids = [
    h("div", { className: "gid__name", text: c.name || t("unknownCharacter") }),
    h("div", { className: "gid__spec", text: c.spec && c.class ? `${c.spec} ${c.class}` : t("unknownSpec") }),
    h("div", { className: "gid__ilvl" }, [h("span", { className: "mono", text: avg === null ? "?" : String(avg) }), h("small", { text: count < total ? `ilvl · ${count}/${total}` : "ilvl" })]),
  ];
  if (typeof c.gear_as_of === "string") {
    const read = parseDate(c.gear_as_of);
    const stale = read && Date.now() - read.getTime() > DAY_MS;
    kids.push(h("div", { className: `gid__asof${stale ? " is-stale" : ""}`, text: t("raiderioRead", { when: relativeTime(c.gear_as_of) }), attrs: { title: absoluteTime(c.gear_as_of) } }));
  }
  const prof = raiderioProfileUrl(c);
  if (prof) kids.push(extLink(prof, t("updateRio"), "gid__upd"));
  return h("div", { className: "gid" }, kids);
}

/** Gear by slot: equipped item and ilvl, then the best upgrade in the open report. */
function gearTable() {
  const c = char();
  const raids = currentRaids();
  const bySlot = new Map((c.gear || []).map((g) => [g.slot, g]));
  const best = bestUpgradeBySlot(c, S.tab);
  const top = upgradesFor(S.tab)[0];
  const head = h("tr", {}, [
    h("th", { text: t("slot"), attrs: { scope: "col" } }),
    h("th", { text: t("equipped"), attrs: { scope: "col" } }),
    h("th", { className: "num", text: t("ilvl"), attrs: { scope: "col" } }),
    h("th", { text: t("bestFor", { diff: S.tab }), attrs: { scope: "col" } }),
    h("th", { className: "num", text: t("ilvl"), attrs: { scope: "col" } }),
    h("th", { className: "num", text: t("gain"), attrs: { scope: "col" } }),
  ]);
  const body = h("tbody", {}, ILVL_SLOTS.map((slot) => {
    const g = bySlot.get(slot);
    const up = best.get(slot);
    const isTop = up && top && up.item === top.item;
    return h("tr", { className: isTop ? "is-best" : "" }, [
      h("th", { className: "gt__slot", text: slotLabel(slot), attrs: { scope: "row" } }),
      h("td", {}, [g ? h("span", { className: "gt__it" }, [itemIcon(g.item_id, g.icon), itemLink(g.item_id, g.ilvl, { bonus: g.bonus_ids, name: g.name })]) : h("span", { className: "muted", text: "–" })]),
      h("td", { className: "num mono", text: g && Number.isFinite(g.ilvl) ? String(g.ilvl) : "?" }),
      h("td", {}, [up
        ? h("span", { className: "gt__it" }, [itemIcon(up.item, up.icon), h("span", { className: "gt__upw" }, [itemLink(up.item, up.level, { name: up.name }), h("span", { className: "gt__src", text: sourceName(up, raids) })])])
        : h("span", { className: "muted", text: t("noneShort") })]),
      h("td", { className: "num mono", text: up && Number.isFinite(up.level) ? String(up.level) : "" }),
      h("td", { className: "num" }, [up ? h("span", { className: "pct mono", text: fmtPct(up.percDiff) }) : null]),
    ]);
  }));
  return h("div", { className: "table-wrap", attrs: { tabindex: "0", role: "region", "aria-label": t("gearTable") } }, [h("table", { className: "gt gt--gear" }, [h("thead", {}, [head]), body])]);
}

function foldSection(id, title, hint, bodyKids) {
  const d = h("details", { className: "fold-sec", attrs: { open: S.folds.has(id), id: `fold-${id}` } }, [
    h("summary", { className: "disclose" }, [h("span", { className: "fold__title", text: title }), h("span", { className: "fold__hint", text: hint })]),
    h("div", { className: "fold-sec__body" }, bodyKids),
  ]);
  d.addEventListener("toggle", () => {
    if (d.open) S.folds.add(id);
    else S.folds.delete(id);
  });
  return d;
}

function folds(all) {
  const power = computePowerToGain(filterLoc(all, S.loc));
  const kids = [
    foldSection("report", t("allReports"), t("allReportsHint", { n: all.length, diff: S.tab }), [
      h("div", { className: "controls" }, [sourceFilters(all), reportLink(S.tab)]),
      power
        ? h("p", { className: "power", attrs: { title: t("powerHint") } }, [
            h("span", { text: t("powerToGain") }),
            h("b", { className: "mono", text: fmtPct(power.pct) }),
            h("span", { text: S.loc === "All" ? t("powerNote", { n: power.items }) : t("powerNoteLoc", { n: power.items, loc: S.loc }) }),
          ])
        : null,
      h("p", { className: "sh__cap", text: t("reportCap") }),
      reportTable(all),
    ]),
  ];
  const rep = reportFor(S.tab);
  const pools = computeBonusRolls(rep && !rep.error ? rep.results : null);
  if (pools.length) {
    kids.push(foldSection("bonus", t("bonusAllFold"), t("bonusAllHint", { n: pools.length, diff: S.tab }), [
      h("p", { className: "sh__cap", text: t("bonusHow") }),
      bonusPoolTable(pools),
    ]));
  }
  if (Array.isArray(char().gear) && char().gear.length) {
    kids.push(foldSection("gear", t("gearFold"), t("gearFoldHint"), [h("div", { className: "gear" }, [gearId(), gearTable()])]));
  }
  return h("div", { className: "folds" }, kids);
}

// ---------------------------------------------------------------------------------------------
// Rail: run status, changes since the previous run, run history
// ---------------------------------------------------------------------------------------------
function reportLinks(reports, stop) {
  const byDiff = new Map(reports.map((r) => [r.difficulty, r]));
  return h("span", { className: "hrow__reports" }, REPORT_DIFFICULTIES.filter((d) => byDiff.has(d)).map((d) => {
    const r = byDiff.get(d);
    const up = r.uploaded === true && !r.error;
    const a = linkOrText(r.error ? null : isReportUrl(r.report_url), d, {
      className: `hrow__rep${r.error ? " is-fail" : ""}${up ? " is-up" : ""}`,
      title: t(r.error ? "reportError" : up ? "reportTitleUploaded" : "reportTitle", { diff: d }),
      kids: up ? [icon("check")] : null,
    });
    if (stop) a.addEventListener("click", (e) => e.stopPropagation());
    return a;
  }));
}

function statusBlock() {
  const run = S.data.run || {};
  const when = run.finished_at || run.started_at;
  const gh = isGithubUrl(run.url);
  const c = char();
  return h("div", { className: `status${run.ok ? "" : " is-fail"}` }, [
    h("div", { className: "status__row" }, [
      h("span", { className: `tag ${run.ok ? "tag--ok" : "tag--fail"}`, text: run.ok ? t("ok") : t("failed") }),
      h("span", { className: "status__when", text: relativeTime(when), attrs: { title: absoluteTime(when) } }),
    ]),
    h("div", { className: "status__row status__meta" }, [h("span", { text: `${triggerLabel(run.trigger)} · ${shortDate(when)}` }), gh ? extLink(gh, "GitHub", "hrow__gh") : null]),
    c && Array.isArray(c.reports) && c.reports.length ? reportLinks(c.reports, false) : null,
    run.ok ? null : h("p", { className: "status__why", text: t("failedWhy") }),
  ]);
}

function historyBlock() {
  const runs = indexRuns();
  const box = h("div", { className: "history" });
  if (!runs.length) {
    box.appendChild(h("p", { className: "muted", text: t("noRunsRecorded") }));
    return box;
  }
  const groups = groupRuns(runs);
  const VISIBLE = 7;
  const shown = S.historyExpanded ? groups : groups.slice(0, VISIBLE);
  const list = h("ol", { className: "history__list" });
  shown.forEach((g) => {
    const [head, ...rest] = g;
    const open = S.openGroups.has(head.id);
    list.appendChild(historyRow(head, rest.length ? { n: rest.length, open } : null, false));
    if (open) rest.forEach((r) => list.appendChild(historyRow(r, null, true)));
  });
  box.appendChild(list);
  if (groups.length > VISIBLE) {
    box.appendChild(h("button", {
      className: "pill pill--action",
      text: S.historyExpanded ? t("showFewer") : t("showAll", { n: runs.length }),
      attrs: { type: "button", "aria-expanded": String(S.historyExpanded) },
      on: { click: () => { S.historyExpanded = !S.historyExpanded; rerender(); } },
    }));
  }
  return box;
}
function historyRow(run, fold, nested) {
  const active = Boolean(S.data && S.data.run && S.data.run.id === run.id);
  const reports = (Array.isArray(run.characters) ? run.characters : []).flatMap((c) => (Array.isArray(c.reports) ? c.reports : []));
  const gh = isGithubUrl(run.url);
  const ghLink = gh ? h("a", { className: "hrow__gh", attrs: { href: gh, target: "_blank", rel: "noopener noreferrer", "aria-label": `GitHub ${shortDate(run.started_at)}` } }, [h("span", { text: "GitHub" }), icon("ext")]) : null;
  if (ghLink) ghLink.addEventListener("click", (e) => e.stopPropagation());
  return h("li", {
    className: `hrow${run.ok ? "" : " hrow--fail"}${nested ? " hrow--nested" : ""}${active ? " is-active" : ""}`,
    attrs: { tabindex: "0", role: "link", "aria-current": active ? "true" : null, "aria-label": t("openRun", { when: shortDate(run.started_at) }) },
    on: {
      click: () => navigateToRun(run.id),
      keydown: (e) => {
        if (e.target !== e.currentTarget) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigateToRun(run.id);
        }
      },
    },
  }, [
    h("span", { className: "hrow__when mono", text: shortDate(run.started_at), attrs: { title: absoluteTime(run.started_at) } }),
    h("span", { className: "hrow__trig", text: triggerLabel(run.trigger) }),
    h("span", { className: `tag ${run.ok ? "tag--ok" : "tag--fail"}`, text: run.ok ? t("ok") : t("failed") }),
    reportLinks(reports, true),
    ghLink,
    fold
      ? h("button", {
          className: `hrow__fold${fold.open ? " is-open" : ""}`,
          attrs: { type: "button", "aria-expanded": String(fold.open) },
          on: {
            click: (e) => {
              e.stopPropagation();
              if (S.openGroups.has(run.id)) S.openGroups.delete(run.id);
              else S.openGroups.add(run.id);
              rerender();
            },
          },
        }, [icon(fold.open ? "minus" : "plus"), h("span", { text: t("sameResults", { n: fold.n }) })])
      : null,
  ]);
}

/** "Since the previous run": diff against the closest older run that has this report. */
function previousRunWith(runId, diff) {
  const runs = indexRuns();
  const at = runs.findIndex((r) => r.id === runId);
  if (at < 0) return null;
  for (const run of runs.slice(at + 1)) {
    const c = Array.isArray(run.characters) ? run.characters[0] : null;
    const reps = c && Array.isArray(c.reports) ? c.reports : [];
    if (reps.some((r) => r.difficulty === diff && !r.error)) return run;
  }
  return null;
}
function loadPrev(id) {
  if (!S.prev.has(id)) {
    const url = runDataUrl(id);
    S.prev.set(id, url ? fetchJson(url).then((d) => { learnItems(d); return d; }).catch(() => null) : Promise.resolve(null));
  }
  return S.prev.get(id);
}
function diffRuns(cur, prev, diff) {
  const ups = (c) => {
    const r = c && Array.isArray(c.reports) ? c.reports.find((x) => x.difficulty === diff) : null;
    return new Map(computeUpgrades(r ? r.results : []).map((u) => [u.item, u]));
  };
  const now = ups(cur);
  const before = ups(prev);
  const gearOf = (c) => new Map((c && Array.isArray(c.gear) ? c.gear : []).map((g) => [g.slot, g]));
  const gn = gearOf(cur);
  const gb = gearOf(prev);
  const gear = [];
  for (const slot of ILVL_SLOTS) {
    const a = gb.get(slot);
    const b = gn.get(slot);
    if (a && b && (a.item_id !== b.item_id || a.ilvl !== b.ilvl)) gear.push({ slot, before: a, after: b });
  }
  return { added: [...now.values()].filter((u) => !before.has(u.item)), removed: [...before.values()].filter((u) => !now.has(u.item)), gear };
}
function changesBlock(diff) {
  const box = h("div", { className: "changes" });
  const runId = S.data && S.data.run ? S.data.run.id : null;
  const prev = runId ? previousRunWith(runId, diff) : null;
  if (!prev) {
    box.appendChild(h("p", { className: "muted", text: t("noPrevious") }));
    return box;
  }
  const when = relativeTime(prev.started_at);
  box.setAttribute("title", absoluteTime(prev.started_at));
  const body = h("div", { className: "changes__body", attrs: { "aria-live": "polite" } }, [h("span", { className: "muted", text: "…" })]);
  box.appendChild(body);
  const data = S.data;
  loadPrev(prev.id).then((p) => {
    clear(body);
    if (!p) {
      body.appendChild(h("p", { className: "muted", text: t("previousUnavailable") }));
      return;
    }
    const { added, removed, gear } = diffRuns((data.characters || [])[0], (p.characters || [])[0], diff);
    if (!added.length && !removed.length && !gear.length) {
      body.appendChild(h("p", { className: "changes__none" }, [icon("check"), h("span", { text: t("noChanges", { when }) })]));
      return;
    }
    const line = (label, mod, kids) => h("div", { className: "changes__line" }, [h("span", { className: `tag tag--${mod}`, text: label }), h("div", { className: "changes__items" }, kids)]);
    const items = (list) => list.map((u) => h("span", { className: "changes__item" }, [itemLink(u.item, u.level, { name: u.name }), h("span", { className: "pct mono", text: fmtPct(u.percDiff) })]));
    body.appendChild(h("p", { className: "changes__lead", text: t("changedSince", { when }) }));
    if (added.length) body.appendChild(line(t("changesNew"), "ok", items(added)));
    if (removed.length) body.appendChild(line(t("changesGone"), "muted", items(removed)));
    if (gear.length) {
      body.appendChild(line(t("changesGear"), "muted", gear.map(({ slot, before, after }) => h("span", { className: "changes__item" }, [
        h("span", { className: "changes__slot", text: `${slotLabel(slot)} ` }),
        h("span", { className: "mono", text: `${before.ilvl ?? "?"} → ${after.ilvl ?? "?"}` }),
      ]))));
    }
    if (window.$WowheadPower && typeof window.$WowheadPower.refreshLinks === "function") window.$WowheadPower.refreshLinks();
  });
  return box;
}

function rail() {
  const block = (id, title, kid) => h("section", { className: "rail-block", attrs: { "aria-labelledby": id } }, [
    h("h2", { className: "rail-block__h", text: title, attrs: { id } }),
    kid,
  ]);
  return h("aside", { className: "rail", attrs: { "aria-label": t("railLabel") } }, [
    block("stH", t("status"), statusBlock()),
    reportFor(S.tab) && !reportFor(S.tab).error ? block("chH", `${t("changes")} · ${S.tab}`, changesBlock(S.tab)) : null,
    block("histH", t("historyHeading"), historyBlock()),
  ]);
}

// ---------------------------------------------------------------------------------------------
// Footer and page
// ---------------------------------------------------------------------------------------------
function footer() {
  const prof = raiderioProfileUrl(char());
  return h("footer", { className: "foot" }, [
    h("details", { className: "fold" }, [
      h("summary", { className: "disclose" }, [h("span", { className: "fold__title", text: t("howItWorks") }), h("span", { className: "fold__hint", text: t("howHint") })]),
      h("ol", { className: "fold__list" }, ["how1", "how2", "how3", "how4"].map((k) => h("li", { text: t(k) }))),
    ]),
    // Raider.io's API terms ask for a link back to raider.io.
    h("p", { className: "foot__line" }, [
      h("span", { text: `${t("gearData")} ` }),
      h("a", { text: "Raider.IO", attrs: { href: prof || "https://raider.io", target: "_blank", rel: "noopener noreferrer" } }),
      h("span", { text: " · QE Live · Wowhead · " }),
      h("a", { text: t("sourceOnGithub"), attrs: { href: "https://github.com/Bmiest/bmiest_wowaudit_wishlist_updater", target: "_blank", rel: "noopener noreferrer" } }),
    ]),
  ]);
}

function render(app) {
  clear(app);
  app.appendChild(topBar());
  const page = h("main", { className: "page", attrs: { id: "main" } });
  app.appendChild(page);
  page.appendChild(pageHead());
  const a = alerts();
  if (a) page.appendChild(a);
  if (S.data && char()) {
    settleTab();
    const all = upgradesFor(S.tab);
    const main = h("div", { className: "main" }, [raidNightSection(all)]);
    const rep = reportFor(S.tab);
    if (rep && !rep.error) {
      main.appendChild(h("div", { className: "two two--even" }, [dungeonWeek(all), bonusRollSection()]));
      main.appendChild(h("div", { className: "two" }, [crestSection()]));
      main.appendChild(folds(all));
    } else if (availableTabs().length) {
      main.appendChild(h("div", { className: "two" }, [crestSection()]));
    }
    page.appendChild(h("div", { className: "grid" }, [main, rail()]));
  } else if (S.data) {
    page.appendChild(h("div", { className: "grid" }, [h("p", { className: "empty", text: t("noCharacterData") }), rail()]));
  }
  page.appendChild(footer());
}

if (typeof document !== "undefined" && document.addEventListener) document.addEventListener("DOMContentLoaded", boot);
