from typing import Literal

from mcp.server.fastmcp import FastMCP

from app.database import get_session
from app.mcp_tools import (
    get_kb_index_status as get_kb_index_status_impl,
    get_ticket_analysis as get_ticket_analysis_impl,
    list_ingestion_runs as list_ingestion_runs_impl,
    search_incident_knowledge as search_incident_knowledge_impl,
)


mcp = FastMCP(
    "AI IncidentOps Copilot",
    instructions="Read-only IncidentOps tools. Requires MCP_DEMO_USER_ID in the server environment.",
)


def _with_session():
    session_generator = get_session()
    session = next(session_generator)
    return session, session_generator


@mcp.tool()
def search_incident_knowledge(query: str, top_k: int = 5, retrieval_mode: Literal["bm25_only", "dense_only", "hybrid_rrf"] = "hybrid_rrf") -> dict:
    """Search the IncidentOps knowledge base with existing BM25, dense, or hybrid retrieval."""
    session, session_generator = _with_session()
    try:
        return search_incident_knowledge_impl(session, query=query, top_k=top_k, retrieval_mode=retrieval_mode)
    finally:
        session_generator.close()


@mcp.tool()
def get_ticket_analysis(ticket_id: int) -> dict:
    """Return a redacted ticket analysis summary, cited chunks, trace summary, and review reasons."""
    session, session_generator = _with_session()
    try:
        return get_ticket_analysis_impl(session, ticket_id=ticket_id)
    finally:
        session_generator.close()


@mcp.tool()
def get_kb_index_status() -> dict:
    """Return the current knowledge-base index status. Requires an Admin demo persona."""
    session, session_generator = _with_session()
    try:
        return get_kb_index_status_impl(session)
    finally:
        session_generator.close()


@mcp.tool()
def list_ingestion_runs(limit: int = 20) -> dict:
    """List recent knowledge-base ingestion runs. Requires an Admin demo persona."""
    session, session_generator = _with_session()
    try:
        return list_ingestion_runs_impl(session, limit=limit)
    finally:
        session_generator.close()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
