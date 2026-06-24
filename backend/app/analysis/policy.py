from app.analysis.contracts import RetrievalResult, TriageDecision


def apply_review_policy(decision: TriageDecision, retrieval: RetrievalResult, ocr_failed: bool = False) -> TriageDecision:
    reasons = list(decision.review_reasons)
    if decision.confidence < 0.7:
        reasons.append("low_confidence")
    if decision.severity in {"high", "critical"}:
        reasons.append("high_or_critical_severity")
    if decision.predicted_category == "安全风险":
        reasons.append("security_category")
    if retrieval.insufficient_evidence:
        reasons.append("insufficient_retrieval_evidence")
    if ocr_failed:
        reasons.append("ocr_failed_or_unavailable")
    reasons = sorted(set(reasons))
    decision.requires_human_review = bool(reasons)
    decision.review_reasons = reasons
    if reasons and not decision.uncertainty:
        decision.uncertainty = "触发人工复核策略：" + ", ".join(reasons)
    return decision
