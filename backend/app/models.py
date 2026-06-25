from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    requester = "requester"
    admin = "admin"


class TicketSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TicketStatus(str, Enum):
    open = "open"
    triaged = "triaged"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class AttachmentFileType(str, Enum):
    screenshot = "screenshot"
    log = "log"
    other = "other"


class RemediationTaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class AIReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    overridden = "overridden"


class KBIngestionStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    degraded = "degraded"
    failed = "failed"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.requester, index=True)
    department: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Ticket(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    requester_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(index=True)
    description: str = Field(sa_column=Column(Text))
    user_category: str = Field(index=True)
    predicted_category: str | None = Field(default=None, index=True)
    affected_system: str | None = Field(default=None, index=True)
    urgency: str = Field(default="中", index=True)
    severity: TicketSeverity = Field(default=TicketSeverity.low, index=True)
    confidence: float = Field(default=0.0, index=True)
    status: TicketStatus = Field(default=TicketStatus.open, index=True)
    assigned_team: str | None = Field(default=None, index=True)
    suggested_resolution: str | None = Field(default=None, sa_column=Column(Text))
    next_steps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    related_kb_articles: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    ai_signals: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketAttachment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    file_name: str
    file_path: str
    file_type: AttachmentFileType = Field(default=AttachmentFileType.other, index=True)
    mime_type: str | None = Field(default=None, index=True)
    size_bytes: int = Field(default=0)
    checksum: str | None = Field(default=None, index=True)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBaseArticle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    category: str = Field(index=True)
    content: str = Field(sa_column=Column(Text))
    summary: str = Field(sa_column=Column(Text))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reading_time: int = Field(default=3)
    hit_count: int = Field(default=0, index=True)
    source_name: str | None = Field(default=None, index=True)
    source_filename: str | None = Field(default=None, index=True)
    source_type: str = Field(default="manual", index=True)
    source_checksum: str | None = Field(default=None, index=True)
    version: str = Field(default="v1", index=True)
    page_count: int | None = Field(default=None)
    ingestion_run_id: int | None = Field(default=None, foreign_key="kbingestionrun.id", index=True)
    kb_version: str = Field(default="kb-v1", index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ingestion_status: str = Field(default="ready", index=True)
    index_status: str = Field(default="stale", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBaseChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="knowledgebasearticle.id", index=True)
    chunk_index: int = Field(index=True)
    content: str = Field(sa_column=Column(Text))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    content_hash: str = Field(index=True, unique=True)
    page_number: int | None = Field(default=None, index=True)
    kb_version: str = Field(default="kb-v1", index=True)
    ingestion_run_id: int | None = Field(default=None, foreign_key="kbingestionrun.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class KBIngestionRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: KBIngestionStatus = Field(default=KBIngestionStatus.pending, index=True)
    source_filename: str | None = Field(default=None, index=True)
    source_type: str | None = Field(default=None, index=True)
    document_count: int = Field(default=0)
    chunk_count: int = Field(default=0)
    embedding_provider: str = Field(default="local_hash_embedding_fallback", index=True)
    embedding_model: str | None = Field(default=None, index=True)
    kb_version: str = Field(default="kb-v1", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: datetime | None = Field(default=None, index=True)
    latency_ms: float | None = Field(default=None)
    fallback_reason: str | None = Field(default=None, sa_column=Column(Text))
    error_message: str | None = Field(default=None, sa_column=Column(Text))


class TicketTimelineEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    event_type: str = Field(index=True)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RemediationTask(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    title: str
    description: str = Field(sa_column=Column(Text))
    assigned_to: str = Field(index=True)
    status: RemediationTaskStatus = Field(default=RemediationTaskStatus.todo, index=True)
    due_date: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AdminNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    author: str = Field(default="管理员", index=True)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AIReview(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    original_category: str
    original_severity: TicketSeverity
    run_id: str | None = Field(default=None, index=True)
    review_reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    corrected_category: str | None = Field(default=None)
    corrected_severity: TicketSeverity | None = Field(default=None)
    correction_reason: str | None = Field(default=None, sa_column=Column(Text))
    reviewer_note: str | None = Field(default=None, sa_column=Column(Text))
    status: AIReviewStatus = Field(default=AIReviewStatus.pending, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AIAnalysisAudit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    run_id: str = Field(index=True, unique=True)
    trace_id: str = Field(index=True)
    analysis_version: str = Field(default="evidence-v1", index=True)
    provider: str = Field(index=True)
    retrieval_mode: str = Field(index=True)
    index_version: str | None = Field(default=None, index=True)
    corpus_hash: str | None = Field(default=None, index=True)
    chunking_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    stage_traces: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    final_decision: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    resolution: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    candidate_sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    previous_diff: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source_chunk_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    retrieved_sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    uncertainty: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
