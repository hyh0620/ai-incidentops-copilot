import assert from "node:assert/strict";
import test from "node:test";

import { normalizeApiDate, reviewReasonDisplay, reviewReasonText } from "../lib/format";

test("normalizeApiDate treats naive API datetime as UTC", () => {
  assert.equal(normalizeApiDate("2026-06-29 15:31:00"), "2026-06-29T15:31:00Z");
  assert.equal(normalizeApiDate("2026-06-29T15:31:00"), "2026-06-29T15:31:00Z");
});

test("normalizeApiDate keeps explicit timezone", () => {
  assert.equal(normalizeApiDate("2026-06-29T15:31:00Z"), "2026-06-29T15:31:00Z");
  assert.equal(normalizeApiDate("2026-06-29T15:31:00+00:00"), "2026-06-29T15:31:00+00:00");
});

test("reviewReasonDisplay presents Chinese business wording", () => {
  assert.deepEqual(reviewReasonDisplay("insufficient_retrieval_evidence"), {
    title: "检索证据不足",
    description: "未找到足够强的知识库依据，需人工确认。"
  });
  assert.deepEqual(reviewReasonDisplay("ocr_failed_or_unavailable"), {
    title: "OCR 识别失败或不可用",
    description: "图片或扫描附件未能可靠提取文本，需人工确认。"
  });
  assert.equal(reviewReasonText("high_or_critical_severity"), "高危或严重事件");
});

test("unknown review reason does not expose raw internal code", () => {
  const display = reviewReasonDisplay("new_internal_reason_code");

  assert.equal(display.title, "需要人工复核");
  assert(!display.description.includes("new_internal_reason_code"));
});
