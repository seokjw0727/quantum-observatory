export const KINDS = {
  preprint: "Preprint",
  journal_article: "Journal article",
  conference_paper: "Conference paper",
  talk: "Conference talk",
  report: "Report",
};
export const PAPER_KINDS = new Set([
  "preprint",
  "journal_article",
  "conference_paper",
]);
const kstDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const dateKeyCache = new Map();
export function safeURL(value) {
  try {
    const u = new URL(value);
    return ["https:", "http:"].includes(u.protocol) && !u.username
      ? u.href
      : "#";
  } catch {
    return "#";
  }
}
export function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
export function dayKey(value) {
  if (!value) return "";
  if (!value.includes("T")) return value;
  if (dateKeyCache.has(value)) return dateKeyCache.get(value);
  const parts = kstDateFormatter.formatToParts(new Date(value));
  const result = ["year", "month", "day"]
    .map((t) => parts.find((p) => p.type === t).value)
    .join("-");
  dateKeyCache.set(value, result);
  return result;
}
export function effectiveDate(record) {
  return PAPER_KINDS.has(record.kind) ? record.first_published : record.date;
}
export function matches(record, filters = {}) {
  if (filters.topic && !(record.topics || []).includes(filters.topic))
    return false;
  if (filters.kind === "papers" && !PAPER_KINDS.has(record.kind)) return false;
  if (filters.kind && filters.kind !== "papers" && record.kind !== filters.kind)
    return false;
  if (filters.source && record.source !== filters.source) return false;
  const date = dayKey(
    filters.dateBasis === "discovered"
      ? record.observed_at
      : effectiveDate(record),
  );
  if (filters.start && (!date || date < filters.start)) return false;
  if (filters.end && (!date || date >= filters.end)) return false;
  const text = [
    record.title,
    ...record.authors,
    record.abstract || "",
    record.doi || "",
    record.arxiv_id || "",
  ]
    .join(" ")
    .toLowerCase();
  return (filters.query || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((q) => text.includes(q));
}
export function selectRecords(records, filters = {}) {
  const groups = new Map();
  for (const r of records.filter((r) => matches(r, filters))) {
    const key = PAPER_KINDS.has(r.kind) ? r.work_id : r.id;
    if (!groups.has(key)) groups.set(key, { ...r, matchedIds: [r.id] });
    else {
      const old = groups.get(key);
      old.matchedIds.push(r.id);
      if (!old.abstract && r.abstract) old.abstract = r.abstract;
    }
  }
  return [...groups.values()].sort((a, b) =>
    filters.sort === "title"
      ? a.title.localeCompare(b.title)
      : (dayKey(effectiveDate(b)) || "").localeCompare(
          dayKey(effectiveDate(a)) || "",
        ) || a.title.localeCompare(b.title),
  );
}
export function dateLabel(value, options = {}) {
  if (!value) return "Date unavailable";
  const key = dayKey(value);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    ...options,
    timeZone: "UTC",
  }).format(new Date(key + "T12:00:00Z"));
}
export function weekLabel(start) {
  const end = new Date(start + "T12:00:00Z");
  end.setUTCDate(end.getUTCDate() + 6);
  return `${dateLabel(start)} – ${dateLabel(end.toISOString().slice(0, 10), { year: "numeric" })}`;
}
export function csvCell(value) {
  let text = String(value ?? "");
  if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function toCSV(records) {
  return [
    [
      "Title",
      "Authors",
      "Type",
      "First public / event date",
      "Source",
      "Topics",
      "URL",
    ],
    ...records.map((r) => [
      r.title,
      r.authors.join("; "),
      KINDS[r.kind],
      dayKey(effectiveDate(r)),
      r.source,
      r.topics.join("; "),
      r.url,
    ]),
  ]
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n");
}
export function chartPoints(weeks, width = 720, height = 180) {
  const max = Math.max(1, ...weeks.map((w) => w.research));
  return weeks.map((w, i) => ({
    x: 36 + (i * (width - 56)) / Math.max(1, weeks.length - 1),
    y: height - 22 - (w.research / max) * (height - 46),
    week: w,
  }));
}
