import asyncio
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import KnowledgeBaseArticle, Ticket, TicketAttachment, TicketTimelineEvent, User
from app.services.incident_classifier import classify_incident
from app.services.multimodal_analyzer import analyze_screenshot_with_vision_model, combine_multimodal_signals
from app.services.rag_service import hybrid_search_articles, rebuild_kb_index
from app.services.ticket_service import reanalyze_ticket


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_article(session: Session, title: str, category: str, content: str, tags: list[str]) -> KnowledgeBaseArticle:
    article = KnowledgeBaseArticle(
        title=title,
        category=category,
        summary=content[:120],
        content=content,
        tags=tags,
        reading_time=3,
    )
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def test_vpn_query_returns_vpn_kb_top_k(session: Session, tmp_path: Path):
    add_article(
        session,
        "VPN 无法连接",
        "网络连接",
        "VPN cannot connect 时检查客户端版本、证书、MFA 认证状态和 network gateway 日志。",
        ["vpn", "network", "cannot connect"],
    )
    add_article(session, "密码重置失败", "账号权限", "password reset failed and login denied", ["password", "login"])
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)

    results = hybrid_search_articles(session, "VPN cannot connect from home network", top_k=3, index_dir=tmp_path, force_fallback=True)

    assert results[0]["title"] == "VPN 无法连接"
    assert "VPN" in results[0]["evidence_excerpt"]
    assert results[0]["chunk_id"]


def test_database_timeout_retrieval_and_classification_include_evidence(session: Session, tmp_path: Path):
    add_article(
        session,
        "数据库连接超时",
        "软件系统",
        "database connection timeout 时检查连接池、慢查询、JDBC 配置和网络连通性。",
        ["database", "timeout"],
    )
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)
    log_text = "ERROR DatabaseTimeoutException HTTP 500 database connection timeout"
    signals = combine_multimodal_signals(
        title="Database connection timeout",
        description="API failed after deployment",
        affected_system="订单数据库",
        log_file_name="app.log",
        log_content=log_text,
    )
    classification = classify_incident("Database connection timeout", "API failed", "数据库", "高", "订单数据库", signals, log_text)
    results = hybrid_search_articles(session, "Database connection timeout " + log_text, "软件系统", signals["detected_keywords"], index_dir=tmp_path, force_fallback=True)

    assert classification["predicted_category"] == "软件系统"
    assert classification["evidence"]
    assert results[0]["title"] == "数据库连接超时"
    assert "timeout" in results[0]["evidence_excerpt"].lower()


def test_reanalyze_adds_timeline_event(session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    add_article(session, "数据库连接超时", "软件系统", "database timeout troubleshooting", ["database", "timeout"])
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)
    import app.services.rag_service as rag_service

    monkeypatch.setattr(rag_service, "DEFAULT_INDEX_DIR", tmp_path)
    user = User(name="测试用户", email="test@example.com", role="requester", department="研发")
    session.add(user)
    session.commit()
    session.refresh(user)
    ticket = Ticket(
        requester_id=user.id,
        title="Database connection timeout",
        description="batch job failed with timeout",
        user_category="数据库",
        urgency="高",
        affected_system="批处理平台",
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    log_path = tmp_path / "app.log"
    log_path.write_text("ERROR DatabaseTimeoutException database timeout HTTP 500", encoding="utf-8")
    session.add(TicketAttachment(ticket_id=ticket.id, file_name="app.log", file_path=str(log_path), file_type="log"))
    session.commit()

    asyncio.run(reanalyze_ticket(session, ticket.id))

    events = session.exec(select(TicketTimelineEvent).where(TicketTimelineEvent.ticket_id == ticket.id)).all()
    assert any(event.event_type == "reanalyzed" for event in events)


def test_ocr_failure_degrades_without_exception():
    result = analyze_screenshot_with_vision_model("missing.png", "/path/does/not/exist.png")

    assert result["ocr_status"] in {"failed", "unavailable"}
    assert result["extracted_text"] == ""
    assert result["error"]


def test_high_confidence_requires_evidence():
    result = classify_incident(
        title="phishing suspicious unauthorized malware unknown login",
        description="",
        user_category="安全风险",
        urgency="高",
        affected_system="SSO",
        multimodal_signals={"detected_keywords": ["phishing", "suspicious", "unauthorized", "malware"], "evidence": []},
    )

    assert result["confidence"] <= 0.69
    assert result["uncertainty"]
