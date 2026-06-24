from typing import Any

from app.models import TicketSeverity


CLASSIFICATION_RULES = [
    {
        "category": "安全风险",
        "severity": TicketSeverity.high,
        "keywords": ["phishing", "suspicious", "unknown login", "malware", "unauthorized", "安全风险", "安全告警", "可疑", "告警", "钓鱼", "未知登录", "异常登录", "恶意软件", "未授权"],
    },
    {
        "category": "网络连接",
        "severity": TicketSeverity.medium,
        "keywords": ["vpn", "network", "wifi", "cannot connect", "网络连接", "无法连接", "网络", "无线", "连接失败", "频繁断开", "延迟"],
    },
    {
        "category": "账号权限",
        "severity": TicketSeverity.medium,
        "keywords": ["password", "mfa", "login", "access denied", "账号权限", "密码", "验证码", "登录", "拒绝访问", "权限", "账号", "无法访问"],
    },
    {
        "category": "软件系统",
        "severity": TicketSeverity.high,
        "keywords": ["500", "database", "timeout", "api", "exception", "软件系统", "数据库", "超时", "接口", "异常", "空白页", "构建失败"],
    },
    {
        "category": "系统资源",
        "severity": TicketSeverity.high,
        "keywords": ["disk", "cpu", "memory", "server down", "系统资源", "硬件设备", "磁盘", "内存", "服务器宕机", "空间不足", "占用率"],
    },
]

NO_INCIDENT_CONTEXT_MARKERS = [
    "没有报告实际故障",
    "未报告实际故障",
    "非故障",
    "培训材料",
    "演练材料",
    "测试文本",
    "not an incident",
    "training material",
]


def _confidence(match_count: int) -> float:
    if match_count >= 3:
        return min(0.95, 0.85 + (match_count - 3) * 0.02)
    if match_count == 2:
        return 0.84
    if match_count == 1:
        return 0.76
    return 0.52


def classify_incident(
    title: str,
    description: str,
    user_category: str | None = None,
    urgency: str | None = None,
    affected_system: str | None = None,
    multimodal_signals: dict[str, Any] | None = None,
    log_content: str | None = None,
) -> dict[str, Any]:
    """Offline rules fallback. This is not an LLM and is labeled accordingly."""
    signals = multimodal_signals or {}
    detected_keywords = signals.get("detected_keywords", [])
    evidence_items = signals.get("evidence", [])
    evidence_text = " ".join(str(item.get("excerpt", "")) for item in evidence_items if item.get("excerpt"))
    usable_evidence = [item for item in evidence_items if item.get("available") or item.get("excerpt")]
    searchable = " ".join(
        [
            title,
            description,
            user_category or "",
            urgency or "",
            affected_system or "",
            log_content or "",
            signals.get("ocr_text", ""),
            evidence_text,
            " ".join(detected_keywords),
        ]
    ).lower()

    if any(marker in searchable for marker in NO_INCIDENT_CONTEXT_MARKERS):
        return {
            "predicted_category": "其他",
            "severity": TicketSeverity.low,
            "confidence": 0.58,
            "matched_keywords": [],
            "rationale": "检测到关键词处于培训/非故障上下文，不按真实事件升级。",
            "evidence": usable_evidence,
            "retrieved_sources": [],
            "uncertainty": "文本包含风险词，但上下文说明未报告实际故障，建议人工确认。",
            "provider": "rule_fallback",
        }

    best: dict[str, Any] | None = None
    for rule in CLASSIFICATION_RULES:
        matched = [keyword for keyword in rule["keywords"] if keyword.lower() in searchable]
        if matched and (best is None or len(matched) > len(best["matched_keywords"])):
            best = {
                "predicted_category": rule["category"],
                "severity": rule["severity"],
                "matched_keywords": matched,
            }

    if best is None:
        return {
            "predicted_category": "其他",
            "severity": TicketSeverity.low,
            "confidence": _confidence(0),
            "matched_keywords": [],
            "rationale": "未命中明显规则关键词，按低风险其他类处理。",
            "evidence": usable_evidence,
            "retrieved_sources": [],
            "uncertainty": "未命中明确证据，仅可作为低置信度离线规则 fallback 结果。",
            "provider": "rule_fallback",
        }

    match_count = len(set(best["matched_keywords"] + detected_keywords))
    severity = best["severity"]
    if urgency == "高" and severity == TicketSeverity.medium:
        severity = TicketSeverity.high
    confidence = _confidence(match_count)
    uncertainty = None
    if not usable_evidence:
        confidence = min(confidence, 0.69)
        uncertainty = "没有可追溯证据，禁止输出高置信度结论，建议人工复核。"
    elif confidence < 0.7:
        uncertainty = "证据较弱或命中规则较少，建议人工复核。"

    return {
        "predicted_category": best["predicted_category"],
        "severity": severity,
        "confidence": confidence,
        "matched_keywords": sorted(set(best["matched_keywords"] + detected_keywords)),
        "rationale": f"命中 {best['predicted_category']} 规则关键词：{', '.join(best['matched_keywords'])}",
        "evidence": usable_evidence,
        "retrieved_sources": [],
        "uncertainty": uncertainty,
        "provider": "rule_fallback",
    }
