import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, func, select

from app.analysis.pipeline import IncidentAnalysisPipeline
from app.core.config import get_settings
from app.core.time import utc_isoformat, utc_now
from app.models import (
    AIReview,
    AIAnalysisAudit,
    AdminNote,
    AttachmentFileType,
    RemediationTask,
    Ticket,
    TicketAttachment,
    KnowledgeBaseChunk,
    TicketSeverity,
    TicketStatus,
    TicketTimelineEvent,
    User,
)
from app.schemas import TicketUpdate


UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS = get_settings()


def _safe_file_name(file_name: str) -> str:
    cleaned = "".join(char for char in file_name if char.isalnum() or char in ("-", "_", ".", " ")).strip()
    return cleaned or "upload.bin"


LOG_EXTENSIONS = {".log", ".txt", ".json", ".csv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


def _file_suffix(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def _is_probably_utf8_text(content: bytes) -> bool:
    if not content:
        return False
    sample = content[:8192]
    if b"\x00" in sample:
        return False
    try:
        decoded = sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    control_count = sum(1 for char in decoded if ord(char) < 32 and char not in "\n\r\t")
    return control_count <= max(2, len(decoded) // 100)


def _is_supported_image(content: bytes, content_type: str, file_name: str) -> bool:
    suffix = _file_suffix(file_name)
    if suffix not in IMAGE_EXTENSIONS:
        return False
    normalized_type = (content_type or "").lower()
    if normalized_type not in SETTINGS.allowed_image_mime_set and normalized_type not in GENERIC_MIME_TYPES:
        return False
    return (
        content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"GIF87a")
        or content.startswith(b"GIF89a")
        or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    )


def _is_supported_log(content: bytes, content_type: str, file_name: str) -> bool:
    suffix = _file_suffix(file_name)
    if suffix not in LOG_EXTENSIONS:
        return False
    normalized_type = (content_type or "").lower()
    if normalized_type not in SETTINGS.allowed_log_mime_set and normalized_type not in GENERIC_MIME_TYPES:
        return False
    return _is_probably_utf8_text(content)


def detect_file_type(file_name: str, content_type: str, content: bytes) -> AttachmentFileType:
    if _is_supported_image(content, content_type, file_name):
        return AttachmentFileType.screenshot
    if _is_supported_log(content, content_type, file_name):
        return AttachmentFileType.log
    raise HTTPException(status_code=400, detail="不支持的附件类型，仅允许 PNG/JPEG/WebP/GIF 截图或 UTF-8 文本日志/JSON/CSV，且会校验文件内容。")


async def save_upload_file(ticket_id: int, file: UploadFile) -> TicketAttachment:
    safe_name = _safe_file_name(file.filename or "upload.bin")
    content = await file.read(SETTINGS.max_upload_bytes + 1)
    if len(content) > SETTINGS.max_upload_bytes:
        raise HTTPException(status_code=413, detail="附件超过 10MB 限制")
    mime_type = file.content_type or "application/octet-stream"
    file_type = detect_file_type(safe_name, mime_type, content)
    stored_name = f"{ticket_id}_{uuid4().hex}_{safe_name}"
    target = UPLOAD_DIR / stored_name
    target.write_bytes(content)
    return TicketAttachment(
        ticket_id=ticket_id,
        file_name=safe_name,
        file_path=str(target),
        file_type=file_type,
        mime_type=mime_type,
        size_bytes=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
    )


def _requires_ai_review(ticket: Ticket) -> bool:
    suspicious_keywords = {"phishing", "suspicious", "malware", "unauthorized", "unknown login", "可疑", "钓鱼"}
    signals = ticket.ai_signals or {}
    detected = {item.lower() for item in signals.get("detected_keywords", [])}
    has_log = bool(signals.get("extracted_signals", {}).get("has_log"))
    return (
        ticket.confidence < 0.7
        or ticket.severity in {TicketSeverity.high, TicketSeverity.critical}
        or ticket.predicted_category == "安全风险"
        or bool(detected & suspicious_keywords)
        or has_log
    )


def _timeline(ticket_id: int, event_type: str, content: str) -> TicketTimelineEvent:
    return TicketTimelineEvent(ticket_id=ticket_id, event_type=event_type, content=content)


def _latest_attachment(attachments: list[TicketAttachment], file_type: AttachmentFileType) -> TicketAttachment | None:
    candidates = [item for item in attachments if item.file_type == file_type]
    return sorted(candidates, key=lambda item: item.uploaded_at, reverse=True)[0] if candidates else None


def analyze_ticket(session: Session, ticket: Ticket, event_type: str = "ai_triaged") -> dict[str, Any]:
    run = IncidentAnalysisPipeline(session).run(ticket)
    related_sources = [source.metadata for source in run.retrieval.final_sources]
    candidate_sources = [source.metadata for source in run.retrieval.candidates]
    source_chunk_ids = run.triage.supported_by_chunk_ids
    provider = run.triage.provider
    retrieval_mode = f"{run.retrieval.retrieval_mode}; {SETTINGS.embedding_provider}; {SETTINGS.reranker_provider}"
    ticket.predicted_category = run.triage.predicted_category
    ticket.severity = TicketSeverity(run.triage.severity)
    ticket.confidence = run.triage.confidence
    ticket.status = TicketStatus.triaged if ticket.status == TicketStatus.open else ticket.status
    ticket.suggested_resolution = run.resolution.summary
    ticket.next_steps = [step.text for step in run.resolution.steps]
    ticket.related_kb_articles = related_sources
    ticket.ai_signals = {
        "evidence": [item.model_dump() for item in run.evidence_bundle.items],
        "classification": run.triage.model_dump(),
        "retrieval": run.retrieval.model_dump(),
        "analysis": {
            "run_id": run.run_id,
            "trace_id": run.trace_id,
            "analysis_version": run.analysis_version,
            "provider": provider,
            "retrieval_mode": retrieval_mode,
            "source_chunk_ids": source_chunk_ids,
            "created_at": utc_isoformat(run.created_at),
        },
    }
    ticket.updated_at = utc_now()
    session.add(ticket)
    session.add(
        AIAnalysisAudit(
            ticket_id=ticket.id,
            run_id=run.run_id,
            trace_id=run.trace_id,
            analysis_version=run.analysis_version,
            provider=provider,
            retrieval_mode=retrieval_mode,
            index_version=run.retrieval.index_version,
            corpus_hash=run.retrieval.corpus_hash,
            chunking_config={
                "chunk_size": SETTINGS.chunk_size,
                "chunk_overlap": SETTINGS.chunk_overlap,
                "version": SETTINGS.chunking_version,
            },
            stage_traces=[stage.model_dump(mode="json") for stage in run.stages],
            final_decision=run.triage.model_dump(),
            resolution=run.resolution.model_dump(),
            candidate_sources=candidate_sources,
            previous_diff=run.previous_diff.model_dump() if run.previous_diff else {},
            source_chunk_ids=source_chunk_ids,
            evidence=[item.model_dump() for item in run.evidence_bundle.items],
            retrieved_sources=related_sources,
            uncertainty=run.triage.uncertainty,
        )
    )
    session.add(
        _timeline(
            ticket.id,
            event_type,
            f"AI 分析完成：{ticket.predicted_category} / {ticket.severity.value} / 置信度 {ticket.confidence:.2f} / provider={provider} / trace_id={run.trace_id}",
        )
    )

    if run.triage.requires_human_review:
        existing_review = session.exec(select(AIReview).where(AIReview.ticket_id == ticket.id, AIReview.status == "pending")).first()
        if existing_review is None:
            session.add(
                AIReview(
                    ticket_id=ticket.id,
                    run_id=run.run_id,
                    original_category=ticket.predicted_category or "其他",
                    original_severity=ticket.severity,
                    review_reasons=run.triage.review_reasons,
                )
            )
            session.add(_timeline(ticket.id, "ai_review_required", "系统判定该工单需要管理员人工复核：" + "、".join(run.triage.review_reasons)))

    session.commit()
    session.refresh(ticket)
    return {
        "ticket_id": ticket.id,
        "predicted_category": ticket.predicted_category,
        "severity": ticket.severity,
        "confidence": ticket.confidence,
        "suggested_resolution": ticket.suggested_resolution,
        "related_kb_articles": ticket.related_kb_articles,
        "next_steps": ticket.next_steps,
        "provider": provider,
        "retrieval_mode": retrieval_mode,
        "uncertainty": run.triage.uncertainty,
        "run_id": run.run_id,
        "trace_id": run.trace_id,
    }


async def create_ticket_with_ai(
    session: Session,
    *,
    title: str,
    description: str,
    user_category: str,
    urgency: str,
    affected_system: str | None,
    contact_email: str,
    screenshot: UploadFile | None,
    log_file: UploadFile | None,
    requester_id: int | None = None,
) -> dict[str, Any]:
    requester = None
    if requester_id:
        requester = session.get(User, requester_id)
    if requester is None:
        requester = session.exec(select(User).where(User.email == contact_email)).first()
    if requester is None:
        requester = session.exec(select(User).where(User.role == "requester")).first()
    if requester is None:
        raise HTTPException(status_code=400, detail="请先导入 demo 用户或创建 requester 用户")

    ticket = Ticket(
        requester_id=requester.id,
        title=title,
        description=description,
        user_category=user_category,
        urgency=urgency,
        affected_system=affected_system,
        status=TicketStatus.open,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    attachments: list[TicketAttachment] = []
    if screenshot and screenshot.filename:
        attachments.append(await save_upload_file(ticket.id, screenshot))
    if log_file and log_file.filename:
        attachments.append(await save_upload_file(ticket.id, log_file))
    for attachment in attachments:
        session.add(attachment)
    session.commit()

    session.add(_timeline(ticket.id, "created", f"{requester.name} 提交工单"))
    session.commit()
    return analyze_ticket(session, ticket, event_type="ai_triaged")


def get_ticket_detail(session: Session, ticket_id: int) -> dict[str, Any]:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    requester = session.get(User, ticket.requester_id)
    attachments = session.exec(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket_id)).all()
    timeline = session.exec(
        select(TicketTimelineEvent).where(TicketTimelineEvent.ticket_id == ticket_id).order_by(TicketTimelineEvent.created_at)
    ).all()
    tasks = session.exec(select(RemediationTask).where(RemediationTask.ticket_id == ticket_id)).all()
    admin_notes = session.exec(select(AdminNote).where(AdminNote.ticket_id == ticket_id).order_by(AdminNote.created_at.desc())).all()
    ai_review = session.exec(select(AIReview).where(AIReview.ticket_id == ticket_id).order_by(AIReview.created_at.desc())).first()
    ai_audits = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket_id).order_by(AIAnalysisAudit.created_at.desc())).all()
    current_chunk_ids = {int(chunk.id) for chunk in session.exec(select(KnowledgeBaseChunk)).all() if chunk.id is not None}

    def audit_dump(audit: AIAnalysisAudit) -> dict[str, Any]:
        payload = audit.model_dump()
        sources = []
        for source in payload.get("retrieved_sources", []):
            chunk_id = source.get("chunk_id")
            source["historical_snapshot"] = bool(chunk_id and chunk_id not in current_chunk_ids)
            sources.append(source)
        payload["retrieved_sources"] = sources
        return payload

    return {
        **ticket.model_dump(),
        "requester": requester.model_dump() if requester else None,
        "attachments": [item.model_dump() for item in attachments],
        "timeline": [item.model_dump() for item in timeline],
        "tasks": [item.model_dump() for item in tasks],
        "admin_notes": [item.model_dump() for item in admin_notes],
        "ai_review": ai_review.model_dump() if ai_review else None,
        "ai_analysis_audits": [audit_dump(item) for item in ai_audits],
    }


def list_tickets(
    session: Session,
    *,
    status: TicketStatus | None = None,
    severity: TicketSeverity | None = None,
    predicted_category: str | None = None,
    assigned_team: str | None = None,
    search: str | None = None,
    requester_id: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(Ticket).order_by(Ticket.created_at.desc())
    if requester_id is not None:
        statement = statement.where(Ticket.requester_id == requester_id)
    if status:
        statement = statement.where(Ticket.status == status)
    if severity:
        statement = statement.where(Ticket.severity == severity)
    if predicted_category:
        statement = statement.where(Ticket.predicted_category == predicted_category)
    if assigned_team:
        statement = statement.where(Ticket.assigned_team == assigned_team)
    tickets = session.exec(statement).all()
    if search:
        term = search.lower()
        tickets = [item for item in tickets if term in item.title.lower() or term in item.description.lower()]

    rows: list[dict[str, Any]] = []
    for ticket in tickets:
        requester = session.get(User, ticket.requester_id)
        attachment_count = session.exec(
            select(func.count()).select_from(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id)
        ).one()
        rows.append({**ticket.model_dump(), "requester": requester.model_dump() if requester else None, "attachment_count": attachment_count})
    return rows


def list_analysis_runs(session: Session, ticket_id: int) -> list[dict[str, Any]]:
    runs = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket_id).order_by(AIAnalysisAudit.created_at.desc())).all()
    return [run.model_dump() for run in runs]


def get_analysis_run(session: Session, ticket_id: int, run_id: str) -> dict[str, Any]:
    run = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket_id, AIAnalysisAudit.run_id == run_id)).first()
    if run is None:
        raise HTTPException(status_code=404, detail="分析运行不存在")
    return run.model_dump()


def get_analysis_trace(session: Session, ticket_id: int, run_id: str) -> dict[str, Any]:
    run = get_analysis_run(session, ticket_id, run_id)
    return {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "trace_id": run["trace_id"],
        "stage_traces": run["stage_traces"],
        "previous_diff": run.get("previous_diff") or {},
    }


def update_ticket(session: Session, ticket_id: int, payload: TicketUpdate) -> dict[str, Any]:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")

    changes = payload.model_dump(exclude_unset=True)
    internal_note = changes.pop("internal_note", None)
    user_reply = changes.pop("user_reply", None)

    for field, value in changes.items():
        setattr(ticket, field, value)
    ticket.updated_at = utc_now()
    session.add(ticket)

    if internal_note:
        session.add(AdminNote(ticket_id=ticket.id, author="管理员", content=internal_note))
        session.add(_timeline(ticket.id, "internal_note", "管理员添加内部备注"))
    if user_reply:
        session.add(_timeline(ticket.id, "admin_reply", user_reply))
    if "status" in changes:
        session.add(_timeline(ticket.id, "status_changed", f"状态更新为 {ticket.status.value}"))
    if "assigned_team" in changes:
        session.add(_timeline(ticket.id, "assigned", f"分配给 {ticket.assigned_team}"))
    if "severity" in changes:
        session.add(_timeline(ticket.id, "severity_changed", f"严重等级调整为 {ticket.severity.value}"))

    session.commit()
    return get_ticket_detail(session, ticket_id)


async def reanalyze_ticket(
    session: Session,
    ticket_id: int,
    screenshot: UploadFile | None = None,
    log_file: UploadFile | None = None,
) -> dict[str, Any]:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    new_attachments: list[TicketAttachment] = []
    if screenshot and screenshot.filename:
        new_attachments.append(await save_upload_file(ticket.id, screenshot))
    if log_file and log_file.filename:
        new_attachments.append(await save_upload_file(ticket.id, log_file))
    for attachment in new_attachments:
        session.add(attachment)
        session.add(_timeline(ticket.id, "attachment_added", f"新增附件：{attachment.file_name}，已触发重新分析"))
    if new_attachments:
        session.commit()
    return analyze_ticket(session, ticket, event_type="reanalyzed")
