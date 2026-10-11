import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const read = (path) => fs.readFileSync(path, "utf8");

test("source chips cover complete, partial, cached, demo, and failed-source states", () => {
  const source = read("src/components/DataStatusChips.tsx");
  for (const state of ["Live data", "Cached data", "Demo data", "Partial data", 'status === "failed"']) {
    assert.match(source, new RegExp(state));
  }
  assert.match(source, /confidence\?\.partial/);
});

test("crop detail leads with deterministic guidance and tolerates missing optional guidance", () => {
  const detail = read("src/app/crops/[id]/CropDetailClient.tsx");
  assert.ok(detail.indexOf("<DecisionSnapshot") < detail.indexOf("<AiReport"));
  const snapshot = read("src/components/DecisionSnapshot.tsx");
  for (const field of ["action_plan?.first_test", "risk_notes?.[0]", "water_plan", "scale?.fit"]) {
    assert.match(snapshot, new RegExp(field.replace(/[.?[\]]/g, "\\$&")));
  }
});

test("top cards explain rank before an optional AI report can load", () => {
  const card = read("src/components/CropCard.tsx");
  for (const field of ["Why this crop", "Main consideration", "First action", "View growing plan", "rank <= 3", "<details"]) {
    assert.match(card, new RegExp(field.replace(/[.?[\]]/g, "\\$&")));
  }
  const report = read("src/components/AiReport.tsx");
  assert.doesNotMatch(report, /createPortal|verdictSlot/);
});

test("detailed provenance stays available behind disclosure", () => {
  const source = read("src/components/LandSummary.tsx");
  assert.match(source, /aria-expanded=\{expanded\}/);
  assert.match(source, /aria-controls=\{detailsId\}/);
  assert.match(source, /View source details/);
  for (const field of ["data_period", "geographic_level", "limitations"]) assert.match(source, new RegExp(field));
});
