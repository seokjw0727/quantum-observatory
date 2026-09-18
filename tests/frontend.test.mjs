import test from "node:test";
import assert from "node:assert/strict";
import {
  selectRecords,
  dayKey,
  esc,
  safeURL,
  toCSV,
  chartPoints,
  normalizeSort,
} from "../web/assets/core.js";
const a = {
  id: "a",
  work_id: "one",
  title: "Quantum error correction",
  authors: ["Alice"],
  abstract: "Logical qubits",
  kind: "preprint",
  source: "arxiv",
  topics: ["error-correction"],
  first_published: "2026-09-01T00:00:00Z",
  date: "2026-09-01",
  url: "https://arxiv.org/abs/2609.00001",
};
const b = { ...a, id: "b", source: "crossref", kind: "journal_article" };
test("linked versions count once; filters apply before grouping", () => {
  assert.equal(selectRecords([a, b]).length, 1);
  assert.equal(selectRecords([a, b], { source: "crossref" })[0].id, "b");
  assert.equal(selectRecords([a, b], { query: "Alice correction" }).length, 1);
  assert.equal(selectRecords([a, b], { topic: "hardware" }).length, 0);
});
test("exclusive week end and Korea timezone agree", () => {
  assert.equal(dayKey("2026-09-06T15:00:00Z"), "2026-09-07");
  assert.equal(
    selectRecords([a], { start: "2026-08-25", end: "2026-09-01" }).length,
    0,
  );
});
test("HTML and unsafe original URLs are neutralized", () => {
  assert.equal(esc('<img onerror="x">'), "&lt;img onerror=&quot;x&quot;&gt;");
  assert.equal(safeURL("javascript:alert(1)"), "#");
  assert.equal(safeURL("https://good.example/x"), "https://good.example/x");
});
test("CSV protects spreadsheet formula injection and quotes", () => {
  const csv = toCSV([{ ...a, title: "=SUM(1,2)" }]);
  assert.ok(csv.includes('"\'=SUM(1,2)"'));
});
test("undated reports stay in all dates, not a dated period", () => {
  const r = {
    ...a,
    id: "r",
    kind: "report",
    date: null,
    first_published: null,
  };
  assert.equal(selectRecords([r]).length, 1);
  assert.equal(
    selectRecords([r], { start: "2026-08-31", end: "2026-09-07" }).length,
    0,
  );
});
test("zero series produces finite chart coordinates", () => {
  assert.ok(
    chartPoints([{ research: 0 }, { research: 0 }]).every(
      (p) => Number.isFinite(p.x) && Number.isFinite(p.y),
    ),
  );
});
test("citation order distinguishes unknown from zero and sorts the entire corpus", () => {
  const rows = Array.from({ length: 45 }, (_, i) => ({ ...a, id: `paper-${i}`, work_id: `work-${i}`, citations: i, publication_year: 2026 }));
  rows.push({ ...a, id: "unknown", work_id: "unknown", citations: null });
  const sorted = selectRecords(rows, { sort: "citations" });
  assert.equal(sorted[0].citations, 44);
  assert.equal(sorted.slice(20, 40)[0].citations, 24);
  assert.equal(sorted.at(-2).citations, 0);
  assert.equal(sorted.at(-1).id, "unknown");
});
test("oldest order and year filter retain partial years without fabricating a day", () => {
  const partial = { ...a, id: "partial", work_id: "partial", first_published: null, publication_year: 2024 };
  const undated = { ...partial, id: "undated", work_id: "undated", publication_year: null };
  assert.deepEqual(selectRecords([a, partial, undated], { sort: "oldest" }).map((r) => r.id), ["partial", "a", "undated"]);
  assert.equal(selectRecords([a, partial], { year: "2024" })[0].id, "partial");
});
test("ties are deterministic and CSV preserves citation provenance and missing values", () => {
  const first = { ...a, id: "first", work_id: "first", citations: 0, citations_source: "Crossref", citations_as_of: "2026-09-07" };
  const second = { ...first, id: "second", work_id: "second" };
  assert.deepEqual(selectRecords([second, first], { sort: "citations" }).map((r) => r.id), ["first", "second"]);
  assert.equal(selectRecords([a, b], { sort: "citations" }).length, 1);
  const csv = toCSV([first, { ...a, citations: null }]);
  assert.ok(csv.includes('"0","Crossref","2026-09-07"'));
  assert.ok(csv.includes('"2026","","",""'));
  assert.equal(normalizeSort("cite"), "citations");
  assert.equal(normalizeSort("bad"), "latest");
});
