from app.analysis.contracts import RetrievalResult, TriageDecision


def apply_review_policy(
    decision: TriageDecision,
    retrieval: RetrievalResult,
    ocr_failed: bool = False,
    ocr_attempted: bool = False,
) -> TriageDecision:
    reasons = [
        reason
        for reason in decision.review_reasons
        if reason != "ocr_failed_or_unavailable" or (ocr_attempted and ocr_failed)
    ]
    if decision.confidence < 0.7:
        reasons.append("low_confidence")
    if decision.severity in {"high", "critical"}:
        reasons.append("high_or_critical_severity")
    if decision.predicted_category == "安全风险":
        reasons.append("security_category")
    if any(term in decision.predicted_category for term in ["权限", "数据泄露", "账号"]):
        reasons.append("sensitive_access_or_data_category")
    if retrieval.insufficient_evidence:
        reasons.append("insufficient_retrieval_evidence")
    if ocr_attempted and ocr_failed:
        reasons.append("ocr_failed_or_unavailable")
    if decision.fallback_reason:
        reasons.append("llm_fallback")
    if decision.llm_validation_status and decision.llm_validation_status != "passed":
        reasons.append("llm_validation_failed")
    reasons = sorted(set(reasons))
    decision.requires_human_review = bool(reasons)
    decision.review_reasons = reasons
    if reasons and not decision.uncertainty:
        decision.uncertainty = "触发人工复核策略：" + ", ".join(reasons)
    return decision
