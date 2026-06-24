import type { Severity, TaskStatus, TicketStatus } from "@/types";

export const severityText: Record<Severity, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重"
};

export const statusText: Record<TicketStatus, string> = {
  open: "待分诊",
  triaged: "已分诊",
  in_progress: "处理中",
  resolved: "已解决",
  closed: "已关闭"
};

export const taskStatusText: Record<TaskStatus, string> = {
  todo: "待处理",
  in_progress: "进行中",
  done: "已完成"
};

export function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function attachmentTypeText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    screenshot: "截图",
    log: "日志",
    other: "其他附件"
  };
  return mapping[value || ""] || value || "未知类型";
}

export function evidenceSourceTypeText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    text: "文本证据",
    log: "日志证据",
    ocr: "截图 OCR 证据"
  };
  return mapping[value || ""] || value || "未知证据";
}

export function evidenceAvailabilityText(item: { available?: boolean; ocr_status?: string }) {
  if (item.available) return "已提取";
  const mapping: Record<string, string> = {
    success: "识别成功",
    failed: "识别失败",
    unavailable: "组件不可用",
    no_text_detected: "未识别到文字",
    not_provided: "未提供",
    limited: "证据有限"
  };
  return mapping[item.ocr_status || "limited"] || item.ocr_status || "证据有限";
}

export function stageStatusText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    success: "成功",
    degraded: "降级",
    failed: "失败",
    skipped: "跳过"
  };
  return mapping[value || ""] || value || "未知";
}

export function stageNameText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    input_validation: "输入校验",
    attachment_reading_and_redaction: "附件读取与脱敏",
    evidence_extraction: "证据提取",
    pre_classification: "初步分类",
    retrieval_prepare: "检索准备",
    dense_candidate_retrieval: "向量候选召回",
    bm25_lexical_retrieval: "BM25 关键词召回",
    rrf_fusion: "RRF 融合排序",
    candidate_deduplication: "候选去重",
    rerank: "重排序",
    evidence_thresholding: "证据阈值过滤",
    final_triage: "最终分诊",
    resolution: "处置建议生成",
    risk_policy_and_review: "风险策略与人工复核"
  };
  return mapping[value || ""] || value || "未知阶段";
}

export function eventTypeText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    created: "创建工单",
    ai_analyzed: "AI 分析完成",
    ai_triaged: "AI 分诊完成",
    ai_review_required: "需要人工复核",
    reanalyzed: "重新分析",
    admin_reply: "管理员回复",
    status_changed: "状态变更",
    assigned: "分配团队",
    task_created: "创建任务",
    ai_review_updated: "AI 复核更新",
    resolved: "已解决",
    closed: "已关闭"
  };
  return mapping[value || ""] || value || "未知事件";
}

export function providerText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    rule_fallback: "离线规则分诊",
    local_hash_embedding_fallback: "本地哈希向量回退",
    bm25_lexical: "BM25 关键词检索",
    rrf_fusion: "RRF 融合排序",
    heuristic_rerank: "启发式重排序",
    heuristic_reranker: "启发式重排序",
    pytesseract_ocr: "Tesseract OCR",
    "local hybrid retrieval": "本地混合检索"
  };
  return mapping[value || ""] || value || "未知提供方";
}

export function aiReviewStatusText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    pending: "待复核",
    approved: "已通过",
    overridden: "人工覆盖"
  };
  return mapping[value || ""] || value || "未知状态";
}

export function reviewReasonText(value: string | null | undefined) {
  const mapping: Record<string, string> = {
    low_confidence: "低置信度",
    high_severity: "高严重等级",
    critical_severity: "严重事件",
    high_or_critical_severity: "高危或严重事件",
    security_risk: "安全风险",
    security_category: "安全风险类别",
    suspicious_keywords: "命中可疑关键词",
    log_attached: "包含日志附件",
    ocr_failed: "OCR 降级或失败",
    insufficient_evidence: "证据不足",
    seed_demo_review: "演示复核样例"
  };
  return mapping[value || ""] || value || "未知原因";
}

export function timelineContentText(value: string | null | undefined) {
  if (!value) return "";
  let text = value;
  text = text.replace(/\/\s*(low|medium|high|critical)\s*\//g, (_match, severity: string) => {
    return `/ ${severityText[severity as Severity] || severity} /`;
  });
  text = text.replace(/置信度\s+([01](?:\.\d+)?)/g, (_match, raw: string) => {
    const score = Number(raw);
    return Number.isFinite(score) ? `置信度 ${percent(score)}` : `置信度 ${raw}`;
  });
  text = text.replace(/provider=([A-Za-z0-9_ -]+)(?=\s*\/|$)/g, (_match, provider: string) => {
    return `提供方：${providerText(provider.trim())} `;
  });
  text = text.replace(/trace_id=/g, "追踪 ID：");
  text = text.replace(/high_or_critical_severity|security_category|low_confidence|suspicious_keywords|log_attached|ocr_failed|insufficient_evidence/g, (reason) => {
    return reviewReasonText(reason);
  });
  return text;
}
