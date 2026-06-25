import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.mcp_tools import (
    MCPAccessError,
    get_kb_index_status,
    get_ticket_analysis,
    list_ingestion_runs,
    mcp_readonly_counts,
    search_incident_knowledge,
)
from app.models import AIAnalysisAudit, KBIngestionRun, KnowledgeBaseArticle, Ticket, User, UserRole
from app.services.rag_service import rebuild_kb_index


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _session(tmp_path: Path) -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    _seed(session)
    _rebuild(session, tmp_path)
    return session


def _seed(session: Session) -> Ticket:
    session.add_all(
        [
            User(id=1, name="Requester A", email="a@example.com", role=UserRole.requester, department="A"),
            User(id=2, name="Requester B", email="b@example.com", role=UserRole.requester, department="B"),
            User(id=7, name="Admin", email="admin@example.com", role=UserRole.admin, department="IT"),
            KnowledgeBaseArticle(
                title="VPN 无法连接",
                category="网络连接",
                summary="VPN 连接故障",
                content="VPN cannot connect network timeout gateway troubleshooting",
                tags=["vpn", "network"],
            ),
        ]
    )
    session.commit()
    ticket = Ticket(
        requester_id=1,
        title="VPN cannot connect",
        description="VPN cannot connect Bearer abcdefghijklmnop password=Secret123",
        user_category="网络连接",
        urgency="中",
        predicted_category="网络连接",
        confidence=0.8,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    session.add(
        AIAnalysisAudit(
            ticket_id=ticket.id,
            run_id="run-fixture",
            trace_id="trace-fixture",
            provider="rule_fallback",
            retrieval_mode="local hybrid retrieval",
            final_decision={
                "predicted_category": "网络连接",
                "severity": "medium",
                "confidence": 0.8,
                "provider": "rule_fallback",
                "review_reasons": [],
                "fallback_reason": None,
                "llm_validation_status": None,
            },
            evidence=[
                {
                    "id": "ev-log-1",
                    "source_type": "log",
                    "source_name": "vpn.log",
                    "excerpt": "VPN failed Bearer abcdefghijklmnop password=Secret123",
                    "redacted": False,
                    "signal_tags": ["vpn"],
                }
            ],
            retrieved_sources=[
                {
                    "chunk_id": 1,
                    "article_id": 1,
                    "title": "VPN 无法连接",
                    "evidence_excerpt": "VPN cannot connect network timeout",
                    "final_score": 0.8,
                }
            ],
            stage_traces=[
                {
                    "name": "final_triage",
                    "status": "success",
                    "provider": "rule_fallback",
                    "duration_ms": 1.0,
                    "output_summary": "provider=rule_fallback",
                }
            ],
            source_chunk_ids=[1],
        )
    )
    session.add(KBIngestionRun(source_filename="vpn.md", source_type="md", status="completed", document_count=1, chunk_count=1))
    session.commit()
    return ticket


def _rebuild(session: Session, tmp_path: Path) -> None:
    import app.services.rag_service as rag_service

    rag_service.DEFAULT_INDEX_DIR = tmp_path / "index"
    rebuild_kb_index(session, index_dir=rag_service.DEFAULT_INDEX_DIR, force_fallback=True)


def test_mcp_tools_fail_closed_without_demo_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MCP_DEMO_USER_ID", raising=False)
    get_settings.cache_clear()
    session = _session(tmp_path)

    with pytest.raises(MCPAccessError):
        get_kb_index_status(session)


def test_mcp_search_reuses_retrieval_and_is_read_only(tmp_path: Path):
    session = _session(tmp_path)
    before = mcp_readonly_counts(session, demo_user_id=1)

    bm25 = search_incident_knowledge(session, query="VPN cannot connect", retrieval_mode="bm25_only", demo_user_id=1)
    result = search_incident_knowledge(session, query="VPN cannot connect network timeout", retrieval_mode="hybrid_rrf", demo_user_id=1)
    after = mcp_readonly_counts(session, demo_user_id=1)

    assert bm25["retrieval_mode"] == "bm25_only"
    assert bm25["effective_embedding_provider"] == "not_used"
    assert result["results"]
    assert result["results"][0]["title"] == "VPN 无法连接"
    assert before == after


def test_mcp_ticket_access_and_redaction(tmp_path: Path):
    session = _session(tmp_path)
    ticket = session.exec(select(Ticket).where(Ticket.requester_id == 1)).one()

    own = get_ticket_analysis(session, ticket_id=ticket.id, demo_user_id=1)
    admin = get_ticket_analysis(session, ticket_id=ticket.id, demo_user_id=7)

    with pytest.raises(MCPAccessError):
        get_ticket_analysis(session, ticket_id=ticket.id, demo_user_id=2)

    serialized = json.dumps(own, ensure_ascii=False) + json.dumps(admin, ensure_ascii=False)
    assert "Secret123" not in serialized
    assert "abcdefghijklmnop" not in serialized
    assert "[REDACTED_PASSWORD]" in serialized


def test_mcp_admin_only_tools(tmp_path: Path):
    session = _session(tmp_path)

    with pytest.raises(MCPAccessError):
        get_kb_index_status(session, demo_user_id=1)
    with pytest.raises(MCPAccessError):
        list_ingestion_runs(session, demo_user_id=1)

    status = get_kb_index_status(session, demo_user_id=7)
    runs = list_ingestion_runs(session, demo_user_id=7)

    assert status["article_count"] == 1
    assert runs["runs"][0]["source_filename"] == "vpn.md"


def test_mcp_server_stdio_lists_and_calls_tools(tmp_path: Path):
    db_path = tmp_path / "mcp.db"
    index_dir = tmp_path / "index"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        import app.services.rag_service as rag_service

        rag_service.DEFAULT_INDEX_DIR = index_dir
        rebuild_kb_index(session, index_dir=index_dir, force_fallback=True)

    async def run_client() -> None:
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{db_path}",
            "VECTOR_INDEX_DIR": str(index_dir),
            "MCP_DEMO_USER_ID": "7",
            "EMBEDDING_PROVIDER": "local_hash_embedding_fallback",
        }
        params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(Path.cwd()), env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {"search_incident_knowledge", "get_ticket_analysis", "get_kb_index_status", "list_ingestion_runs"} <= names
                result = await client.call_tool(
                    "search_incident_knowledge",
                    {"query": "VPN cannot connect network timeout", "retrieval_mode": "hybrid_rrf", "top_k": 3},
                )
                payload = json.loads(result.content[0].text)
                assert payload["retrieval_mode"] == "hybrid_rrf"
                assert payload["results"][0]["title"] == "VPN 无法连接"

    asyncio.run(run_client())
