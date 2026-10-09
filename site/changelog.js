// changelog.html, built like wijzigingen.html on racetodutchfirst.nl: both languages in the
// page, a version per entry on a rail, the live one marked "live now". The entries come from
// changelog-data.js; which version is live comes from version.json (written by the deploy from
// pyproject.toml), and without it the newest entry. The language is i18n.js's (?lang, then the
// choice on the dashboard, then the browser); the NL | EN switch changes it and remembers it.
"use strict";

(() => {
  const DATE = { en: "en-US", nl: "nl-BE" };
  const LIVE = { en: "Live now", nl: "Nu live" };
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const day = (iso, l) => {
    const d = new Date(`${iso}T12:00:00`);
    return isNaN(d) ? iso : d.toLocaleDateString(DATE[l], { day: "numeric", month: "long", year: "numeric" });
  };

  function paint(live) {
    for (const l of ["en", "nl"]) {
      const ol = document.querySelector(`[data-ch="${l}"]`);
      ol.textContent = "";
      for (const e of CHANGELOG) {
        const isLive = e.version === live;
        const li = el("li", `ch__day${isLive ? " is-live" : ""}`);
        li.id = `v${e.version}`;
        const head = el("div", "ch__h");
        const time = el("time", "ch__date", day(e.date, l));
        time.dateTime = e.date;
        head.append(time, el("span", "ch__ver mono", `v${e.version}`));
        if (isLive) head.appendChild(el("span", "ch__live", LIVE[l]));
        const ul = el("ul", "ch__items");
        for (const line of e[l] || []) ul.appendChild(el("li", null, line));
        li.append(head, ul);
        ol.appendChild(li);
      }
    }
    for (const n of document.querySelectorAll(".js-live")) n.textContent = live ? `v${live}` : "—";
    if (location.hash) {
      const target = document.getElementById(location.hash.slice(1));
      if (target) target.scrollIntoView();
    }
  }

  const body = document.body.dataset;
  function show(l) {
    for (const n of document.querySelectorAll("[data-pv]")) n.hidden = n.getAttribute("data-pv") !== l;
    for (const b of document.querySelectorAll(".lang-switch [data-lang]")) b.setAttribute("aria-pressed", String(b.dataset.lang === l));
    document.documentElement.lang = l;
    document.title = l === "nl" ? body.titleNl : body.titleEn;
    const back = document.querySelector(".pv-bug");
    if (back) back.href = l === "nl" ? "./?lang=nl" : "./";
  }
  for (const b of document.querySelectorAll(".lang-switch [data-lang]")) {
    b.addEventListener("click", () => { setLang(b.dataset.lang); show(lang()); });
  }

  const newest = CHANGELOG[0] && CHANGELOG[0].version;
  paint(newest);
  show(lang());
  fetch("version.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .then((v) => { if (v && v.version && v.version !== newest) paint(v.version); })
    .catch(() => {});
})();
