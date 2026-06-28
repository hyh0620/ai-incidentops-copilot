import assert from "node:assert/strict";
import test from "node:test";

import { normalizeApiDate } from "../lib/format";

test("normalizeApiDate treats naive API datetime as UTC", () => {
  assert.equal(normalizeApiDate("2026-06-29 15:31:00"), "2026-06-29T15:31:00Z");
  assert.equal(normalizeApiDate("2026-06-29T15:31:00"), "2026-06-29T15:31:00Z");
});

test("normalizeApiDate keeps explicit timezone", () => {
  assert.equal(normalizeApiDate("2026-06-29T15:31:00Z"), "2026-06-29T15:31:00Z");
  assert.equal(normalizeApiDate("2026-06-29T15:31:00+00:00"), "2026-06-29T15:31:00+00:00");
});
