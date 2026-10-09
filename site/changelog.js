// changelog.html: the GitHub releases as a list, newest first. Versions are pyproject's,
// released by hand with a "Release x.y.z" bump PR and a GitHub release (see the README). The
// notes are markdown from this repo's own releases, but they are escaped first and only then
// formatted, with just what the notes use: headings, lists, bold, italics, code and links
// (http(s) or relative to the repo; anything else stays text). The notes stay English; in Dutch
// only the page around them is translated, and it says so.
"use strict";

const REPO = "Bmiest/bmiest_wowaudit_wishlist_updater";
const TAG_BASE = `https://github.com/${REPO}/releases/tag/`;

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function href(u) {
  u = u.replace(/&amp;/g, "&");
  if (/^https?:\/\//i.test(u)) return u;
  if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return null; // javascript:, data:, ...
  try { return new URL(u, TAG_BASE).href; } catch (e) { return null; }
}
function inline(s) {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, txt, u) => { const h = href(u); return h ? `<a href="${esc(h)}" rel="noopener">${txt}</a>` : txt; });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/(^|[\s(])#(\d+)\b/g, `$1<a href="https://github.com/${REPO}/pull/$2" rel="noopener">#$2</a>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
}
function md(src) {
  const out = [];
  let list = false, para = [];
  const flush = () => { if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; } };
  const close = () => { if (list) { out.push("</ul>"); list = false; } };
  esc(src).replace(/\r/g, "").split("\n").forEach((line) => {
    const hd = /^#{1,6}\s+(.*)$/.exec(line), li = /^\s*[-*]\s+(.*)$/.exec(line);
    if (hd) { flush(); close(); out.push(`<h3>${inline(hd[1])}</h3>`); }
    else if (li) { flush(); if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(li[1])}</li>`); }
    else if (!line.trim()) { flush(); close(); }
    else { close(); para.push(line.trim()); }
  });
  flush(); close();
  return out.join("\n");
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

document.addEventListener("DOMContentLoaded", () => {
  document.documentElement.lang = lang();
  document.querySelectorAll("[data-t]").forEach((n) => { n.textContent = t(n.getAttribute("data-t")); });
  const en = document.getElementById("clEn");
  if (t("clEn")) { en.textContent = t("clEn"); en.hidden = false; }
  const list = document.getElementById("clList");
  const day = (iso) => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" }); };
  fetch(`https://api.github.com/repos/${REPO}/releases?per_page=30`, { headers: { Accept: "application/vnd.github+json" } })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((rs) => {
      rs = rs.filter((r) => !r.draft);
      list.textContent = "";
      if (!rs.length) { list.appendChild(el("li", "cl__note", t("clNone"))); return; }
      rs.forEach((r, i) => {
        const li = el("li", `cl__rel${i === 0 ? " is-latest" : ""}`);
        li.id = r.tag_name;
        const head = el("div", "cl__head");
        const tag = el("a", "cl__tag", r.tag_name); tag.href = r.html_url; tag.rel = "noopener";
        const when = el("time", "cl__when", day(r.published_at)); when.dateTime = r.published_at;
        head.append(tag, when);
        if (i === 0) head.appendChild(el("span", "cl__badge", t("clLatest")));
        const body = el("div", "cl__body");
        body.innerHTML = md(r.body || "");
        li.append(head, body);
        list.appendChild(li);
      });
      if (location.hash) { const target = document.getElementById(location.hash.slice(1)); if (target) target.scrollIntoView(); }
    })
    .catch(() => {
      list.textContent = "";
      const li = el("li", "cl__note", `${t("clFail")} `);
      const a = el("a", null, t("clFailLink")); a.href = `https://github.com/${REPO}/releases`; a.rel = "noopener";
      li.append(a, ".");
      list.appendChild(li);
    });
});
