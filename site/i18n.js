// EN/NL strings for the dashboard. Loaded before app.js.
//
// The language comes from ?lang=en|nl, else the last choice (localStorage), else the
// browser language (nl* -> Dutch), else English. Game data -- item, boss, dungeon, raid and
// spec names, difficulties, Raid/Dungeon/Delves/Crafted, upgrade tracks -- stays in English in
// both, the way Dutch-speaking players use it.
//
// Values are plain strings with {name} placeholders, or functions of the same vars object
// where the wording depends on a number. tests/js checks that both tables have the same keys.

const I18N = {
  en: {
    title: "Gear upgrades",
    lead: "What to wish for in raid and M+ and where to spend crests, from the daily QE Live reports.",
    langLabel: "Language",
    updated: "Updated",
    runOk: "Run OK",
    runFailed: "Run failed",
    runOnGithub: "Run on GitHub",
    noRuns: "No runs yet",

    staleTitle: "Gear may be out of date",
    staleText: "Raider.IO last read this character {days} days ago, so recent gear changes may be missing. Paste a /simc export for an up-to-date run.",
    updateRio: "Update on Raider.IO",
    warning: "Warning",
    runError: "This run failed",
    viewing: "You're viewing the run of {when}",
    back: "Back to the latest",

    nextRaid: "Next raid night",
    raidNow: "Raid night now",
    tonight: "Tonight",
    inTime: "in {t}",
    hourUnit: "h",
    raidBosses: "Raid bosses",
    raidPlanCap: "What each boss can drop for you, in kill order · gold = best upgrade",
    raidPlanCapTonight: "What each boss can drop for you tonight, in kill order · gold = best upgrade",
    difficulty: "Difficulty",
    openReport: "Open {diff} report",
    items: ({ n }) => (n === 1 ? "1 upgrade" : `${n} upgrades`),
    none: "Nothing for you here",
    more: ({ n }) => `+${n} more`,
    bestUpgrade: "best upgrade",
    otherRaidDrops: "Other raid drops",
    noRaidUpgrades: "No raid upgrades in the {diff} report.",
    noReports: "No reports for this run.",
    reportFailed: "The {diff} report failed in this run.",

    weekM: "Best M+ dungeons this week",
    weekMCap: "Ranked by the biggest upgrade you can get there.",
    noDungeonUpgrades: "No dungeon upgrades in the {diff} report.",
    bonusRoll: "Best bonus roll",
    bonusRollCap: "A {diff} coin, items at max upgrade. Chance: how many of the items it can drop for you are an upgrade. Ranked by the bar, the average gain per roll (misses count as 0).",
    bonusChance: ({ up, n }) => `chance of an upgrade: ${up} of ${n} items`,
    bonusChanceShort: ({ up, n }) => `chance ${up}/${n}`,
    bonusAvg: "average gain per roll",
    bonusAll: ({ n }) => `All ${n} bosses and dungeons, item by item`,
    bonusAllFold: "All bonus rolls",
    bonusAllHint: "Every boss and M+ dungeon with its whole loot pool, {diff} coin ({n})",
    bonusHow: "A bonus roll gives one item from the boss's loot pool, each about as likely: the items QE checked for your spec, so every item is 1 in n. Chance = the upgrades among them; their chances add up to the boss's. Gain = per item, at the level a roll gives, at max upgrade; on the boss row the average per roll, misses counted as 0.",
    bonusPoolItems: ({ n }) => (n === 1 ? "1 item" : `${n} items`),
    bonusMiss: "no upgrade",
    colBonusSource: "Boss / item",
    colChance: "Chance",
    noBonusRoll: "No bonus roll is an upgrade in the {diff} report.",
    crestNow: "Spend crests now",
    crestCap: "Each item at max upgrade against how you wear it now. Crest costs aren't shown.",
    crestReport: "Crest report",
    crestLeftOut: ({ n }) => (n === 1 ? "1 item gains nothing and is left out." : `${n} items gain nothing and are left out.`),
    noCrestEstimate: "No crest estimate for this run.",
    fullyUpgraded: "Everything is fully upgraded.",
    noCrestGain: "No item gains anything from crests right now.",
    noEstimate: "No estimate",

    allReports: "Full report",
    allReportsHint: "All {n} {diff} upgrades as a sortable table",
    reportCap: "% = QE's estimate of how much more you'd heal with this item instead of the one you wear now. Your gear counts at max upgrade, no sockets added.",
    source: "Source",
    filter_All: "All",
    emptyFilter: "No {loc} upgrades in the {diff} report.",
    emptyFilterAct: "Show all sources",
    powerToGain: "Power to gain",
    powerHint: "The biggest upgrade in every slot added up (the best two rings and trinkets; a two-hander or a one-hander plus off-hand). QE rates each item against your current gear, so this is an estimate. QE gives % of your healing, not HPS.",
    powerNote: ({ n }) => `healing, with the best item in every slot (${n} items)`,
    powerNoteLoc: ({ n, loc }) => `healing, with the best ${loc} item in every slot (${n} items)`,
    item: "Item",
    slot: "Slot",
    ilvl: "ilvl",
    gain: "Gain",
    sortBy: "Sort by {col}",
    gearFold: "Gear",
    gearFoldHint: "Equipped items with the best upgrade per slot",
    gearTable: "Gear by slot",
    equipped: "Equipped",
    bestFor: "Best {diff} upgrade",
    noneShort: "No upgrade",
    raiderioRead: "Raider.IO read {when}",

    railLabel: "Run status and history",
    status: "Run status",
    failedWhy: "Something went wrong in this run; the reason is in the GitHub run log.",
    changes: "Changes",
    noChanges: "No changes since {when}: same upgrades, same gear.",
    changedSince: "Changed since {when}:",
    noPrevious: "No earlier run to compare with.",
    previousUnavailable: "The previous run couldn't be loaded.",
    changesNew: "New",
    changesGone: "Gone",
    changesGear: "Gear",
    historyHeading: "Run history",
    openRun: "Open the run of {when}",
    noRunsRecorded: "No runs recorded yet.",
    showFewer: "Show fewer",
    showAll: "Show all {n}",
    sameResults: ({ n }) => (n === 1 ? "+1 run with the same results" : `+${n} runs with the same results`),
    reportError: "{diff}: error",
    reportTitle: "{diff} report",
    reportTitleUploaded: "{diff} report, uploaded to the wishlist",
    ok: "OK",
    failed: "Failed",

    howItWorks: "How this works",
    how1: "Gear comes from Raider.IO, plus the catalyst and crafted stats it can't see, which are stored in the repo. Manual runs can use a pasted /simc export instead.",
    how2: "QE Live's Upgrade Finder runs in a headless browser, first for Heroic and then for Mythic. No sockets are added, and your equipped gear counts at max upgrade.",
    how3: "Item names, the boss or dungeon each upgrade drops from and each raid's kill order come from QE Live's item and instance databases. The raid nights are set in the repo.",
    how4: "This page is republished after every run.",
    sourceOnGithub: "Source on GitHub",
    ftName: "Wishlist updater",
    ftMeta: "Daily QE Live upgrade reports for WoWAudit",
    ftTop: "Back to top",
    ftSources: "Sources",
    ftSrcRio: "the character's gear",
    ftSrcQe: "the upgrade reports, items and drop sources",
    ftSrcAudit: "the wishlists the reports go into",
    ftSrcWh: "item names and icons",
    ftSrcBz: "the boss portraits",
    ftFb: "Something wrong in a report, or an idea? Let me know.",
    ftFbBtn: "Open an issue",
    ftFbDm: "Or on Discord:",
    ftLegal: "Fan-made, not affiliated with Blizzard Entertainment. World of Warcraft and the boss renders are trademarks and work of Blizzard Entertainment, Inc.",

    unknownTime: "unknown time",
    justNow: "just now",
    unknownCharacter: "Unknown character",
    unknownSpec: "Unknown spec",
    unknownSource: "Unknown source",
    unknownItem: "Unknown item",
    unknownTrigger: "Unknown trigger",
    noCharacterData: "No character data for this run.",
    skipped: "Skipped",
    skippedWhy: "Skipped: {why}",
    trigger_schedule: "Scheduled",
    trigger_workflow_dispatch: "Manual run",
    trigger_local: "Local run",

    slot_head: "Head",
    slot_neck: "Neck",
    slot_shoulder: "Shoulders",
    slot_back: "Back",
    slot_chest: "Chest",
    slot_shirt: "Shirt",
    slot_tabard: "Tabard",
    slot_wrist: "Wrists",
    slot_hands: "Hands",
    slot_waist: "Waist",
    slot_legs: "Legs",
    slot_feet: "Feet",
    slot_finger1: "Ring 1",
    slot_finger2: "Ring 2",
    slot_trinket1: "Trinket 1",
    slot_trinket2: "Trinket 2",
    slot_main_hand: "Main hand",
    slot_off_hand: "Off hand",
    qeslot_Finger: "Ring",
    qeslot_Trinket: "Trinket",
    qeslot_1H: "One-hand",
    qeslot_2H: "Two-hand",
    qeslot_Shield: "Shield",

    couldNotLoadLatest: "Could not load the latest run: {msg}",
    couldNotLoadRun: "Could not load that run: {msg}",
    invalidRunId: "\"{id}\" is not a valid run id.",
    indexFormat: "The run data isn't in the expected format.",
  },

  nl: {
    title: "Gear-upgrades",
    lead: "Wat je wenst voor raid en M+ en waar je crests aan besteedt, uit de dagelijkse QE Live-rapporten.",
    langLabel: "Taal",
    updated: "Bijgewerkt",
    runOk: "Run OK",
    runFailed: "Run mislukt",
    runOnGithub: "Run op GitHub",
    noRuns: "Nog geen runs",

    staleTitle: "Gear is mogelijk verouderd",
    staleText: "Raider.IO las dit personage {days} dagen geleden, dus recente gearwijzigingen kunnen ontbreken. Plak een /simc-export voor een actuele run.",
    updateRio: "Update op Raider.IO",
    warning: "Waarschuwing",
    runError: "Deze run is mislukt",
    viewing: "Je bekijkt de run van {when}",
    back: "Terug naar de laatste",

    nextRaid: "Volgende raidavond",
    raidNow: "Nu raidavond",
    tonight: "Vanavond",
    inTime: "over {t}",
    hourUnit: "u",
    raidBosses: "Raidbosses",
    raidPlanCap: "Wat elke boss voor jou kan droppen, in killvolgorde · goud = beste upgrade",
    raidPlanCapTonight: "Wat elke boss vanavond voor jou kan droppen, in killvolgorde · goud = beste upgrade",
    difficulty: "Moeilijkheid",
    openReport: "Open {diff}-rapport",
    items: ({ n }) => (n === 1 ? "1 upgrade" : `${n} upgrades`),
    none: "Niets voor jou",
    more: ({ n }) => `+${n} meer`,
    bestUpgrade: "beste upgrade",
    otherRaidDrops: "Andere raiddrops",
    noRaidUpgrades: "Geen raidupgrades in het {diff}-rapport.",
    noReports: "Geen rapporten voor deze run.",
    reportFailed: "Het {diff}-rapport is in deze run mislukt.",

    weekM: "Beste M+-dungeons deze week",
    weekMCap: "Gerangschikt op de grootste upgrade die je er kunt halen.",
    noDungeonUpgrades: "Geen dungeonupgrades in het {diff}-rapport.",
    bonusRoll: "Beste bonus roll",
    bonusRollCap: "Een {diff}-coin, items op max upgrade. Kans: hoeveel van de items die er voor jou kunnen droppen een upgrade zijn. Gerangschikt op de balk, de gemiddelde winst per roll (missers tellen als 0).",
    bonusChance: ({ up, n }) => `kans op een upgrade: ${up} van ${n} items`,
    bonusChanceShort: ({ up, n }) => `kans ${up}/${n}`,
    bonusAvg: "gemiddelde winst per roll",
    bonusAll: ({ n }) => `Alle ${n} bosses en dungeons, item per item`,
    bonusAllFold: "Alle bonus rolls",
    bonusAllHint: "Elke boss en M+-dungeon met zijn hele lootpool, {diff}-coin ({n})",
    bonusHow: "Een bonus roll geeft één item uit de lootpool van de boss, elk ongeveer even waarschijnlijk: de items die QE voor jouw spec nakeek, dus elk item is 1 op n. Kans = de upgrades daartussen; hun kansen tellen op tot die van de boss. Winst = per item, op het niveau dat een roll geeft, op max upgrade; op de bossrij het gemiddelde per roll, missers tellen als 0.",
    bonusPoolItems: ({ n }) => (n === 1 ? "1 item" : `${n} items`),
    bonusMiss: "geen upgrade",
    colBonusSource: "Boss / item",
    colChance: "Kans",
    noBonusRoll: "Geen enkele bonus roll is een upgrade in het {diff}-rapport.",
    crestNow: "Besteed nu je crests",
    crestCap: "Elk item op max upgrade, tegenover hoe je het nu draagt. Crest-kosten staan er niet bij.",
    crestReport: "Crest-rapport",
    crestLeftOut: ({ n }) => (n === 1 ? "1 item wint niets en staat er niet bij." : `${n} items winnen niets en staan er niet bij.`),
    noCrestEstimate: "Geen crest-schatting voor deze run.",
    fullyUpgraded: "Alles is volledig geüpgraded.",
    noCrestGain: "Geen enkel item wint nu iets met crests.",
    noEstimate: "Geen schatting",

    allReports: "Volledig rapport",
    allReportsHint: "Alle {n} {diff}-upgrades als sorteerbare tabel",
    reportCap: "% = QE's schatting van hoeveel meer je zou healen met dit item in plaats van het item dat je nu draagt. Je gear telt op max upgrade, zonder sockets.",
    source: "Bron",
    filter_All: "Alles",
    emptyFilter: "Geen {loc}-upgrades in het {diff}-rapport.",
    emptyFilterAct: "Toon alle bronnen",
    powerToGain: "Te halen winst",
    powerHint: "De grootste upgrade in elk slot opgeteld (de beste twee ringen en trinkets; een two-hander of een one-hander plus off-hand). QE meet elk item tegen je huidige gear, dus dit is een schatting. QE geeft % van je healing, geen HPS.",
    powerNote: ({ n }) => `healing, met het beste item in elk slot (${n} items)`,
    powerNoteLoc: ({ n, loc }) => `healing, met het beste ${loc}-item in elk slot (${n} items)`,
    item: "Item",
    slot: "Slot",
    ilvl: "ilvl",
    gain: "Winst",
    sortBy: "Sorteer op {col}",
    gearFold: "Gear",
    gearFoldHint: "Gedragen items met de beste upgrade per slot",
    gearTable: "Gear per slot",
    equipped: "Gedragen",
    bestFor: "Beste {diff}-upgrade",
    noneShort: "Geen upgrade",
    raiderioRead: "Raider.IO las {when}",

    railLabel: "Run-status en historiek",
    status: "Run-status",
    failedWhy: "Er ging iets mis in deze run; de reden staat in het log van de GitHub-run.",
    changes: "Wijzigingen",
    noChanges: "Geen wijzigingen sinds {when}: dezelfde upgrades, dezelfde gear.",
    changedSince: "Gewijzigd sinds {when}:",
    noPrevious: "Geen eerdere run om mee te vergelijken.",
    previousUnavailable: "De vorige run kon niet geladen worden.",
    changesNew: "Nieuw",
    changesGone: "Weg",
    changesGear: "Gear",
    historyHeading: "Run-historiek",
    openRun: "Open de run van {when}",
    noRunsRecorded: "Nog geen runs geregistreerd.",
    showFewer: "Toon minder",
    showAll: "Toon alle {n}",
    sameResults: ({ n }) => (n === 1 ? "+1 run met hetzelfde resultaat" : `+${n} runs met hetzelfde resultaat`),
    reportError: "{diff}: fout",
    reportTitle: "{diff}-rapport",
    reportTitleUploaded: "{diff}-rapport, geüpload naar de wishlist",
    ok: "OK",
    failed: "Mislukt",

    howItWorks: "Hoe dit werkt",
    how1: "De gear komt van Raider.IO, plus de catalyst- en crafted-stats die Raider.IO niet ziet; die staan in de repo. Handmatige runs kunnen in de plaats een geplakte /simc-export gebruiken.",
    how2: "QE Live's Upgrade Finder draait in een headless browser, eerst voor Heroic en daarna voor Mythic. Er worden geen sockets toegevoegd, en je huidige gear telt op max upgrade.",
    how3: "Itemnamen, van welke boss of dungeon elke upgrade dropt en de killvolgorde van elke raid komen uit QE Live's item- en instancedatabase. De raidavonden staan in de repo.",
    how4: "Deze pagina wordt na elke run opnieuw gepubliceerd.",
    sourceOnGithub: "Broncode op GitHub",
    ftName: "Wishlist updater",
    ftMeta: "Dagelijkse QE Live-upgraderapporten voor WoWAudit",
    ftTop: "Naar boven",
    ftSources: "Bronnen",
    ftSrcRio: "de gear van het character",
    ftSrcQe: "de upgraderapporten, items en dropbronnen",
    ftSrcAudit: "de wishlists waar de rapporten in gaan",
    ftSrcWh: "itemnamen en iconen",
    ftSrcBz: "de bossportretten",
    ftFb: "Klopt er iets niet in een rapport, of heb je een idee? Laat het weten.",
    ftFbBtn: "Open een issue",
    ftFbDm: "Of op Discord:",
    ftLegal: "Gemaakt door een fan, niet verbonden aan Blizzard Entertainment. World of Warcraft en de bossrenders zijn handelsmerken en werk van Blizzard Entertainment, Inc.",

    unknownTime: "onbekend tijdstip",
    justNow: "zonet",
    unknownCharacter: "Onbekend personage",
    unknownSpec: "Onbekende spec",
    unknownSource: "Onbekende bron",
    unknownItem: "Onbekend item",
    unknownTrigger: "Onbekende trigger",
    noCharacterData: "Geen personagedata voor deze run.",
    skipped: "Overgeslagen",
    skippedWhy: "Overgeslagen: {why}",
    trigger_schedule: "Gepland",
    trigger_workflow_dispatch: "Handmatig",
    trigger_local: "Lokale run",

    slot_head: "Hoofd",
    slot_neck: "Hals",
    slot_shoulder: "Schouders",
    slot_back: "Rug",
    slot_chest: "Borst",
    slot_shirt: "Shirt",
    slot_tabard: "Tabard",
    slot_wrist: "Polsen",
    slot_hands: "Handen",
    slot_waist: "Taille",
    slot_legs: "Benen",
    slot_feet: "Voeten",
    slot_finger1: "Ring 1",
    slot_finger2: "Ring 2",
    slot_trinket1: "Trinket 1",
    slot_trinket2: "Trinket 2",
    slot_main_hand: "Main hand",
    slot_off_hand: "Off hand",
    qeslot_Finger: "Ring",
    qeslot_Trinket: "Trinket",
    qeslot_1H: "One-hand",
    qeslot_2H: "Two-hand",
    qeslot_Shield: "Schild",

    couldNotLoadLatest: "Kon de laatste run niet laden: {msg}",
    couldNotLoadRun: "Kon die run niet laden: {msg}",
    invalidRunId: "\"{id}\" is geen geldige run-id.",
    indexFormat: "De rundata heeft niet het verwachte formaat.",
  },
};

const LANGS = ["en", "nl"];
const LANG_LOCALES = { en: "en-GB", nl: "nl-BE" };
const LANG_STORAGE_KEY = "lang";

function resolveLang() {
  const fromUrl = new URLSearchParams(location.search).get("lang");
  if (LANGS.includes(fromUrl)) return fromUrl;
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (LANGS.includes(stored)) return stored;
  } catch (err) {
    // Storage blocked (private window, previews): fall through to the browser language.
  }
  const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "";
  return nav.toLowerCase().startsWith("nl") ? "nl" : "en";
}

let currentLang = resolveLang();

function lang() {
  return currentLang;
}

function locale() {
  return LANG_LOCALES[currentLang];
}

/** Store the choice and switch. The caller re-renders. */
function setLang(next) {
  if (!LANGS.includes(next)) return;
  currentLang = next;
  try {
    localStorage.setItem(LANG_STORAGE_KEY, next);
  } catch (err) {
    // Not remembered, but the switch still works for this page view.
  }
}

/** Look a string up in the current language, falling back to English, then to the key. */
function t(key, vars) {
  const table = I18N[currentLang];
  const value = Object.hasOwn(table, key) ? table[key] : I18N.en[key];
  if (value === undefined) return key;
  if (typeof value === "function") return value(vars || {});
  if (!vars) return value;
  return value.replace(/\{(\w+)\}/g, (m, k) => (Object.hasOwn(vars, k) ? String(vars[k]) : m));
}

/** "+1.57%" / "+1,57%". */
/** A share 0..1 as a whole percentage ("67%"), in the page's number format. */
function fmtShare(x) {
  return new Intl.NumberFormat(locale(), { style: "percent", maximumFractionDigits: 0 }).format(x);
}
function fmtPct(n) {
  const num = new Intl.NumberFormat(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `+${num.format(n)}%`;
}
