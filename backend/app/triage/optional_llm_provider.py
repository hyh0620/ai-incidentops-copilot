from app.analysis.contracts import EvidenceBundle, RetrievalResult, TriageDecision
from app.triage.rule_provider import RuleFallbackTriageProvider


class OpenAICompatibleTriageProvider:
    provider = "openai_compatible_structured_output_not_implemented"

    def __init__(self, fallback_reason: str = "OpenAI-compatible triage provider is an extension interface and is not implemented in this offline build") -> None:
        self.fallback_reason = fallback_reason
        self.fallback = RuleFallbackTriageProvider()

    def decide(self, title: str, description: str, user_category: str, urgency: str, evidence: EvidenceBundle, retrieval: RetrievalResult) -> TriageDecision:
        decision = self.fallback.decide(title, description, user_category, urgency, evidence, retrieval)
        decision.provider = "rule_fallback"
        decision.uncertainty = f"{self.fallback_reason}; downgraded to rule_fallback"
        decision.review_reasons.append("llm_provider_unavailable")
        return decision
