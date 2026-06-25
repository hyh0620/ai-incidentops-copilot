from typing import Any

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import Principal, require_admin, require_ticket_access, resolve_principal
from app.evidence.redaction import redact_text
from app.models import AIAnalysisAudit, KBIngestionRun, Ticket, UserRole
from app.retrieval.service import retrieve_evidence_by_mode
from app.services.rag_service import index_status
from app.services.ticket_service import get_ticket_detail


class MCPAccessError(RuntimeError):
    pass


def _mcp_principal(session: Session, demo_user_id: int | None = None) -> Principal:
    user_id = demo_user_id if demo_user_id is not None else get_settings().mcp_demo_user_id
    if user_id is None:
        raise MCPAccessError("MCP_DEMO_USER_ID is required. Configure a demo persona before using IncidentOps MCP tools.")
    try:
        return resolve_principal(Principal(user_id=int(user_id)), session)
    except Exception as exc:
        raise MCPAccessError(str(exc)) from exc


def search_incident_knowledge(
    session: Session,
    *,
    query: str,
    top_k: int = 5,
    retrieval_mode: str = "hybrid_rrf",
    demo_user_id: int | None = None,
) -> dict[str, Any]:
    _mcp_principal(session, demo_user_id)
    if retrieval_mode not in {"bm25_only", "dense_only", "hybrid_rrf"}:
        raise MCPAccessError("retrieval_mode must be one of bm25_only, dense_only, hybrid_rrf")
    result = retrieve_evidence_by_mode(session, query=query, predicted_category=None, keywords=[], retrieval_mode=retrieval_mode)
    status = index_status(session)
    settings = get_settings()

    def safe_excerpt(value: Any) -> str:
        text = str(value or "")
        return redact_text(text, settings.redact_internal_ips).text if settings.enable_pii_redaction else text

    if retrieval_mode == "bm25_only":
        effective_provider = "not_used"
        model = None
        fallback_reason = None
    else:
        effective_provider = result.diagnostics.get("embedding_provider")
        model = result.diagnostics.get("embedding_model")
        fallback_reason = result.diagnostics.get("fallback_reason") or result.diagnostics.get("provider_error")
    return {
        "kb_version": status.get("kb_version") or "unknown",
        "retrieval_mode": retrieval_mode,
        "configured_embedding_provider": get_settings().embedding_provider,
        "effective_embedding_provider": effective_provider,
        "embedding_model": model,
        "fallback_reason": fallback_reason,
        "results": [
            {
                "chunk_id": str(source.chunk_id),
                "article_id": source.article_id,
                "title": source.title,
                "source_filename": source.metadata.get("source_filename"),
                "page_number": source.metadata.get("page_number"),
                "excerpt": safe_excerpt(source.metadata.get("evidence_excerpt") or source.excerpt),
                "final_score": float(source.metadata.get("final_score") or source.rerank_score or source.fusion_score or 0.0),
            }
            for source in result.final_sources[: max(1, min(top_k, 20))]
        ],
    }


def get_ticket_analysis(session: Session, *, ticket_id: int, demo_user_id: int | None = None) -> dict[str, Any]:
    principal = _mcp_principal(session, demo_user_id)
    try:
        require_ticket_access(ticket_id, principal, session)
    except Exception as exc:
        raise MCPAccessError(str(exc)) from exc
    detail = get_ticket_detail(session, ticket_id)
    latest_audit = session.exec(
        select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket_id).order_by(AIAnalysisAudit.created_at.desc())
    ).first()
    decision = latest_audit.final_decision if latest_audit else detail.get("ai_signals", {}).get("classification", {})
    review = detail.get("ai_review") or {}
    settings = get_settings()

    def safe_excerpt(value: Any) -> str:
        text = str(value or "")
        return redact_text(text, settings.redact_internal_ips).text if settings.enable_pii_redaction else text

    return {
        "ticket": {
            "id": detail.get("id"),
            "title": detail.get("title"),
            "status": detail.get("status"),
            "predicted_category": detail.get("predicted_category"),
            "severity": detail.get("severity"),
            "confidence": detail.get("confidence"),
            "created_at": str(detail.get("created_at")),
        },
        "analysis": {
            "run_id": latest_audit.run_id if latest_audit else None,
            "trace_id": latest_audit.trace_id if latest_audit else None,
            "provider": latest_audit.provider if latest_audit else decision.get("provider"),
            "model_name": decision.get("model_name"),
            "severity": decision.get("severity"),
            "confidence": decision.get("confidence"),
            "fallback_reason": decision.get("fallback_reason"),
            "llm_validation_status": decision.get("llm_validation_status"),
            "review_reasons": decision.get("review_reasons", []),
        },
        "evidence": [
            {
                "id": item.get("id"),
                "source_type": item.get("source_type"),
                "source_name": item.get("source_name"),
                "excerpt": safe_excerpt(item.get("excerpt")),
                "redacted": True if item.get("redacted") else safe_excerpt(item.get("excerpt")) != str(item.get("excerpt") or ""),
                "signal_tags": item.get("signal_tags", []),
            }
            for item in ((latest_audit.evidence if latest_audit else []) or [])
        ],
        "cited_chunks": [
            {
                "chunk_id": source.get("chunk_id"),
                "article_id": source.get("article_id"),
                "title": source.get("title"),
                "excerpt": safe_excerpt(source.get("evidence_excerpt") or source.get("evidence_excerpt_snapshot") or source.get("chunk_summary")),
                "final_score": source.get("final_score"),
            }
            for source in ((latest_audit.retrieved_sources if latest_audit else []) or [])
        ],
        "trace": [
            {
                "name": stage.get("name"),
                "status": stage.get("status"),
                "provider": stage.get("provider"),
                "duration_ms": stage.get("duration_ms"),
                "error": stage.get("error"),
                "output_summary": stage.get("output_summary"),
            }
            for stage in ((latest_audit.stage_traces if latest_audit else []) or [])
        ],
        "review": {
            "status": review.get("status"),
            "reasons": review.get("review_reasons", decision.get("review_reasons", [])),
        },
    }


def get_kb_index_status(session: Session, *, demo_user_id: int | None = None) -> dict[str, Any]:
    principal = _mcp_principal(session, demo_user_id)
    try:
        require_admin(principal, session)
    except Exception as exc:
        raise MCPAccessError(str(exc)) from exc
    status = index_status(session)
    manifest = status.get("manifest") or {}
    latest_run = status.get("latest_ingestion_run") or {}
    return {
        "kb_version": status.get("kb_version"),
        "article_count": status.get("article_count"),
        "chunk_count": status.get("chunk_count"),
        "configured_embedding_provider": get_settings().embedding_provider,
        "effective_embedding_provider": manifest.get("provider"),
        "embedding_model": manifest.get("embedding_model"),
        "fallback_reason": manifest.get("fallback_reason") or manifest.get("provider_error"),
        "latest_ingestion_run": latest_run,
        "latest_rebuild_at": manifest.get("rebuilt_at"),
        "ready": status.get("ready"),
        "stale": status.get("stale"),
    }


def list_ingestion_runs(session: Session, *, limit: int = 20, demo_user_id: int | None = None) -> dict[str, Any]:
    principal = _mcp_principal(session, demo_user_id)
    try:
        require_admin(principal, session)
    except Exception as exc:
        raise MCPAccessError(str(exc)) from exc
    runs = session.exec(select(KBIngestionRun).order_by(KBIngestionRun.started_at.desc()).limit(max(1, min(limit, 50)))).all()
    return {
        "runs": [
            {
                "id": run.id,
                "source_filename": run.source_filename,
                "source_type": run.source_type,
                "status": run.status,
                "document_count": run.document_count,
                "chunk_count": run.chunk_count,
                "embedding_provider": run.embedding_provider,
                "embedding_model": run.embedding_model,
                "kb_version": run.kb_version,
                "latency_ms": run.latency_ms,
                "fallback_reason": run.fallback_reason,
                "error_message": run.error_message,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs
        ],
    }


def mcp_readonly_counts(session: Session, *, demo_user_id: int | None = None) -> dict[str, int]:
    principal = _mcp_principal(session, demo_user_id)
    before = {
        "tickets": len(session.exec(select(Ticket)).all()),
        "ingestion_runs": len(session.exec(select(KBIngestionRun)).all()),
    }
    if principal.role != UserRole.admin:
        before["visible_tickets"] = len(session.exec(select(Ticket).where(Ticket.requester_id == principal.user_id)).all())
    else:
        before["visible_tickets"] = before["tickets"]
    return before
