from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: str
    source_type: str
    source_name: str
    source_id: str | None = None
    excerpt: str
    available: bool
    redacted: bool = False
    signal_tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)
    redaction_enabled: bool = True
    redaction_summary: dict[str, int] = Field(default_factory=dict)


class RetrievalCandidate(BaseModel):
    article_id: int
    chunk_id: int
    title: str
    category: str
    excerpt: str
    dense_score: float = 0.0
    lexical_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float | None = None
    ranking_stage: str = "fusion"
    provider: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    final_sources: list[RetrievalCandidate] = Field(default_factory=list)
    retrieval_mode: str
    index_version: str | None = None
    corpus_hash: str | None = None
    insufficient_evidence: bool = False
    threshold: float
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class TriageDecision(BaseModel):
    predicted_category: str
    severity: str
    confidence: float
    rationale: str
    requires_human_review: bool
    review_reasons: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    provider: str
    supported_by_evidence_ids: list[str] = Field(default_factory=list)
    supported_by_chunk_ids: list[int] = Field(default_factory=list)


class ResolutionStep(BaseModel):
    text: str
    citation_chunk_ids: list[int] = Field(default_factory=list)
    citation_evidence_ids: list[str] = Field(default_factory=list)
    provider: str = "policy_playbook_fallback"


class ResolutionProposal(BaseModel):
    summary: str
    steps: list[ResolutionStep] = Field(default_factory=list)
    provider: str = "policy_playbook_fallback"
    insufficient_evidence: bool = False


class AnalysisStageTrace(BaseModel):
    name: str
    status: Literal["success", "degraded", "failed", "skipped"]
    provider: str | None = None
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    input_summary: str | None = None
    output_summary: str | None = None
    error: str | None = None


class AnalysisRunDiff(BaseModel):
    category_changed: bool = False
    severity_changed: bool = False
    confidence_delta: float = 0.0
    evidence_changed: bool = False
    sources_changed: bool = False
    review_reasons_changed: bool = False


class AnalysisRunResult(BaseModel):
    run_id: str
    trace_id: str
    ticket_id: int
    analysis_version: str
    created_at: datetime
    evidence_bundle: EvidenceBundle
    retrieval: RetrievalResult
    triage: TriageDecision
    resolution: ResolutionProposal
    stages: list[AnalysisStageTrace]
    previous_diff: AnalysisRunDiff | None = None
    provider_status: dict[str, str] = Field(default_factory=dict)
