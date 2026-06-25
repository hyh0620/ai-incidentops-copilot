import json

import httpx
import pytest

from app.analysis.contracts import EvidenceBundle, EvidenceItem, RetrievalCandidate, RetrievalResult
from app.core.config import get_settings
from app.triage.factory import get_triage_provider
from app.triage.optional_llm_provider import OpenAICompatibleTriageProvider
from app.triage.rule_provider import RuleFallbackTriageProvider


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        items=[
            EvidenceItem(
                id="ev-text-0",
                source_type="text",
                source_name="ticket_text",
                excerpt="API HTTP 500 [REDACTED_EMAIL] [REDACTED_BEARER_TOKEN]",
                available=True,
                redacted=True,
                signal_tags=["api", "500"],
            )
        ]
    )


def _retrieval() -> RetrievalResult:
    candidate = RetrievalCandidate(
        article_id=1,
        chunk_id=101,
        title="生产 API 返回 500 错误",
        category="软件系统",
        excerpt="HTTP 500 exception troubleshooting",
        dense_score=0.9,
        lexical_score=1.0,
        fusion_score=0.7,
        provider="local_hash_embedding_fallback",
        metadata={"final_score": 0.7},
    )
    return RetrievalResult(
        candidates=[candidate],
        final_sources=[candidate],
        retrieval_mode="local hybrid retrieval",
        insufficient_evidence=False,
        threshold=0.02,
    )


def _client_with_content(content: str, captured: list[str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request.content.decode())
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _configure_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "fixture-model")
    monkeypatch.setenv("OPENAI_API_BASE", "http://llm.local/v1")
    get_settings.cache_clear()


def test_default_factory_returns_rule_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANALYSIS_PROVIDER", "rule_fallback")
    get_settings.cache_clear()

    assert isinstance(get_triage_provider(), RuleFallbackTriageProvider)


def test_valid_llm_json_passes_schema_and_citation(monkeypatch: pytest.MonkeyPatch):
    _configure_llm(monkeypatch)
    captured: list[str] = []
    client = _client_with_content(
        json.dumps(
            {
                "category": "软件系统",
                "severity": "high",
                "summary": "HTTP 500 与 API 异常证据一致",
                "recommended_actions": ["查看服务日志"],
                "cited_chunk_ids": ["101"],
                "confidence": 0.82,
                "review_reason": "高危事件需复核",
            }
        ),
        captured,
    )
    provider = OpenAICompatibleTriageProvider(client=client)

    decision = provider.decide(
        "用户 user@example.com 报告 API 500",
        "Bearer abcdefghijklmnop password=Secret123",
        "软件系统",
        "高",
        _evidence(),
        _retrieval(),
    )

    assert decision.provider == "openai_compatible"
    assert decision.llm_validation_status == "passed"
    assert decision.supported_by_chunk_ids == [101]
    assert decision.confidence == 0.82
    sent = "\n".join(captured)
    assert "user@example.com" not in sent
    assert "Secret123" not in sent
    assert "abcdefghijklmnop" not in sent


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("not-json", "invalid_json"),
        (
            json.dumps(
                {
                    "category": "软件系统",
                    "severity": "urgent",
                    "summary": "bad",
                    "recommended_actions": ["x"],
                    "cited_chunk_ids": ["101"],
                    "confidence": 0.8,
                    "review_reason": None,
                }
            ),
            "invalid_schema",
        ),
        (
            json.dumps(
                {
                    "category": "软件系统",
                    "severity": "high",
                    "summary": "bad",
                    "recommended_actions": ["x"],
                    "cited_chunk_ids": ["999"],
                    "confidence": 0.8,
                    "review_reason": None,
                }
            ),
            "invalid_citation",
        ),
        (
            json.dumps(
                {
                    "category": "软件系统",
                    "severity": "high",
                    "summary": "bad",
                    "recommended_actions": ["x"],
                    "cited_chunk_ids": [],
                    "confidence": 0.8,
                    "review_reason": None,
                }
            ),
            "invalid_schema",
        ),
        (
            json.dumps(
                {
                    "category": "软件系统",
                    "severity": "high",
                    "summary": "bad",
                    "recommended_actions": ["x"],
                    "cited_chunk_ids": ["101", "101"],
                    "confidence": 0.8,
                    "review_reason": None,
                }
            ),
            "invalid_schema",
        ),
    ],
)
def test_llm_validation_failures_fallback(monkeypatch: pytest.MonkeyPatch, content: str, reason: str):
    _configure_llm(monkeypatch)
    provider = OpenAICompatibleTriageProvider(client=_client_with_content(content))

    decision = provider.decide("API 500", "API 500", "软件系统", "高", _evidence(), _retrieval())

    assert decision.provider == "rule_fallback"
    assert decision.fallback_reason == reason
    assert decision.llm_validation_status == "failed"
    assert "llm_fallback" in decision.review_reasons


def test_missing_api_key_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "fixture-model")
    get_settings.cache_clear()

    decision = OpenAICompatibleTriageProvider().decide("API 500", "API 500", "软件系统", "高", _evidence(), _retrieval())

    assert decision.provider == "rule_fallback"
    assert decision.fallback_reason == "missing_api_key"


def test_timeout_and_provider_error_fallback(monkeypatch: pytest.MonkeyPatch):
    _configure_llm(monkeypatch)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    timeout_decision = OpenAICompatibleTriageProvider(client=httpx.Client(transport=httpx.MockTransport(timeout_handler))).decide(
        "API 500", "API 500", "软件系统", "高", _evidence(), _retrieval()
    )

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    error_decision = OpenAICompatibleTriageProvider(client=httpx.Client(transport=httpx.MockTransport(error_handler))).decide(
        "API 500", "API 500", "软件系统", "高", _evidence(), _retrieval()
    )

    assert timeout_decision.fallback_reason == "timeout"
    assert error_decision.fallback_reason == "provider_error"
