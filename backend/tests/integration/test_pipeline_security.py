import asyncio
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AIAnalysisAudit, AttachmentFileType, KnowledgeBaseArticle, Ticket, TicketAttachment, TicketTimelineEvent, User, UserRole
from app.services.rag_service import index_status, rebuild_kb_index
from app.services.ticket_service import reanalyze_ticket


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_index_stale_then_rebuild_ready(tmp_path: Path):
    session = _session()
    session.add(
        KnowledgeBaseArticle(
            title="VPN 无法连接",
            category="网络连接",
            summary="vpn",
            content="VPN cannot connect network timeout",
            tags=["vpn"],
        )
    )
    session.commit()

    before = index_status(session, index_dir=tmp_path)
    manifest = rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)
    after = index_status(session, index_dir=tmp_path)

    assert before["ready"] is False
    assert manifest["build_status"] == "ready"
    assert after["ready"] is True


def test_pipeline_trace_redacts_sensitive_log_tokens(tmp_path: Path, monkeypatch):
    import app.services.rag_service as rag_service

    session = _session()
    session.add(User(id=1, name="测试用户", email="test@example.com", role=UserRole.requester, department="研发"))
    session.add(
        KnowledgeBaseArticle(
            title="生产 API 返回 500 错误",
            category="软件系统",
            summary="api 500",
            content="API 500 exception timeout troubleshooting",
            tags=["api", "500"],
        )
    )
    session.commit()
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)
    monkeypatch.setattr(rag_service, "DEFAULT_INDEX_DIR", tmp_path)

    ticket = Ticket(requester_id=1, title="API 500", description="production API 500", user_category="软件系统", urgency="高")
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    log_text = "ERROR HTTP 500 password=Secret123 Bearer abcdefghijklmnop"
    log_path = tmp_path / "api.log"
    log_path.write_text(log_text, encoding="utf-8")
    session.add(TicketAttachment(ticket_id=ticket.id, file_name="api.log", file_path=str(log_path), file_type=AttachmentFileType.log))
    session.commit()

    asyncio.run(reanalyze_ticket(session, ticket.id))
    audit = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket.id)).first()

    serialized = str(audit.evidence) + str(audit.stage_traces) + str(audit.final_decision)
    assert "Secret123" not in serialized
    assert "abcdefghijklmnop" not in serialized
    assert audit.trace_id
    assert audit.source_chunk_ids
    names = [stage["name"] for stage in audit.stage_traces]
    assert "dense_candidate_retrieval" in names
    assert "bm25_lexical_retrieval" in names
    assert "rrf_fusion" in names
    assert "rerank" in names
    assert "evidence_thresholding" in names
    rerank_stage = next(stage for stage in audit.stage_traces if stage["name"] == "rerank")
    assert rerank_stage["status"] in {"success", "skipped"}
    assert rerank_stage["duration_ms"] >= 0


def test_reanalyze_creates_new_run_not_overwriting(tmp_path: Path, monkeypatch):
    import app.services.rag_service as rag_service

    session = _session()
    session.add(User(id=1, name="测试用户", email="test@example.com", role=UserRole.requester, department="研发"))
    session.add(KnowledgeBaseArticle(title="数据库连接超时", category="软件系统", summary="db", content="database timeout", tags=["database"]))
    session.commit()
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)
    monkeypatch.setattr(rag_service, "DEFAULT_INDEX_DIR", tmp_path)
    ticket = Ticket(requester_id=1, title="Database timeout", description="database timeout", user_category="数据库", urgency="高")
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    asyncio.run(reanalyze_ticket(session, ticket.id))
    asyncio.run(reanalyze_ticket(session, ticket.id))
    audits = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket.id)).all()
    events = session.exec(select(TicketTimelineEvent).where(TicketTimelineEvent.ticket_id == ticket.id)).all()

    assert len(audits) == 2
    assert len({audit.run_id for audit in audits}) == 2
    assert any(event.event_type == "reanalyzed" for event in events)
