// Unit tests for the dashboard's plain functions (site/app.js, site/i18n.js), run with
// `node --test tests/js/` (tests/test_site.py runs them under pytest when node is installed).
// The scripts are loaded the way the browser loads them: as classic scripts sharing one global
// scope, here a vm context with just enough of `window` for the top level to run.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const SITE = new URL("../../site/", import.meta.url);
const read = (f) => readFileSync(new URL(f, SITE), "utf8");

function load(lang = "en") {
  const ctx = {
    location: { search: `?lang=${lang}`, hash: "", pathname: "/" },
    navigator: { languages: ["en"] },
    localStorage: { getItem: () => null, setItem: () => {} },
    Intl, URLSearchParams, console,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of ["i18n.js", "bossart.js", "app.js"]) vm.runInContext(read(f), ctx, { filename: f });
  // Results cross the vm boundary as JSON, so deepEqual compares plain values.
  return (expr) => {
    const out = vm.runInContext(`JSON.stringify(${expr})`, ctx);
    return out === undefined ? undefined : JSON.parse(out);
  };
}

test("no markup sinks: data only ever reaches the page as text", () => {
  for (const f of ["app.js", "i18n.js", "bossart.js"]) {
    const src = read(f);
    for (const sink of [".innerHTML", ".outerHTML", "insertAdjacentHTML(", "document.write(", "eval(", "new Function"]) {
      assert.ok(!src.includes(sink), `${f} uses ${sink}`);
    }
  }
});

test("EN and NL have the same keys, and every key app.js asks for exists", () => {
  const js = load();
  const en = js("Object.keys(I18N.en)").sort();
  const nl = js("Object.keys(I18N.nl)").sort();
  assert.deepEqual(nl, en);
  const used = [...read("app.js").matchAll(/\bt\("([A-Za-z_0-9]+)"/g)].map((m) => m[1]);
  for (const key of used) assert.ok(en.includes(key), `missing i18n key ${key}`);
  for (const k of ["slot_head", "trigger_schedule", "qeslot_Finger", "reportTitleUploaded", "how4"]) assert.ok(en.includes(k));
});

test("URL validators refuse anything but their fixed shapes", () => {
  const js = load();
  assert.equal(js('wowheadItemUrl(123, [1, 2], 330)'), "https://www.wowhead.com/item=123?bonus=1:2&ilvl=330");
  assert.equal(js('wowheadItemUrl("12x")'), null);
  assert.equal(js('wowheadItemUrl(5, ["1;alert(1)"])'), "https://www.wowhead.com/item=5");
  assert.equal(js('wowIconUrl("inv_helm_01")'), "https://wow.zamimg.com/images/wow/icons/medium/inv_helm_01.jpg");
  for (const bad of ['"../x"', '"javascript:alert(1)"', '"A b"', "null", "7"]) assert.equal(js(`wowIconUrl(${bad})`), null);
  assert.equal(js("bossHeadUrl(142077)"), "img/boss/head-142077.webp");
  assert.equal(js('bossHeadUrl("142077")'), null);
  assert.equal(js('runDataUrl("123_ab")'), "data/runs/123_ab.json");
  assert.equal(js('runDataUrl("../index")'), null);
  assert.equal(js('isReportUrl("https://questionablyepic.com/live/upgradereport/x")'), "https://questionablyepic.com/live/upgradereport/x");
  assert.equal(js('isReportUrl("javascript:alert(1)//https://questionablyepic.com/")'), null);
  assert.equal(js('isGithubUrl("https://evil.example/https://github.com/")'), null);
  assert.equal(js('raiderioProfileUrl({ name: "Shiftheal", realm: "ragnaros", region: "eu" })'), "https://raider.io/characters/eu/ragnaros/Shiftheal");
  assert.equal(js('raiderioProfileUrl({ name: "Shiftheal", realm: "../x", region: "eu" })'), null);
});

test("computeUpgrades keeps one row per item, the max-upgrade row first, upgrades only", () => {
  const js = load();
  const rows = js(`computeUpgrades([
    { item: 1, percDiff: 0.5, dropType: "drop" }, { item: 1, percDiff: 0.4, dropType: "max" },
    { item: 2, percDiff: 0.9 }, { item: 3, percDiff: 0 }, { item: 4, percDiff: "1" }])`);
  assert.deepEqual(rows.map((r) => [r.item, r.percDiff]), [[2, 0.9], [1, 0.4]]);
});

test("computeBonusRolls averages a roll over the whole pool, misses as 0, shared items in both", () => {
  const js = load();
  const rows = js(`computeBonusRolls([
    { item: 1, percDiff: 1.5, dropType: "bonus", dropLoc: "Raid", dropSource: "Ula'tek", level: 344 },
    { item: 2, percDiff: 0, dropType: "bonus", dropLoc: "Raid", dropSource: "Ula'tek", level: 344 },
    { item: 2, percDiff: 0.3, dropType: "bonus", dropLoc: "Raid", dropSource: "Ula'tek", level: 344 },
    { item: 1, percDiff: 9, dropType: "max", dropLoc: "Raid", dropSource: "Ula'tek" },
    { item: 3, percDiff: 0.6, dropType: "bonus", dropLoc: "Raid", dropSource: "Nek'zali / Vashnik", level: 334 },
    { item: 4, percDiff: -0.2, dropType: "bonus", dropLoc: "Raid", dropSource: "Vashnik", level: 334 },
    { item: 5, percDiff: 0.2, dropType: "bonus", dropLoc: "Dungeon", dropSource: "Murder Row", level: 334 },
    { item: 6, percDiff: 0.9, dropType: "bonus", dropLoc: "Delves", dropSource: "Delves" },
    { item: 7, percDiff: "1", dropType: "bonus", dropLoc: "Raid", dropSource: "Ula'tek" }])`);
  assert.deepEqual(rows.map((p) => [p.name, p.dropLoc, p.pool, p.upgrades, Number(p.avg.toFixed(3)), p.level, p.best && p.best.item]), [
    ["Ula'tek", "Raid", 2, 2, 0.9, 344, 1],
    ["Nek'zali", "Raid", 1, 1, 0.6, 334, 3],
    ["Vashnik", "Raid", 2, 1, 0.3, 334, 3],
    ["Murder Row", "Dungeon", 1, 1, 0.2, 334, 5],
  ]);
  assert.deepEqual(js("computeBonusRolls(null)"), []);
});

const NIGHT = 'parseRaidNight({ days: ["Wednesday", "Sunday"], start: "20:00", end: "23:00", timezone: "Europe/Brussels" })';
const at = (js, iso) => js(`(() => { const n = nextRaidNight(${NIGHT}, new Date("${iso}")); return n && { start: n.start.toISOString(), end: n.end.toISOString(), live: n.live, dayOffset: n.dayOffset }; })()`);

test("the next raid night is computed in the raid's time zone, DST included", () => {
  const js = load();
  // Sunday 4 Oct 2026, CEST (UTC+2): tonight 20:00 = 18:00 UTC.
  assert.deepEqual(at(js, "2026-10-04T08:00:00Z"), { start: "2026-10-04T18:00:00.000Z", end: "2026-10-04T21:00:00.000Z", live: false, dayOffset: 0 });
  assert.equal(at(js, "2026-10-04T19:00:00Z").live, true);
  // After the raid: Wednesday.
  assert.deepEqual(at(js, "2026-10-04T21:30:00Z"), { start: "2026-10-07T18:00:00.000Z", end: "2026-10-07T21:00:00.000Z", live: false, dayOffset: 3 });
  // Sunday 25 Oct 2026, the clocks went back that night: CET (UTC+1).
  assert.equal(at(js, "2026-10-25T10:00:00Z").start, "2026-10-25T19:00:00.000Z");
  // A raid that runs past midnight is still live after it.
  const late = 'parseRaidNight({ days: ["Saturday"], start: "23:00", end: "01:00", timezone: "Europe/Brussels" })';
  const n = js(`nextRaidNight(${late}, new Date("2026-10-03T22:30:00Z"))`);
  assert.equal(n.live, true);
  assert.equal(n.end, "2026-10-03T23:00:00.000Z");
});

test("a raid-night config that doesn't parse shows the bosses undated instead", () => {
  const js = load();
  assert.equal(js('parseRaidNight({ days: ["Sunday"], start: "20:00", end: "23:00", timezone: "Mars/Olympus" })'), null);
  assert.equal(js('parseRaidNight({ days: ["Someday"], start: "20:00", end: "23:00", timezone: "UTC" })'), null);
  assert.equal(js('parseRaidNight({ days: ["Sunday"], start: "8pm", end: "23:00", timezone: "UTC" })'), null);
  assert.equal(js("parseRaidNight(null)"), null);
  assert.equal(js("nextRaidNight(null, new Date())"), null);
});

test("planRaids puts each raid upgrade under its bosses in kill order, the rest under other", () => {
  const js = load();
  const plan = js(`(() => {
    const raids = cleanRaids([{ id: 1320, name: "The Venomous Abyss", bosses: [
      { id: 2888, name: "Nek'zali" }, { id: 2874, name: "Entombed Sentinels" }, { id: 2895, name: "Ula'tek" }] }]);
    const ups = [
      { item: 1, percDiff: 1.5, dropLoc: "Raid", dropSource: "Ula'tek" },
      { item: 2, percDiff: 0.7, dropLoc: "Raid", dropSource: "Nek'zali / Entombed Sentinels" },
      { item: 3, percDiff: 0.6, dropLoc: "Raid", dropSource: "Someone New" },
      { item: 4, percDiff: 0.9, dropLoc: "Dungeon", dropSource: "Ula'tek" },
    ];
    const { plan, other } = planRaids(ups, raids);
    return {
      bosses: plan[0].bosses.map((b) => [b.boss.name, b.boss.head, b.items.map((u) => u.item)]),
      other: other.map((o) => [o.boss.name, o.items.map((u) => u.item)]),
    };
  })()`);
  assert.deepEqual(plan.bosses, [
    ["Nek'zali the Soulcoiler", 142077, [2]],
    ["Entombed Sentinels", 143437, [2]],
    ["Ula'tek", 140369, [1]],
  ]);
  assert.deepEqual(plan.other, [["Someone New", [3]]]);
});

test("the Raider.io staleness warning is recognised so it can be translated", () => {
  const js = load("nl");
  assert.equal(js('staleDays("Raider.io last read this character 2.9 days ago, so recent gear changes may be missing.")'), 2.9);
  assert.equal(js('staleDays("head: override is for item 1 but 2 is equipped.")'), null);
  assert.match(js('t("staleText", { days: "2,9" })'), /2,9 dagen/);
  assert.equal(js("fmtPct(1.5)"), "+1,50%");
});

test("bossart.js only holds integer display ids and plain names", () => {
  const js = load();
  for (const [id, v] of Object.entries(js("window.BossArt"))) {
    assert.match(id, /^\d+$/);
    assert.ok(Number.isInteger(v.head) && v.head > 0, id);
    assert.equal(typeof v.name, "string");
    readFileSync(new URL(`img/boss/head-${v.head}.webp`, SITE)); // the head ships with the site
  }
});
