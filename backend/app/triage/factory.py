from app.core.config import get_settings
from app.triage.base import TriageProvider
from app.triage.optional_llm_provider import OpenAICompatibleTriageProvider
from app.triage.rule_provider import RuleFallbackTriageProvider


def get_triage_provider() -> TriageProvider:
    settings = get_settings()
    configured_provider = settings.analysis_provider
    if configured_provider == "rule_fallback" and settings.triage_provider == "openai_compatible":
        configured_provider = "openai_compatible"
    if configured_provider == "openai_compatible":
        return OpenAICompatibleTriageProvider()
    return RuleFallbackTriageProvider()
