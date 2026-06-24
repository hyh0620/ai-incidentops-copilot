from app.analysis.contracts import EvidenceBundle, RetrievalResult, TriageDecision
from app.models import TicketSeverity
from app.services.incident_classifier import classify_incident


class RuleFallbackTriageProvider:
    provider = "rule_fallback"

    def decide(self, title: str, description: str, user_category: str, urgency: str, evidence: EvidenceBundle, retrieval: RetrievalResult) -> TriageDecision:
        signals = sorted({tag for item in evidence.items for tag in item.signal_tags})
        legacy_signals = {
            "detected_keywords": signals,
            "evidence": [
                {
                    "source_type": item.source_type,
                    "source_name": item.source_name,
                    "excerpt": item.excerpt,
                    "available": item.available,
                }
                for item in evidence.items
            ],
        }
        result = classify_incident(title, description, user_category, urgency, None, legacy_signals, "\n".join(item.excerpt for item in evidence.items))
        supported_evidence_ids = [item.id for item in evidence.items if item.available and item.excerpt]
        supported_chunk_ids = [source.chunk_id for source in retrieval.final_sources]
        confidence = float(result["confidence"])
        if not supported_evidence_ids:
            confidence = min(confidence, 0.69)
        return TriageDecision(
            predicted_category=str(result["predicted_category"]),
            severity=result["severity"].value if isinstance(result["severity"], TicketSeverity) else str(result["severity"]),
            confidence=confidence,
            rationale=str(result.get("rationale", "rule fallback decision")),
            requires_human_review=False,
            review_reasons=[],
            uncertainty=result.get("uncertainty"),
            provider=self.provider,
            supported_by_evidence_ids=supported_evidence_ids,
            supported_by_chunk_ids=supported_chunk_ids,
        )
