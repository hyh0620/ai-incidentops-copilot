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
  const normalized = normalizeApiDate(value);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(normalized));
}

export function normalizeApiDate(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return value;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  if (hasTimezone) return trimmed;
  return `${trimmed.replace(" ", "T")}Z`;
}

export function isSameLocalDay(value: string | null | undefined, date = new Date()) {
  if (!value) return false;
  const current = new Date(normalizeApiDate(value));
  return (
    current.getFullYear() === date.getFullYear()
    && current.getMonth() === date.getMonth()
    && current.getDate() === date.getDate()
  );
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
    openai_compatible: "LLM 结构化分析",
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

export interface ReviewReasonDisplay {
  title: string;
  description: string;
}

export function reviewReasonDisplay(value: string | null | undefined): ReviewReasonDisplay {
  const mapping: Record<string, ReviewReasonDisplay> = {
    insufficient_retrieval_evidence: {
      title: "检索证据不足",
      description: "未找到足够强的知识库依据，需人工确认。"
    },
    ocr_failed_or_unavailable: {
      title: "OCR 识别失败或不可用",
      description: "图片或扫描附件未能可靠提取文本，需人工确认。"
    },
    high_or_critical_severity: {
      title: "高危或严重事件",
      description: "当前事件等级较高，需要管理员确认。"
    },
    high_severity: {
      title: "高危或严重事件",
      description: "当前事件等级较高，需要管理员确认。"
    },
    critical_severity: {
      title: "高危或严重事件",
      description: "当前事件等级较高，需要管理员确认。"
    },
    security_category: {
      title: "安全风险事件",
      description: "涉及安全风险，需人工确认处置。"
    },
    security_risk: {
      title: "安全风险事件",
      description: "涉及安全风险，需人工确认处置。"
    },
    suspicious_keywords: {
      title: "安全风险事件",
      description: "命中可疑关键词，需人工确认处置。"
    },
    sensitive_access_or_data_category: {
      title: "敏感权限或数据事件",
      description: "涉及账号、权限或敏感数据，需人工确认。"
    },
    low_confidence: {
      title: "低置信度分析",
      description: "系统判断置信度较低，需要人工确认。"
    },
    llm_fallback: {
      title: "分析已降级回退",
      description: "可选 LLM 分析未通过校验，已回退到规则分诊。"
    },
    llm_validation_failed: {
      title: "LLM 输出校验失败",
      description: "结构化输出或引用校验未通过，需人工确认。"
    },
    seed_demo_review: {
      title: "演示复核样例",
      description: "合成演示数据中的人工复核记录。"
    }
  };
  if (value?.startsWith("llm_")) {
    return {
      title: "LLM 分析降级",
      description: "可选 LLM 分析未完成或未通过校验，需人工确认。"
    };
  }
  return mapping[value || ""] || {
    title: "需要人工复核",
    description: "系统记录了新的复核原因，建议查看原始分析记录（调试）。"
  };
}

export function reviewReasonText(value: string | null | undefined) {
  return reviewReasonDisplay(value).title;
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
  text = text.replace(/insufficient_retrieval_evidence|ocr_failed_or_unavailable|high_or_critical_severity|security_category|sensitive_access_or_data_category|low_confidence|suspicious_keywords|log_attached|ocr_failed|insufficient_evidence/g, (reason) => {
    return reviewReasonText(reason);
  });
  return text;
}
