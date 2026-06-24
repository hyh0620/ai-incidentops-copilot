from app.core.config import get_settings
from app.triage.base import TriageProvider
from app.triage.optional_llm_provider import OpenAICompatibleTriageProvider
from app.triage.rule_provider import RuleFallbackTriageProvider


def get_triage_provider() -> TriageProvider:
    settings = get_settings()
    if settings.triage_provider == "openai_compatible":
        if settings.llm_provider != "openai_compatible":
            return OpenAICompatibleTriageProvider("TRIAGE_PROVIDER=openai_compatible but LLM_PROVIDER is not openai_compatible")
        return OpenAICompatibleTriageProvider("OpenAI-compatible triage provider interface exists but HTTP implementation is not enabled in v2")
    return RuleFallbackTriageProvider()
