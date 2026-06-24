import assert from "node:assert/strict";
import test from "node:test";

import { buildPersonaHeaders, DEMO_PERSONA_COOKIE, personaIdFromCookie, normalizeDemoPersonaId } from "../lib/persona";

test("personaIdFromCookie reads persisted demo persona", () => {
  assert.equal(personaIdFromCookie(`foo=bar; ${DEMO_PERSONA_COOKIE}=2`), "2");
});

test("invalid persona falls back to Requester A", () => {
  assert.equal(normalizeDemoPersonaId("999"), "1");
});

test("buildPersonaHeaders injects X-Demo-User-Id", () => {
  const headers = buildPersonaHeaders({ Accept: "application/json" }, "7");
  assert.equal(headers.get("X-Demo-User-Id"), "7");
  assert.equal(headers.get("Accept"), "application/json");
});
