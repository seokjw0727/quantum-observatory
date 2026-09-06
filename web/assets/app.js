import { enhanceSelects } from "./selects.js";
import { setupNavigation, revealPage, closeDetail } from "./motion.js";
import {
  KINDS,
  PAPER_KINDS,
  esc,
  safeURL,
  dayKey,
  effectiveDate,
  selectRecords,
  dateLabel,
  weekLabel,
  toCSV,
  chartPoints,
} from "./core.js";

const app = document.querySelector("#app");
const dialog = document.querySelector("#detail-dialog");
const path = location.pathname.replace(/\/$/, "");
const page =
  {
    "/research": "research",
    "/archive": "archive",
    "/methodology": "methodology",
  }[path] || "overview";
let summary,
  records,
  sources,
  filters,
  pageNumber = 1;
const PAGE_SIZE = 20;
const number = new Intl.NumberFormat("en-US");
const params = new URLSearchParams(location.search);
const detailCache = new Map();
let activeDetail = null;

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document
    .querySelector("#theme-toggle")
    .setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
    );
}
try {
  setTheme(
    localStorage.getItem("qo-theme") ||
      (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light"),
  );
} catch {
  setTheme("light");
}
document.querySelector("#theme-toggle").addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(theme);
  try {
    localStorage.setItem("qo-theme", theme);
  } catch {}
});
document
  .querySelector(`[data-page="${page}"]`)
  ?.setAttribute("aria-current", "page");

setupNavigation();

function selectedWeek() {
  return (
    summary.weeks.find((w) => w.id === filters.week) || summary.weeks.at(-2)
  );
}
function sourceName(id) {
  return sources.find((s) => s.id === id)?.name || id;
}
function topicName(id) {
  return summary.topics[id]?.short || id;
}
function statusLabel(value) {
  return (
    {
      success: "Available",
      failed: "Unavailable",
      not_configured: "Not configured",
      disabled: "Disabled",
      partial: "Partial",
      backfilled: "Backfilled",
      in_progress: "In progress",
      incomplete: "Incomplete",
    }[value] || value
  );
}
function weekOptions(includeAll = false) {
  return (
    (includeAll ? '<option value="all">All collected dates</option>' : "") +
    [...summary.weeks]
      .reverse()
      .map(
        (w) =>
          `<option value="${w.id}" ${filters.week === w.id ? "selected" : ""}>${weekLabel(w.id)}${w.status === "in_progress" ? " · In progress" : ""}</option>`,
      )
      .join("")
  );
}
function pageHeading(title, description, withWeek = false) {
  return `<div class="page-heading"><div><span class="eyebrow">QUANTUM COMPUTING & INFORMATION</span><h1>${title}</h1><p>${description}</p></div>${withWeek ? `<div class="date-control"><label for="week-select">Reporting period · Korea Standard Time</label><select id="week-select" class="select">${weekOptions(page === "research")}</select></div>` : ""}</div>`;
}
function freshness() {
  const age = (Date.now() - Date.parse(summary.generated_at)) / 86400000;
  const material = sources.filter((s) => s.enabled && s.kind !== "enrichment");
  const available = material.filter((s) => s.status === "success").length;
  return `<div class="status-line"><span><span class="status-mark"></span>${age > 8 ? "Update overdue · " : ""}Last collected ${dateLabel(summary.generated_at, { year: "numeric" })}<span class="sr-only">, ${esc(summary.generated_at)}</span></span><span>${available} of ${material.length} collection sources available · <a href="/methodology/">View coverage</a></span></div>`;
}
function stat(label, value, note) {
  return `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${number.format(value)}</div><div class="stat-note">${note}</div></div>`;
}
function chart() {
  const weeks = summary.weeks
    .filter((w) => w.id <= selectedWeek().id)
    .slice(-12);
  const points = chartPoints(weeks);
  const pointsString = points.map((p) => `${p.x},${p.y}`).join(" ");
  const max = Math.max(1, ...weeks.map((w) => w.research));
  return `<section class="panel"><div class="panel-heading"><div><h2>Research activity</h2><p>First public appearance · up to 12 weeks</p></div><span class="legend">Unique research</span></div><svg class="trend" viewBox="0 0 720 190" role="img" aria-label="Weekly unique research counts. Exact values are available in the table below.">${[0, 0.5, 1].map((r) => `<line class="gridline" x1="36" x2="700" y1="${158 - r * 134}" y2="${158 - r * 134}"/><text x="26" y="${162 - r * 134}" text-anchor="end">${Math.round(max * r)}</text>`).join("")}${points.length ? `<polygon class="area" points="${points[0].x},158 ${pointsString} ${points.at(-1).x},158"/><polyline class="line" points="${pointsString}"/>` : ""}${points.map((p, i) => `<circle class="point ${p.week.id === filters.week ? "selected" : ""}" cx="${p.x}" cy="${p.y}" r="${p.week.id === filters.week ? 4 : 2.7}"><title>${weekLabel(p.week.id)}: ${p.week.research} research works · ${statusLabel(p.week.status)}</title></circle>${i % 3 === 0 || i === points.length - 1 ? `<text x="${p.x}" y="184" text-anchor="middle">${dateLabel(p.week.id)}</text>` : ""}`).join("")}</svg><p class="chart-note">Retrospective publication counts. Current and incomplete periods are provisional.</p><details class="chart-table"><summary>View chart data</summary><div class="table-wrap"><table><thead><tr><th>Week beginning</th><th>Research</th><th>Coverage</th></tr></thead><tbody>${weeks.map((w) => `<tr><td><a href="/?week=${w.id}">${dateLabel(w.id, { year: "numeric" })}</a></td><td>${w.research}</td><td>${statusLabel(w.status)}</td></tr>`).join("")}</tbody></table></div></details></section>`;
}
function topicsPanel() {
  const w = selectedWeek();
  const topics = Object.entries(w.topics).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...topics.map((x) => x[1]));
  return `<section class="panel"><div class="panel-heading"><div><h2>Across the field</h2><p>Research by topic · selected week</p></div></div><div class="topic-bars">${topics.map(([id, count]) => `<div class="topic-row"><a class="topic-name text-link" href="/research/?week=${w.id}&topic=${id}" title="${esc(summary.topics[id].label)}">${esc(topicName(id))}</a><div class="topic-track" aria-hidden="true"><div class="topic-fill" style="width:${(count / max) * 100}%;background:${summary.topics[id].color}"></div></div><span class="topic-value">${number.format(count)}</span></div>`).join("")}</div><p class="chart-note">Topics overlap. A research work can belong to more than one field.</p></section>`;
}
function researchToolbar() {
  return `<div class="toolbar"><div class="search-wrap"><span class="search-icon" aria-hidden="true">⌕</span><label class="sr-only" for="search">Search titles, authors, DOI, or arXiv ID</label><input type="search" id="search" placeholder="Search titles, authors, or identifiers…" value="${esc(filters.query)}" autocomplete="off"></div><label class="sr-only" for="topic-filter">Topic</label><select id="topic-filter" class="select"><option value="">All topics</option>${Object.entries(
    summary.topics,
  )
    .map(
      ([id, t]) =>
        `<option value="${id}" ${filters.topic === id ? "selected" : ""}>${esc(t.short)}</option>`,
    )
    .join(
      "",
    )}</select><label class="sr-only" for="kind-filter">Material type</label><select id="kind-filter" class="select"><option value="">All materials</option><option value="papers" ${filters.kind === "papers" ? "selected" : ""}>Research papers</option>${Object.entries(
    KINDS,
  )
    .map(
      ([id, label]) =>
        `<option value="${id}" ${filters.kind === id ? "selected" : ""}>${label}</option>`,
    )
    .join("")}</select>${
    page === "research"
      ? `<label class="sr-only" for="source-filter">Source</label><select id="source-filter" class="select"><option value="">All sources</option>${sources
          .filter((s) => s.kind !== "enrichment")
          .map(
            (s) =>
              `<option value="${s.id}" ${filters.source === s.id ? "selected" : ""}>${esc(s.name)}</option>`,
          )
          .join(
            "",
          )}</select><label class="sr-only" for="basis-filter">Date basis</label><select id="basis-filter" class="select"><option value="published" ${filters.dateBasis === "published" ? "selected" : ""}>First public / event</option><option value="discovered" ${filters.dateBasis === "discovered" ? "selected" : ""}>First collected</option></select>`
      : ""
  }</div>`;
}
function listShell() {
  return `<section aria-labelledby="research-heading"><div class="section-heading"><div><h2 id="research-heading">${page === "overview" ? "This week’s reading" : "Research library"}</h2><p>${page === "overview" ? "Papers, conference contributions, and reports." : "Search the collected corpus. Related publication versions are grouped."}</p></div>${page === "overview" ? `<a class="text-link" href="/research/?week=${filters.week}">Explore all research ↗</a>` : ""}</div><div class="research-panel">${researchToolbar()}<div id="results"></div></div></section>`;
}
function currentResults() {
  const w = selectedWeek();
  return selectRecords(records, {
    ...filters,
    start: filters.week === "all" ? null : w.id,
    end: filters.week === "all" ? null : w.end,
  });
}
function item(r) {
  const d = effectiveDate(r);
  const authors =
    r.authors.slice(0, 4).join(", ") +
    (r.authors.length > 4 ? ` +${r.authors.length - 4} authors` : "");
  return `<li class="research-item"><div class="item-date">${d ? dateLabel(d) : "Undated"}<span>${d ? dayKey(d).slice(0, 4) : "Source date missing"}</span></div><div class="item-body"><div class="item-heading"><span class="kind-badge">${KINDS[r.kind]}${r.presentation_status === "accepted" ? " · Accepted" : ""}</span><span class="item-source">${esc(r.venue || sourceName(r.source))}${r.linked_record_ids.length > 1 ? " · Linked versions" : ""}</span></div><h3><button class="item-title" data-detail="${r.id}">${esc(r.title)}</button></h3><p class="item-authors">${esc(authors || "Author metadata unavailable")}</p><div class="item-tags">${r.topics
    .slice(0, 4)
    .map((t) => `<span class="tag">${esc(topicName(t))}</span>`)
    .join(
      "",
    )}${r.topics.length > 4 ? `<span class="tag">+${r.topics.length - 4}</span>` : ""}</div></div><a class="item-open" href="${esc(safeURL(r.url))}" target="_blank" rel="noopener noreferrer" aria-label="Open original: ${esc(r.title)}">↗</a></li>`;
}
function renderResults() {
  const selected = currentResults();
  const pages = Math.max(1, Math.ceil(selected.length / PAGE_SIZE));
  pageNumber = Math.min(pageNumber, pages);
  const visible = selected.slice(
    (pageNumber - 1) * PAGE_SIZE,
    pageNumber * PAGE_SIZE,
  );
  document.querySelector("#results").innerHTML =
    `<div class="result-meta"><span role="status" aria-live="polite">${number.format(selected.length)} results · publication versions grouped</span><button class="button" id="export-csv" ${selected.length ? "" : "disabled"}>Export CSV ↓</button></div>${visible.length ? `<ol class="research-list">${visible.map(item).join("")}</ol>` : `<div class="empty-state"><h3>No matching research</h3><p>${filters.week === "all" ? "Try a different topic, material type, or search term." : "No collected materials match this period and your filters. Missing source coverage is not evidence of no research."}</p><button class="button" id="reset-filters">Reset filters</button> <a href="/research/?week=all" class="text-link">Browse all dates</a></div>`}<div class="pagination"><span>${selected.length ? `${(pageNumber - 1) * PAGE_SIZE + 1}–${Math.min(pageNumber * PAGE_SIZE, selected.length)} of ${number.format(selected.length)}` : "0 results"}</span><div class="pagination-controls"><button class="button" id="prev-page" ${pageNumber <= 1 ? "disabled" : ""}>← Previous</button><button class="button" id="next-page" ${pageNumber >= pages ? "disabled" : ""}>Next →</button></div></div>`;
  document
    .querySelectorAll("[data-detail]")
    .forEach((el) =>
      el.addEventListener("click", () => openDetail(el.dataset.detail)),
    );
  document.querySelector("#prev-page").onclick = () => {
    pageNumber--;
    renderResults();
    document
      .querySelector("#research-heading")
      .scrollIntoView({ block: "start" });
  };
  document.querySelector("#next-page").onclick = () => {
    pageNumber++;
    renderResults();
    document
      .querySelector("#research-heading")
      .scrollIntoView({ block: "start" });
  };
  document.querySelector("#reset-filters")?.addEventListener("click", () => {
    filters = { ...filters, query: "", topic: "", kind: "", source: "" };
    pageNumber = 1;
    updateURL();
    renderPage();
  });
  document.querySelector("#export-csv").onclick = () => {
    const blob = new Blob(["\uFEFF" + toCSV(selected)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quantum-research-${filters.week}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
}
function updateURL() {
  const p = new URLSearchParams();
  for (const key of ["week", "query", "topic", "kind", "source", "dateBasis"])
    if (filters[key] && !(key === "dateBasis" && filters[key] === "published"))
      p.set(key, filters[key]);
  history.replaceState(null, "", location.pathname + "?" + p);
}
function bindFilters() {
  document.querySelector("#week-select")?.addEventListener("change", (e) => {
    filters.week = e.target.value;
    pageNumber = 1;
    updateURL();
    renderPage();
  });
  for (const [id, key] of [
    ["topic-filter", "topic"],
    ["kind-filter", "kind"],
    ["source-filter", "source"],
    ["basis-filter", "dateBasis"],
  ])
    document.getElementById(id)?.addEventListener("change", (e) => {
      filters[key] = e.target.value;
      pageNumber = 1;
      updateURL();
      renderResults();
    });
  let timer;
  document.querySelector("#search")?.addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      filters.query = e.target.value;
      pageNumber = 1;
      updateURL();
      renderResults();
    }, 160);
  });
}
function overview() {
  const w = selectedWeek();
  const growth =
    w.change_pct === null
      ? "Comparison unavailable"
      : `${w.change_pct >= 0 ? "+" : ""}${w.change_pct.toFixed(1)}% versus previous week`;
  return (
    pageHeading(
      "Research overview",
      "A weekly view of the work moving quantum research forward.",
      true,
    ) +
    freshness() +
    `<section class="stats" aria-label="Weekly statistics">${stat("New research", w.research, growth)}${stat("Conference talks", w.talks, "Accepted contributions · event week")}${stat("Reports", w.reports, "Known publication dates only")}${stat("Active topics", Object.values(w.topics).filter((x) => x > 0).length, "Across eight research areas")}</section><div class="analytics">${chart()}${topicsPanel()}</div>${
      w.rising.length
        ? `<div class="section-heading"><div class="rising"><strong>Gaining share</strong>${w.rising
            .slice(0, 3)
            .map(
              (r) =>
                `<span>${esc(topicName(r.topic))} +${r.change_pp.toFixed(1)} pp</span>`,
            )
            .join(
              "",
            )}<span class="chart-note">vs. previous four weeks</span></div></div>`
        : ""
    }${w.status === "in_progress" ? '<p class="notice quiet-notice">This week is still in progress. Counts are provisional; growth comparisons are withheld.</p>' : ""}${listShell()}`
  );
}
function archive() {
  return (
    pageHeading(
      "Weekly archive",
      "Return to a reporting period and explore its research.",
    ) +
    freshness() +
    `<p class="chart-note" style="margin:20px 0">Historical weeks are recalculated as late-indexed publications and linked versions are discovered.</p><div class="archive-grid">${[
      ...summary.weeks,
    ]
      .reverse()
      .map(
        (w) =>
          `<a class="archive-card" href="/?week=${w.id}"><span class="small-label">${statusLabel(w.status)}</span><h2>${weekLabel(w.id)}</h2><div class="archive-count">${number.format(w.research)}<span>research works</span></div><p>${w.talks} conference talks · ${w.reports} reports</p></a>`,
      )
      .join("")}</div>`
  );
}
function methodology() {
  return (
    pageHeading(
      "Sources & methodology",
      "Understand what is collected, how it is counted, and where coverage ends.",
    ) +
    freshness() +
    `<div class="method-grid" style="margin-top:32px"><article class="prose"><h2>A defined view of research</h2><p>This observatory follows quantum computing and quantum information through selected public sources. Counts describe this collected corpus, not all research worldwide. There are currently ${number.format(summary.totals.records)} source records, grouped into ${number.format(summary.totals.research)} research works, plus ${number.format(summary.totals.talks)} conference contributions and ${number.format(summary.totals.reports)} reports.</p><h2>What counts as new?</h2><p>Research is assigned to the week of its earliest known public appearance. An arXiv revision does not become a new paper. A journal publication with an explicit DOI or arXiv link is grouped with its preprint. Similar titles alone are never enough to merge records.</p><p>Publication dates and collection dates are distinct. Use “First collected” in the Research view to find late-indexed or newly discovered materials. Date-only metadata retains the publisher’s calendar date; timestamps are converted to Korea Standard Time.</p><h2>Weekly periods and comparisons</h2><p>A week runs from Monday 00:00 to the next Monday 00:00 in Korea Standard Time. Collection is scheduled for Monday 09:17 KST. Historical activity is reconstructed from publication metadata. Comparisons require complete, matching research-source coverage. Current and incomplete weeks do not receive growth percentages.</p><p>Topic share is the number of research works carrying a tag divided by all research works that week. Rising topics compare that share with the previous four weeks and require at least five works in the selected week. Multi-topic percentages can total more than 100%.</p><h2>Conference contributions and reports</h2><p>QIP entries are accepted contributions from the official conference list, not independently verified recordings of delivered talks. The conference date range is retained; an individual presentation date is not invented. Conference editions are configured explicitly and must be updated for a new year.</p><p>Report publication dates are used only when explicitly available. A file’s upload directory is not treated as its publication date. ${number.format(summary.totals.undated)} records currently have no precise publication or event date and are available under “All collected dates.” DOE OSTI discovers technical reports through its official API. GAO monitoring covers a configured report page; the NQI adapter discovers report links from its publication index when accessible.</p><h2>Classification and source limits</h2><p>Eight transparent topic dictionaries match titles and available arXiv abstracts. These are rule-based tags, not an assessment of scientific quality. Untagged physics and journal results are excluded; official conference and report records remain discoverable even if unclassified.</p><p>Crossref currently covers PRX Quantum, Quantum, and npj Quantum Information. Citation metadata is supplementary and carries a retrieval date. Publisher abstracts and PDFs are not mirrored. arXiv abstracts are displayed with attribution and a source link.</p><h2>Updates and reproducibility</h2><p>Successful source checkpoints, record identifiers, classification rules, collection manifests, and content hashes are stored with the data. A 14-day overlap catches many indexing delays; early-month runs revisit at least 12 weeks. Longer delays can still be missed. Required-source failure blocks publication; optional-source failures are visible here.</p><p>Scheduled jobs can be delayed or disabled by the hosting service. The last successful collection remains visible, and the website marks an update overdue after eight days.</p><p><a href="/data/summary.json">Download statistics JSON</a> · <a href="/data/manifest.json">View collection manifest</a></p></article><aside><section class="panel"><div class="panel-heading"><div><h2>Source coverage</h2><p>Latest collection attempt</p></div></div><ul class="source-list">${sources.map((s) => `<li><div class="source-head"><a href="${esc(safeURL(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a><span class="source-status ${esc(s.status)}">${statusLabel(s.status)}</span></div><p>${esc(s.description || s.note || s.message || "")}</p><div class="source-stats">${s.last_success ? `Last success ${dateLabel(s.last_success, { year: "numeric" })}` : "No successful automated collection"}${s.included !== undefined ? ` · ${number.format(s.included)} included this run` : ""}</div></li>`).join("")}</ul></section><p class="chart-note" style="margin-top:16px">A failed source is missing coverage, not a zero-research result.</p></aside></div>`
  );
}
function renderPage() {
  if (page === "overview") app.innerHTML = overview();
  else if (page === "research")
    app.innerHTML =
      pageHeading(
        "Explore research",
        "Find a paper. Follow a topic. Trace an idea to its source.",
        true,
      ) +
      freshness() +
      `<div style="margin-top:30px">${listShell()}</div>`;
  else if (page === "archive") app.innerHTML = archive();
  else app.innerHTML = methodology();
  revealPage(app);
  app.setAttribute("aria-busy", "false");
  document.title =
    {
      overview: "Overview",
      research: "Research",
      archive: "Weekly archive",
      methodology: "Methodology",
    }[page] + " · Quantum Observatory";
  if (page === "overview" || page === "research") {
    if (filters.week === "all" && document.querySelector("#week-select"))
      document.querySelector("#week-select").value = "all";
    renderResults();
    bindFilters();
    enhanceSelects(app);
  }
}
async function openDetail(id) {
  const index = records.find((r) => r.id === id);
  if (!index) return;
  activeDetail = id;
  document.querySelector("#detail-content").innerHTML =
    `<div class="detail-top"><span class="small-label">Research detail</span><button class="icon-button" id="close-detail" aria-label="Close research detail">×</button></div><div class="detail-inner"><h2 id="detail-title">${esc(index.title)}</h2><p role="status">Loading source metadata…</p></div>`;
  document.querySelector("#close-detail").onclick = () => closeDetail(dialog);
  if (!dialog.open) dialog.showModal();
  try {
    if (!detailCache.has(index.detail_shard)) {
      const res = await fetch(index.detail_shard);
      if (!res.ok) throw Error("Request failed");
      detailCache.set(index.detail_shard, await res.json());
    }
    if (activeDetail !== id || !dialog.open) return;
    const r = detailCache.get(index.detail_shard)[id];
    if (!r) throw Error("Missing detail");
    const linked = records.filter((x) => r.linked_record_ids.includes(x.id));
    document.querySelector("#detail-content").innerHTML =
      `<div class="detail-top"><span class="small-label">${KINDS[r.kind]}${r.presentation_status === "accepted" ? " · Accepted contribution" : ""}</span><button class="icon-button" id="close-detail" aria-label="Close research detail">×</button></div><div class="detail-inner"><span class="item-source">${esc(r.venue || sourceName(r.source))}</span><h2 id="detail-title">${esc(r.title)}</h2><p class="authors">${esc(r.authors.join(", ") || "Author metadata unavailable")}</p><div class="item-tags">${r.topics.map((t) => `<span class="tag">${esc(summary.topics[t]?.label || t)}</span>`).join("")}</div><dl class="detail-meta"><div><dt>${r.kind === "talk" ? "Conference dates" : "First public appearance"}</dt><dd>${r.kind === "talk" ? `${dateLabel(r.date, { year: "numeric" })} – ${dateLabel(r.event_end, { year: "numeric" })}` : dateLabel(effectiveDate(r), { year: "numeric" })}</dd></div><div><dt>Collected</dt><dd>${dateLabel(r.observed_at, { year: "numeric" })}</dd></div><div><dt>Identifier</dt><dd>${esc(r.doi || r.arxiv_id || sourceName(r.source))}</dd></div><div><dt>Source</dt><dd>${esc(sourceName(r.source))}${r.version ? ` · v${r.version}` : ""}</dd></div></dl><h3>${r.abstract ? "Abstract" : "Source material"}</h3><p class="abstract">${r.abstract ? esc(r.abstract) : "An abstract is not available in this snapshot. Follow the original source for the full material."}</p>${linked.length > 1 ? `<h3 style="margin-top:26px">Linked records</h3><ul class="linked-list">${linked.map((x) => `<li><a href="${esc(safeURL(x.url))}" target="_blank" rel="noopener noreferrer">${esc(KINDS[x.kind])} · ${esc(x.venue || sourceName(x.source))}</a></li>`).join("")}</ul>` : ""}<div class="detail-links"><a class="button primary" href="${esc(safeURL(r.url))}" target="_blank" rel="noopener noreferrer">Read original ↗</a>${r.arxiv_id ? `<a class="button" href="https://arxiv.org/pdf/${encodeURIComponent(r.arxiv_id)}" target="_blank" rel="noopener noreferrer">Open PDF ↗</a>` : ""}</div><p class="detail-footnote">Metadata from ${esc(sourceName(r.source))}. ${r.citations != null ? `${number.format(r.citations)} indexed citations as of ${dateLabel(r.citations_as_of, { year: "numeric" })}. ` : ""}Topic tags are assigned by transparent rules. ${r.presentation_status === "accepted" ? "Acceptance and the conference date range do not verify an individual talk was delivered." : ""}</p></div>`;
    document.querySelector("#close-detail").onclick = () => closeDetail(dialog);
    document.querySelector("#close-detail").focus();
  } catch {
    if (activeDetail === id)
      document.querySelector("#detail-content .detail-inner").innerHTML =
        `<h2 id="detail-title">${esc(index.title)}</h2><p>Detailed metadata could not be loaded.</p><p style="margin-top:20px"><a href="${esc(safeURL(index.url))}" target="_blank" rel="noopener noreferrer">Read original ↗</a></p>`;
  }
}
dialog.addEventListener("click", (e) => {
  if (e.target === dialog && e.clientX < dialog.getBoundingClientRect().left)
    closeDetail(dialog);
});
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeDetail(dialog);
});

dialog.addEventListener("close", () => {
  activeDetail = null;
});
document.addEventListener("keydown", (e) => {
  if (
    e.key === "/" &&
    !dialog.open &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
  ) {
    const search = document.querySelector("#search");
    if (search) {
      e.preventDefault();
      search.focus();
    }
  }
});
async function load() {
  try {
    const [s, r, m] = await Promise.all(
      ["/data/summary.json", "/data/index.json", "/data/manifest.json"].map(
        async (url) => {
          const response = await fetch(url);
          if (!response.ok) throw Error("Snapshot unavailable");
          return response.json();
        },
      ),
    );
    summary = s;
    records = r.records;
    sources = m.sources;
    if (r.run_id !== s.run_id || m.run_id !== s.run_id || r.build_id !== s.build_id || m.build_id !== s.build_id)
      throw Error("Snapshot versions do not match");
    filters = {
      week:
        params.get("week") ||
        (page === "research" ? "all" : summary.last_complete_week),
      query: params.get("query") || "",
      topic: params.get("topic") || "",
      kind: params.get("kind") || "",
      source: params.get("source") || "",
      dateBasis:
        params.get("dateBasis") === "discovered" ? "discovered" : "published",
    };
    if (
      !summary.weeks.some((w) => w.id === filters.week) &&
      !(filters.week === "all" && page === "research")
    )
      filters.week = summary.last_complete_week;
    renderPage();
  } catch {
    app.setAttribute("aria-busy", "false");
    app.innerHTML =
      pageHeading(
        "Research is temporarily unavailable",
        "The published snapshot could not be loaded.",
      ) +
      '<div class="notice"><p>Please reload the page. If the issue persists, the last deployment may need to be restored.</p><button class="button" id="retry" style="margin-top:16px">Try again</button></div>';
    document.querySelector("#retry").onclick = load;
  }
}
load();
