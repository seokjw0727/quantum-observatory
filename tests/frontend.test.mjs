import test from "node:test";
import assert from "node:assert/strict";
import {
  selectRecords,
  dayKey,
  esc,
  safeURL,
  toCSV,
  chartPoints,
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
