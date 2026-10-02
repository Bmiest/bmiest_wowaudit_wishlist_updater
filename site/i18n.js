// EN/NL strings for the dashboard. Loaded before app.js.
//
// The language comes from ?lang=en|nl, else the last choice (localStorage), else the
// browser language (nl* -> Dutch), else English. Game data -- item, boss, dungeon and spec
// names, difficulties, Raid/Dungeon/Delves/Crafted -- stays in English in both, the way
// Dutch-speaking players use it.
//
// Values are plain strings with {name} placeholders, or functions of the same vars object
// where the wording depends on a number.

const I18N = {
  en: {
    pageTitle: "Gear upgrade reports for WoW",
    lead: "Daily QE Live upgrade reports for Shiftheal: what to wish for in raid and M+, and where to spend crests.",
    langLabel: "Language",
    keyStats: "Key stats",
    latestReports: "Latest reports",
    reportsFromRun: "Reports from this run",
    reportsCaption: "The % is QE's estimate of how much more you'd heal if this item replaced the one you wear now. Your equipped gear counts at max upgrade, and no sockets are added.",
    crestHeading: "Where to spend crests",
    crestCaption: "QE's estimate of each item at max upgrade compared with how it's equipped now. Crest costs aren't shown.",
    historyHeading: "Run history",
    historyCaption: "Every automated run. Click one to see its reports. Runs in a row that found the same are folded together.",
    historyLegend: "✓ marks the report that was uploaded.",
    gearHeading: "Gear",
    gearCaption: "Equipped gear as of this run, from ",
    gearCaptionUpgrade: "Under each slot: the best upgrade in the report you have open.",
    howItWorks: "How this works",
    how1: "Gear comes from Raider.io, plus the catalyst and crafted stats it can't see, which are stored in the repo. Manual runs can use a pasted /simc export instead.",
    how2: "QE Live's Upgrade Finder runs in a headless browser, first for Heroic and then for Mythic. No sockets are added, and your equipped gear counts at max upgrade.",
    how3: "The boss or dungeon each upgrade drops from comes from QE Live's item database.",
    how4: "This page is republished after every run.",
    gearData: "Gear data: ",
    sourceOnGithub: "Source on GitHub",

    unknownTime: "unknown time",
    justNow: "just now",
    updated: "updated {when}",
    noRuns: "No runs yet",
    latestOk: "Latest run OK",
    latestFailed: "Latest run failed",
    viewOnGithub: "View on GitHub",
    unavailable: "Unavailable",
    ok: "OK",
    failed: "Failed",
    unknownCharacter: "Unknown character",
    unknownSpec: "Unknown spec",
    unknown: "Unknown",

    trigger_schedule: "Scheduled",
    trigger_workflow_dispatch: "Manual run",
    trigger_local: "Local run",
    unknownTrigger: "Unknown trigger",

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

    filter_All: "All",
    raidDifficulty: "Raid · difficulty {d}",
    unknownSource: "Unknown source",

    powerHint: "The biggest upgrade in every slot added up (the best two rings and trinkets; a two-hander or a one-hander plus off-hand). QE rates each item against your current gear, so this is an estimate. QE gives % of your healing, not HPS.",
    reportError: "{diff}: error",
    reportTitle: "{diff} report",
    reportTitleUploaded: "{diff} report, uploaded",

    noRunsRecorded: "No runs recorded yet.",
    showFewer: "Show fewer",
    showAll: "Show all {n}",
    showTop: "Show top {n}",
    sameResults: ({ n }) => (n === 1 ? "+1 run with the same results" : `+${n} runs with the same results`),
    sameResultsHide: "Hide the runs with the same results",
    viewingRun: "Viewing run ",
    backToLatest: "Back to latest",

    bestMythicUpgrade: "Best Mythic upgrade",
    noUpgrades: "No upgrades found",
    mythicPowerToGain: "Mythic power to gain",
    notInRunData: "Not in this run's data",
    powerNote: ({ n }) => `healing, with the best item in every slot (${n} items)`,
    powerNoteLoc: ({ n, loc }) => `healing, with the best ${loc} item in every slot (${n} items)`,
    nextCrest: "Next crest",
    noEstimate: "No estimate",
    noEstimateLower: "no estimate",
    allUpgraded: "All upgraded",
    nothingWorthCrest: "Nothing gains from crests",
    avgIlvl: "Avg ilvl",
    basedOnSlots: "based on {count} of {total} slots",
    lastRun: "Last run",

    noCharacterData: "No character data for this run.",
    runNoCharacterData: "This run has no character data.",
    skipped: "Skipped",
    skippedWhy: "Skipped: {why}",
    noReports: "No reports for this run.",
    reportDifficulty: "Report difficulty",
    openReport: "Open report ↗",
    error: "Error",
    powerToGain: "Power to gain",
    noUpgradesFilter: "No upgrades in this filter.",

    sincePrevious: "Since the previous run",
    sincePreviousWhen: "Since the previous run ({when})",
    changesNew: "New",
    changesGone: "Gone",
    changesGear: "Gear",
    noChanges: "No changes since the previous run.",
    noPrevious: "No earlier run to compare with.",
    previousUnavailable: "The previous run couldn't be loaded.",

    crestReport: "Crest report ↗",
    crestReportTitle: "{diff} crest report",
    noCrestEstimate: "No crest estimate for this run.",
    fullyUpgraded: "Everything is fully upgraded.",
    noCrestGain: "No item gains anything from crests right now.",

    avgIlvlPrefix: "Avg ilvl ",
    slotsNote: " ({count}/{total} slots)",
    raiderioRead: "Raider.io read {when}",
    gearStale: "Gear may be out of date",
    gearStaleTitle: "Raider.io last read this character more than a day ago, so upgrades may be measured against old gear. Update it on Raider.io.",
    updateOnRaiderio: "Update on Raider.io ↗",
    bestForSlot: "Best {diff} upgrade for this slot",

    couldNotLoadLatest: "Could not load the latest run: {msg}",
    couldNotLoadRun: "Could not load run {id}: {msg}",
    invalidRunId: "\"{id}\" is not a valid run id.",
    couldNotLoadIndex: "Could not load the run index: {msg}",
    historyUnavailable: "Run history is unavailable.",
    reportsUnavailable: "Reports are unavailable.",
    indexFormat: "The run index isn't in the expected format.",
  },

  nl: {
    pageTitle: "Gear-upgraderapporten voor WoW",
    lead: "Dagelijkse QE Live-upgraderapporten voor Shiftheal: wat je wenst voor raid en M+, en waar je crests aan besteedt.",
    langLabel: "Taal",
    keyStats: "Kerncijfers",
    latestReports: "Laatste rapporten",
    reportsFromRun: "Rapporten van deze run",
    reportsCaption: "Het % is QE's schatting van hoeveel meer je zou healen als dit item het item vervangt dat je nu draagt. Je huidige gear telt op max upgrade, en er worden geen sockets toegevoegd.",
    crestHeading: "Waar je crests aan besteedt",
    crestCaption: "QE's schatting van elk item op max upgrade, vergeleken met hoe je het nu draagt. Crest-kosten staan er niet bij.",
    historyHeading: "Run-historiek",
    historyCaption: "Elke automatische run. Klik erop om de rapporten te zien. Opeenvolgende runs met hetzelfde resultaat worden samengevouwen.",
    historyLegend: "✓ markeert het rapport dat geüpload is.",
    gearHeading: "Gear",
    gearCaption: "Gedragen gear op het moment van deze run, van ",
    gearCaptionUpgrade: "Onder elk slot: de beste upgrade uit het rapport dat openstaat.",
    howItWorks: "Hoe dit werkt",
    how1: "De gear komt van Raider.io, plus de catalyst- en crafted-stats die Raider.io niet ziet; die staan in de repo. Handmatige runs kunnen in de plaats een geplakte /simc-export gebruiken.",
    how2: "QE Live's Upgrade Finder draait in een headless browser, eerst voor Heroic en daarna voor Mythic. Er worden geen sockets toegevoegd, en je huidige gear telt op max upgrade.",
    how3: "Van welke boss of dungeon elke upgrade dropt, komt uit QE Live's itemdatabase.",
    how4: "Deze pagina wordt na elke run opnieuw gepubliceerd.",
    gearData: "Gear-data: ",
    sourceOnGithub: "Broncode op GitHub",

    unknownTime: "onbekend tijdstip",
    justNow: "zonet",
    updated: "bijgewerkt {when}",
    noRuns: "Nog geen runs",
    latestOk: "Laatste run OK",
    latestFailed: "Laatste run mislukt",
    viewOnGithub: "Bekijk op GitHub",
    unavailable: "Niet beschikbaar",
    ok: "OK",
    failed: "Mislukt",
    unknownCharacter: "Onbekend personage",
    unknownSpec: "Onbekende spec",
    unknown: "Onbekend",

    trigger_schedule: "Gepland",
    trigger_workflow_dispatch: "Handmatig",
    trigger_local: "Lokale run",
    unknownTrigger: "Onbekende trigger",

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

    filter_All: "Alles",
    raidDifficulty: "Raid · moeilijkheid {d}",
    unknownSource: "Onbekende bron",

    powerHint: "De grootste upgrade in elk slot opgeteld (de beste twee ringen en trinkets; een two-hander of een one-hander plus off-hand). QE meet elk item tegen je huidige gear, dus dit is een schatting. QE geeft % van je healing, geen HPS.",
    reportError: "{diff}: fout",
    reportTitle: "{diff}-rapport",
    reportTitleUploaded: "{diff}-rapport, geüpload",

    noRunsRecorded: "Nog geen runs geregistreerd.",
    showFewer: "Toon minder",
    showAll: "Toon alle {n}",
    showTop: "Toon top {n}",
    sameResults: ({ n }) => (n === 1 ? "+1 run met hetzelfde resultaat" : `+${n} runs met hetzelfde resultaat`),
    sameResultsHide: "Verberg de runs met hetzelfde resultaat",
    viewingRun: "Je bekijkt run ",
    backToLatest: "Terug naar de laatste",

    bestMythicUpgrade: "Beste Mythic-upgrade",
    noUpgrades: "Geen upgrades gevonden",
    mythicPowerToGain: "Mythic: te halen winst",
    notInRunData: "Niet in de data van deze run",
    powerNote: ({ n }) => `healing, met het beste item in elk slot (${n} items)`,
    powerNoteLoc: ({ n, loc }) => `healing, met het beste ${loc}-item in elk slot (${n} items)`,
    nextCrest: "Volgende crest",
    noEstimate: "Geen schatting",
    noEstimateLower: "geen schatting",
    allUpgraded: "Alles geüpgraded",
    nothingWorthCrest: "Niets wint met crests",
    avgIlvl: "Gem. ilvl",
    basedOnSlots: "op basis van {count} van {total} slots",
    lastRun: "Laatste run",

    noCharacterData: "Geen personagedata voor deze run.",
    runNoCharacterData: "Deze run heeft geen personagedata.",
    skipped: "Overgeslagen",
    skippedWhy: "Overgeslagen: {why}",
    noReports: "Geen rapporten voor deze run.",
    reportDifficulty: "Moeilijkheid van het rapport",
    openReport: "Open rapport ↗",
    error: "Fout",
    powerToGain: "Te halen winst",
    noUpgradesFilter: "Geen upgrades in deze filter.",

    sincePrevious: "Sinds de vorige run",
    sincePreviousWhen: "Sinds de vorige run ({when})",
    changesNew: "Nieuw",
    changesGone: "Weg",
    changesGear: "Gear",
    noChanges: "Geen wijzigingen sinds de vorige run.",
    noPrevious: "Geen eerdere run om mee te vergelijken.",
    previousUnavailable: "De vorige run kon niet geladen worden.",

    crestReport: "Crest-rapport ↗",
    crestReportTitle: "{diff}-crestrapport",
    noCrestEstimate: "Geen crest-schatting voor deze run.",
    fullyUpgraded: "Alles is volledig geüpgraded.",
    noCrestGain: "Geen enkel item wint nu iets met crests.",

    avgIlvlPrefix: "Gem. ilvl ",
    slotsNote: " ({count}/{total} slots)",
    raiderioRead: "Raider.io las {when}",
    gearStale: "Gear is mogelijk verouderd",
    gearStaleTitle: "Raider.io las dit personage langer dan een dag geleden, dus upgrades worden mogelijk tegen oude gear gemeten. Update het op Raider.io.",
    updateOnRaiderio: "Update op Raider.io ↗",
    bestForSlot: "Beste {diff}-upgrade voor dit slot",

    couldNotLoadLatest: "Kon de laatste run niet laden: {msg}",
    couldNotLoadRun: "Kon run {id} niet laden: {msg}",
    invalidRunId: "\"{id}\" is geen geldige run-id.",
    couldNotLoadIndex: "Kon de run-index niet laden: {msg}",
    historyUnavailable: "De run-historiek is niet beschikbaar.",
    reportsUnavailable: "De rapporten zijn niet beschikbaar.",
    indexFormat: "De run-index heeft niet het verwachte formaat.",
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
function fmtPct(n) {
  const num = new Intl.NumberFormat(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `+${num.format(n)}%`;
}

/** Fill every [data-i18n] element's text and [data-i18n-aria] element's aria-label. */
function applyStaticText() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
}
