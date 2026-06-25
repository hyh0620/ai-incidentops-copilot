import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.analysis.contracts import EvidenceBundle, RetrievalCandidate, RetrievalResult, TriageDecision
from app.core.config import get_settings
from app.evidence.redaction import redact_text
from app.triage.rule_provider import RuleFallbackTriageProvider


class LLMAnalysisOutput(BaseModel):
    category: str = Field(min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    summary: str = Field(min_length=1)
    recommended_actions: list[str] = Field(min_length=1)
    cited_chunk_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    review_reason: str | None = None

    @field_validator("cited_chunk_ids")
    @classmethod
    def unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate cited_chunk_ids")
        return value


class OpenAICompatibleTriageProvider:
    provider = "openai_compatible"

    def __init__(
        self,
        fallback_reason: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.fallback_reason = fallback_reason
        self.fallback = RuleFallbackTriageProvider()
        self.client = client

    def _fallback_decision(
        self,
        reason: str,
        title: str,
        description: str,
        user_category: str,
        urgency: str,
        evidence: EvidenceBundle,
        retrieval: RetrievalResult,
        candidate_chunk_ids: list[int],
    ) -> TriageDecision:
        decision = self.fallback.decide(title, description, user_category, urgency, evidence, retrieval)
        decision.provider = "rule_fallback"
        decision.fallback_reason = reason
        decision.llm_validation_status = "failed"
        decision.candidate_chunk_ids = candidate_chunk_ids
        decision.cited_chunk_ids = []
        decision.model_name = get_settings().openai_model or None
        decision.uncertainty = f"LLM 结构化分析失败：{reason}；已回退至规则分诊"
        decision.review_reasons = sorted(set([*decision.review_reasons, "llm_fallback", f"llm_{reason}"]))
        return decision

    def _evidence_candidates(self, retrieval: RetrievalResult) -> list[RetrievalCandidate]:
        settings = get_settings()
        candidates = retrieval.final_sources or retrieval.candidates
        return candidates[: max(1, settings.llm_analysis_max_evidence_chunks)]

    def _messages(
        self,
        title: str,
        description: str,
        user_category: str,
        urgency: str,
        evidence: EvidenceBundle,
        candidates: list[RetrievalCandidate],
    ) -> list[dict[str, str]]:
        settings = get_settings()
        safe_title = redact_text(title, settings.redact_internal_ips).text if settings.enable_pii_redaction else title
        safe_description = redact_text(description, settings.redact_internal_ips).text if settings.enable_pii_redaction else description
        safe_ticket = {
            "title": safe_title[:600],
            "description": safe_description[:1600],
            "user_category": user_category,
            "urgency": urgency,
            "evidence": [
                {
                    "id": item.id,
                    "source_type": item.source_type,
                    "source_name": item.source_name,
                    "excerpt": item.excerpt[:1200],
                    "signal_tags": item.signal_tags,
                    "redacted": item.redacted,
                }
                for item in evidence.items
                if item.available
            ],
        }
        safe_chunks = [
            {
                "chunk_id": str(candidate.chunk_id),
                "title": candidate.title,
                "excerpt": candidate.excerpt[:1000],
                "final_score": float(candidate.rerank_score if candidate.rerank_score is not None else candidate.fusion_score),
            }
            for candidate in candidates
        ]
        schema_hint = {
            "category": "string",
            "severity": "low | medium | high | critical",
            "summary": "string",
            "recommended_actions": ["string"],
            "cited_chunk_ids": ["string"],
            "confidence": 0.0,
            "review_reason": "string | null",
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是只读的运维事件分析助手。只能基于给定工单摘要和候选知识库证据给出结构化 JSON。"
                    "必须引用候选中的 chunk_id，不得编造证据，不得执行命令或更改状态。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "ticket": safe_ticket,
                        "retrieved_evidence_chunks": safe_chunks,
                        "required_json_schema": schema_hint,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _call_provider(self, messages: list[dict[str, str]]) -> str:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("missing_api_key")
        if not settings.openai_model:
            raise RuntimeError("provider_error: missing OPENAI_MODEL")
        url = f"{settings.openai_api_base.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=settings.llm_analysis_timeout_seconds)
        try:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except httpx.TimeoutException as exc:
            raise RuntimeError("timeout") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"provider_error: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _parse_output(self, raw: str) -> LLMAnalysisOutput:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("invalid_json") from exc
        try:
            return LLMAnalysisOutput.model_validate(data)
        except ValidationError as exc:
            raise RuntimeError(f"invalid_schema: {exc.errors()[0]['msg']}") from exc

    def _validate_citations(self, output: LLMAnalysisOutput, candidates: list[RetrievalCandidate]) -> list[int]:
        allowed = {str(candidate.chunk_id): int(candidate.chunk_id) for candidate in candidates}
        cited: list[int] = []
        for chunk_id in output.cited_chunk_ids:
            if chunk_id not in allowed:
                raise RuntimeError("invalid_citation")
            cited.append(allowed[chunk_id])
        return cited

    def decide(
        self,
        title: str,
        description: str,
        user_category: str,
        urgency: str,
        evidence: EvidenceBundle,
        retrieval: RetrievalResult,
    ) -> TriageDecision:
        candidates = self._evidence_candidates(retrieval)
        candidate_chunk_ids = [int(candidate.chunk_id) for candidate in candidates]
        if self.fallback_reason:
            return self._fallback_decision(self.fallback_reason, title, description, user_category, urgency, evidence, retrieval, candidate_chunk_ids)
        if not candidates:
            return self._fallback_decision("invalid_citation", title, description, user_category, urgency, evidence, retrieval, candidate_chunk_ids)

        try:
            raw = self._call_provider(self._messages(title, description, user_category, urgency, evidence, candidates))
            output = self._parse_output(raw)
            cited_chunk_ids = self._validate_citations(output, candidates)
        except RuntimeError as exc:
            reason = str(exc).split(":", 1)[0]
            if reason not in {"missing_api_key", "timeout", "provider_error", "invalid_json", "invalid_schema", "invalid_citation"}:
                reason = "provider_error"
            return self._fallback_decision(reason, title, description, user_category, urgency, evidence, retrieval, candidate_chunk_ids)

        supported_evidence_ids = [item.id for item in evidence.items if item.available and item.excerpt]
        review_reasons = [output.review_reason] if output.review_reason else []
        return TriageDecision(
            predicted_category=output.category,
            severity=output.severity,
            confidence=output.confidence,
            rationale=output.summary,
            requires_human_review=bool(review_reasons),
            review_reasons=review_reasons,
            uncertainty=output.summary,
            provider=self.provider,
            supported_by_evidence_ids=supported_evidence_ids,
            supported_by_chunk_ids=cited_chunk_ids,
            model_name=get_settings().openai_model or None,
            candidate_chunk_ids=candidate_chunk_ids,
            cited_chunk_ids=cited_chunk_ids,
            llm_validation_status="passed",
            fallback_reason=None,
        )
