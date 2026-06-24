from typing import Protocol

from app.analysis.contracts import EvidenceBundle, RetrievalResult, TriageDecision


class TriageProvider(Protocol):
    provider: str

    def decide(self, title: str, description: str, user_category: str, urgency: str, evidence: EvidenceBundle, retrieval: RetrievalResult) -> TriageDecision:
        ...
