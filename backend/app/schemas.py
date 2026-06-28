from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from app.core.time import utc_isoformat
from app.models import (
    AIReviewStatus,
    AttachmentFileType,
    KBIngestionStatus,
    RemediationTaskStatus,
    TicketSeverity,
    TicketStatus,
    UserRole,
)


class UTCBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_utc_datetime(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return utc_isoformat(value)
        return value


class UserRead(UTCBaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    department: str
    created_at: datetime


class AttachmentRead(UTCBaseModel):
    id: int
    ticket_id: int
    file_name: str
    file_path: str
    file_type: AttachmentFileType
    mime_type: str | None = None
    size_bytes: int = 0
    checksum: str | None = None
    uploaded_at: datetime


class KnowledgeBaseArticleCreate(UTCBaseModel):
    title: str
    category: str
    content: str
    summary: str
    tags: list[str] = []
    reading_time: int = 3


class KnowledgeBaseArticleRead(KnowledgeBaseArticleCreate):
    id: int
    hit_count: int
    source_name: str | None = None
    source_filename: str | None = None
    source_type: str = "manual"
    source_checksum: str | None = None
    version: str = "v1"
    page_count: int | None = None
    ingestion_run_id: int | None = None
    kb_version: str = "kb-v1"
    updated_at: datetime | None = None
    ingestion_status: str = "ready"
    index_status: str = "stale"
    created_at: datetime


class KBIngestionRunRead(UTCBaseModel):
    id: int
    status: KBIngestionStatus
    source_filename: str | None = None
    source_type: str | None = None
    document_count: int
    chunk_count: int
    embedding_provider: str
    embedding_model: str | None = None
    kb_version: str
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: float | None = None
    fallback_reason: str | None = None
    error_message: str | None = None


class TicketTimelineEventRead(UTCBaseModel):
    id: int
    ticket_id: int
    event_type: str
    content: str
    created_at: datetime


class RemediationTaskCreate(BaseModel):
    ticket_id: int
    title: str
    description: str
    assigned_to: str
    due_date: datetime | None = None
    status: RemediationTaskStatus = RemediationTaskStatus.todo


class RemediationTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    due_date: datetime | None = None
    status: RemediationTaskStatus | None = None


class RemediationTaskRead(UTCBaseModel):
    id: int
    ticket_id: int
    title: str
    description: str
    assigned_to: str
    status: RemediationTaskStatus
    due_date: datetime | None
    created_at: datetime


class AdminNoteRead(UTCBaseModel):
    id: int
    ticket_id: int
    author: str
    content: str
    created_at: datetime


class AIReviewRead(UTCBaseModel):
    id: int
    ticket_id: int
    original_category: str
    original_severity: TicketSeverity
    run_id: str | None = None
    review_reasons: list[str] = []
    corrected_category: str | None
    corrected_severity: TicketSeverity | None
    correction_reason: str | None = None
    reviewer_note: str | None
    status: AIReviewStatus
    created_at: datetime


class AIReviewWithTicketRead(AIReviewRead):
    ticket: dict[str, Any] | None = None


class AIReviewUpdate(BaseModel):
    corrected_category: str | None = None
    corrected_severity: TicketSeverity | None = None
    correction_reason: str | None = None
    reviewer_note: str | None = None
    status: AIReviewStatus


class AIAnalysisAuditRead(UTCBaseModel):
    id: int
    ticket_id: int
    run_id: str
    trace_id: str
    analysis_version: str
    provider: str
    retrieval_mode: str
    index_version: str | None
    corpus_hash: str | None
    chunking_config: dict[str, Any]
    stage_traces: list[dict[str, Any]]
    final_decision: dict[str, Any]
    resolution: dict[str, Any]
    candidate_sources: list[dict[str, Any]]
    previous_diff: dict[str, Any]
    source_chunk_ids: list[int]
    evidence: list[dict[str, Any]]
    retrieved_sources: list[dict[str, Any]]
    uncertainty: str | None
    created_at: datetime


class TicketBaseRead(UTCBaseModel):
    id: int
    requester_id: int
    title: str
    description: str
    user_category: str
    predicted_category: str | None
    affected_system: str | None
    urgency: str
    severity: TicketSeverity
    confidence: float
    status: TicketStatus
    assigned_team: str | None
    suggested_resolution: str | None
    next_steps: list[str]
    related_kb_articles: list[dict[str, Any]]
    ai_signals: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TicketListRead(TicketBaseRead):
    requester: UserRead | None = None
    attachment_count: int = 0


class TicketDetailRead(TicketBaseRead):
    requester: UserRead | None = None
    attachments: list[AttachmentRead] = []
    timeline: list[TicketTimelineEventRead] = []
    tasks: list[RemediationTaskRead] = []
    admin_notes: list[AdminNoteRead] = []
    ai_review: AIReviewRead | None = None
    ai_analysis_audits: list[AIAnalysisAuditRead] = []


class TicketCreateResponse(BaseModel):
    ticket_id: int
    predicted_category: str
    severity: TicketSeverity
    confidence: float
    suggested_resolution: str
    related_kb_articles: list[dict[str, Any]]
    next_steps: list[str]
    provider: str | None = None
    retrieval_mode: str | None = None
    uncertainty: str | None = None
    run_id: str | None = None
    trace_id: str | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TicketStatus | None = None
    severity: TicketSeverity | None = None
    assigned_team: str | None = None
    internal_note: str | None = None
    user_reply: str | None = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketAssignUpdate(BaseModel):
    assigned_team: str


class KBSearchRequest(BaseModel):
    query: str
    category: str | None = None
    top_k: int = 3


class AnalyticsSummary(BaseModel):
    total_tickets: int
    pending_tickets: int
    high_risk_tickets: int
    avg_resolution_hours: float
    today_new_tickets: int
    ai_review_pending: int
