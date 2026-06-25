import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.core.config import get_settings
from app.evaluation.metrics import hit_rate_at_k, mrr, ndcg_at_k, summarize_latencies
from app.models import AIAnalysisAudit, AttachmentFileType, KnowledgeBaseArticle, Ticket, TicketAttachment, User, UserRole
from app.retrieval.service import retrieve_evidence_by_mode
from app.seed import KB_ARTICLES
from app.services import rag_service
from app.services.rag_service import rebuild_kb_index
from app.services.ticket_service import analyze_ticket


EVIDENCE_TERM_SYNONYMS = {
    "cannot connect": ["无法连接", "连接"],
    "timeout": ["超时", "请求超时", "连接超时"],
    "database": ["数据库"],
    "databasetimeoutexception": ["数据库", "连接超时"],
    "exception": ["异常"],
    "api": ["API", "接口"],
    "mfa": ["MFA", "多因素认证", "验证码"],
    "login": ["登录"],
    "phishing": ["钓鱼"],
    "suspicious": ["可疑"],
    "unknown login": ["未知登录", "异地登录", "可疑登录"],
    "unauthorized": ["未授权", "未授权访问"],
    "malware": ["恶意软件"],
    "disk": ["磁盘"],
    "server": ["服务器"],
    "access denied": ["访问被拒绝", "权限拒绝"],
    "password": ["密码"],
    "failed": ["失败"],
    "pipeline": ["流水线"],
    "policy": ["策略"],
    "blocked": ["阻止"],
}


def _expanded_terms(terms: list[str]) -> list[str]:
    expanded: list[str] = []
    for term in terms:
        lowered = term.lower()
        expanded.append(lowered)
        expanded.extend(item.lower() for item in EVIDENCE_TERM_SYNONYMS.get(lowered, []))
    return expanded


def _load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_session(tmp_dir: Path, force_fallback: bool) -> tuple[Session, dict[str, Any]]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    session.add(User(id=1, name="Fixture User", email="fixture@example.com", role=UserRole.requester, department="Benchmark"))
    session.add_all([KnowledgeBaseArticle(**article) for article in KB_ARTICLES])
    session.commit()

    rag_service.DEFAULT_INDEX_DIR = tmp_dir / "eval_index"
    manifest = rebuild_kb_index(session, index_dir=rag_service.DEFAULT_INDEX_DIR, force_fallback=force_fallback)
    return session, manifest


def _citation_supported(row: dict[str, Any]) -> bool:
    expected_titles = set(row.get("expected_titles", []))
    if not expected_titles:
        return bool(row.get("insufficient_evidence") or not row.get("source_titles"))
    excerpts_text = "\n".join(row.get("source_excerpts", [])).lower()
    terms = _expanded_terms([str(term) for term in row.get("expected_evidence_terms", [])])
    title_supported = bool(expected_titles & set(row.get("source_titles", [])))
    term_supported = any(term.lower() in excerpts_text for term in terms) if terms else title_supported
    return title_supported and term_supported


def _unsupported_citation_count(row: dict[str, Any]) -> int:
    expected_titles = set(row.get("expected_titles", []))
    terms = _expanded_terms([str(term) for term in row.get("expected_evidence_terms", [])])
    unsupported = 0
    for result in row.get("top_k_results", []):
        title = result.get("title")
        excerpt = str(result.get("evidence_excerpt") or result.get("chunk_summary") or "").lower()
        if expected_titles and (title in expected_titles or any(term.lower() in excerpt for term in terms)):
            continue
        unsupported += 1
    return unsupported


def _summarize_retrieval_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
    citation_count = sum(len(row.get("top_k_results", [])) for row in rows)
    unsupported_count = sum(row.get("unsupported_citation_count", 0) for row in rows)
    first = rows[0] if rows else {}
    return {
        "HitRate@1": round(hit_rate_at_k(rows, 1), 4),
        "HitRate@3": round(hit_rate_at_k(rows, 3), 4),
        "HitRate@5": round(hit_rate_at_k(rows, 5), 4),
        "MRR": round(mrr(rows), 4),
        "nDCG@3": round(ndcg_at_k(rows, 3), 4),
        "EvidencePrecision": round((citation_count - unsupported_count) / citation_count, 4) if citation_count else 1.0,
        "UnsupportedCitationRate": round(unsupported_count / citation_count, 4) if citation_count else 0.0,
        "avg_latency_ms": round(sum(row.get("latency_ms", 0.0) for row in rows) / len(rows), 2) if rows else 0.0,
        "configured_embedding_provider": first.get("configured_embedding_provider"),
        "effective_dense_provider": first.get("effective_dense_provider"),
        "effective_embedding_provider": first.get("effective_embedding_provider"),
        "embedding_provider": first.get("effective_embedding_provider"),
        "embedding_model": first.get("embedding_model"),
        "fallback_reason": first.get("fallback_reason"),
        "case_count": len(rows),
    }


def run_evaluation(
    dataset_path: Path,
    artifacts_dir: Path,
    embedding_provider_override: str | None = None,
) -> dict[str, Any]:
    if embedding_provider_override:
        os.environ["EMBEDDING_PROVIDER"] = embedding_provider_override
        get_settings.cache_clear()
        rag_service.clear_embedding_backend_cache()
    settings = get_settings()
    configured_embedding_provider = settings.embedding_provider
    force_embedding_fallback = configured_embedding_provider == "local_hash_embedding_fallback"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    retrieval_mode_rows: dict[str, list[dict[str, Any]]] = {"bm25_only": [], "dense_only": [], "hybrid_rrf": []}
    all_stages: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp_dir = Path(raw_tmp)
        session, manifest = _prepare_session(tmp_dir, force_fallback=force_embedding_fallback)
        dataset_base = Path.cwd()
        article_ids_by_title = {article.title: article.id for article in session.exec(select(KnowledgeBaseArticle)).all()}
        for case in _load_cases(dataset_path):
            expected_article_ids = [
                article_ids_by_title[title]
                for title in case.get("expected_source_titles", [])
                if title in article_ids_by_title
            ]
            retrieval_query = "\n".join(
                str(case.get(key) or "")
                for key in ["title", "description", "log_text", "ocr_text"]
                if case.get(key)
            )
            for retrieval_mode in retrieval_mode_rows:
                start = time.perf_counter()
                retrieval_result = retrieve_evidence_by_mode(
                    session,
                    query=retrieval_query,
                    predicted_category=None,
                    keywords=[],
                    retrieval_mode=retrieval_mode,
                    force_fallback=force_embedding_fallback,
                )
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                top_results = [candidate.metadata for candidate in retrieval_result.final_sources[:5]]
                if retrieval_mode == "bm25_only":
                    effective_dense_provider = "not_used"
                    effective_embedding_provider = "not_used"
                    embedding_model = None
                    fallback_reason = None
                else:
                    effective_dense_provider = retrieval_result.diagnostics.get("embedding_provider")
                    effective_embedding_provider = effective_dense_provider
                    embedding_model = retrieval_result.diagnostics.get("embedding_model")
                    fallback_reason = retrieval_result.diagnostics.get("fallback_reason") or retrieval_result.diagnostics.get(
                        "provider_error"
                    )
                mode_row = {
                    "id": case["id"],
                    "query": retrieval_query,
                    "expected_article_ids": expected_article_ids,
                    "expected_titles": list(case.get("expected_source_titles", [])),
                    "expected_evidence_terms": list(case.get("expected_evidence_terms", [])),
                    "source_titles": [result.get("title") for result in top_results if result.get("title")],
                    "source_excerpts": [str(result.get("evidence_excerpt") or result.get("chunk_summary") or "") for result in top_results],
                    "top_k_results": top_results,
                    "insufficient_evidence": retrieval_result.insufficient_evidence,
                    "retrieval_mode": retrieval_mode,
                    "configured_embedding_provider": configured_embedding_provider,
                    "effective_dense_provider": effective_dense_provider,
                    "effective_embedding_provider": effective_embedding_provider,
                    "embedding_provider": effective_embedding_provider,
                    "embedding_model": embedding_model,
                    "fallback_reason": fallback_reason,
                    "latency_ms": latency_ms,
                    "hit": False,
                }
                mode_row["citation_grounded"] = _citation_supported(mode_row)
                mode_row["unsupported_citation_count"] = _unsupported_citation_count(mode_row)
                mode_row["hit"] = bool(mode_row["citation_grounded"])
                retrieval_mode_rows[retrieval_mode].append(mode_row)

            description = case["description"]
            ticket = Ticket(
                requester_id=1,
                title=case["title"],
                description=description,
                user_category="其他",
                urgency="高" if case["expected_severity"] in {"high", "critical"} else "中",
                affected_system="fixture benchmark",
            )
            session.add(ticket)
            session.commit()
            session.refresh(ticket)
            if case.get("log_text"):
                log_path = tmp_dir / f"{case['id']}.log"
                log_path.write_text(case["log_text"], encoding="utf-8")
                session.add(
                    TicketAttachment(
                        ticket_id=ticket.id,
                        file_name=log_path.name,
                        file_path=str(log_path),
                        file_type=AttachmentFileType.log,
                        mime_type="text/plain",
                        size_bytes=len(case["log_text"].encode("utf-8")),
                    )
                )
                session.commit()
            if case.get("screenshot_fixture"):
                source_path = dataset_base / case["screenshot_fixture"]
                if source_path.exists():
                    target_path = tmp_dir / f"{case['id']}.png"
                    shutil.copyfile(source_path, target_path)
                else:
                    target_path = tmp_dir / f"missing-{case['id']}.png"
                session.add(
                    TicketAttachment(
                        ticket_id=ticket.id,
                        file_name=target_path.name,
                        file_path=str(target_path),
                        file_type=AttachmentFileType.screenshot,
                        mime_type="image/png",
                        size_bytes=target_path.stat().st_size if target_path.exists() else 0,
                    )
                )
                session.commit()
            result = analyze_ticket(session, ticket, event_type="benchmark_analyzed")
            detail = session.get(Ticket, ticket.id)
            sources = detail.related_kb_articles if detail else []
            source_titles = [source.get("title") for source in sources]
            source_excerpts = [str(source.get("evidence_excerpt") or source.get("chunk_summary") or "") for source in sources]
            final_decision = (detail.ai_signals or {}).get("classification", {}) if detail else {}
            stages = []
            evidence_items = []
            audit = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket.id)).first()
            if audit:
                stages = audit.stage_traces
                all_stages.extend(stages)
                final_decision = audit.final_decision
                evidence_items = audit.evidence
            expected_terms = _expanded_terms([str(term) for term in case.get("expected_evidence_terms", [])])
            expected_titles = set(case.get("expected_source_titles", []))
            insufficient = bool(audit and audit.final_decision.get("review_reasons") and "insufficient_retrieval_evidence" in audit.final_decision.get("review_reasons", []))
            excerpts_text = "\n".join(source_excerpts).lower()
            title_supported = bool(expected_titles & set(title for title in source_titles if title))
            term_supported = any(term.lower() in excerpts_text for term in expected_terms) if expected_terms else bool(expected_titles)
            if not expected_titles:
                supported = bool(insufficient or not source_titles)
            else:
                supported = title_supported and term_supported
            unsupported_citations = 0
            for title, excerpt in zip(source_titles, source_excerpts):
                excerpt_l = excerpt.lower()
                if expected_titles and (title in expected_titles or any(term in excerpt_l for term in expected_terms)):
                    continue
                unsupported_citations += 1
            ocr_statuses = [
                str(item.get("metadata", {}).get("ocr_status"))
                for item in evidence_items
                if item.get("source_type") == "ocr"
            ]
            rows.append(
                {
                    "id": case["id"],
                    "expected_titles": list(expected_titles),
                    "expected_article_ids": expected_article_ids,
                    "source_titles": [title for title in source_titles if title],
                    "source_excerpts": source_excerpts,
                    "insufficient_evidence": insufficient,
                    "expected_category": case["expected_category"],
                    "predicted_category": result["predicted_category"],
                    "expected_severity": case["expected_severity"],
                    "severity": result["severity"].value if hasattr(result["severity"], "value") else str(result["severity"]),
                    "requires_human_review": case["requires_human_review"],
                    "actual_review": bool(final_decision.get("requires_human_review")),
                    "confidence": result["confidence"],
                    "citation_grounded": supported,
                    "unsupported_citation_count": unsupported_citations,
                    "citation_count": len(source_titles),
                    "provider": result.get("provider"),
                    "retrieval_mode": result.get("retrieval_mode"),
                    "ocr_statuses": ocr_statuses,
                    "stage_count": len(stages),
                }
            )
        session.close()

    total = len(rows)
    category_accuracy = sum(row["predicted_category"] == row["expected_category"] for row in rows) / total if total else 0.0
    severity_exact = sum(row["severity"] == row["expected_severity"] for row in rows) / total if total else 0.0
    review_cases = [row for row in rows if row["requires_human_review"]]
    review_recall = sum(row["actual_review"] for row in review_cases) / len(review_cases) if review_cases else 0.0
    auto_approved_review_cases = [row for row in rows if row["requires_human_review"] and not row["actual_review"]]
    false_auto_approval_rate = len(auto_approved_review_cases) / len(review_cases) if review_cases else 0.0
    citation_grounding = sum(row["citation_grounded"] for row in rows) / total if total else 0.0
    insufficient_rate = sum(not row["source_titles"] for row in rows) / total if total else 0.0
    mode_summaries = {mode: _summarize_retrieval_mode(mode_rows) for mode, mode_rows in retrieval_mode_rows.items()}
    hybrid_summary = mode_summaries["hybrid_rrf"]
    global_provider_metadata = {
        "configured_embedding_provider": configured_embedding_provider,
        "effective_embedding_provider": manifest.get("provider"),
        "embedding_model": manifest.get("embedding_model"),
        "fallback_reason": manifest.get("fallback_reason") or manifest.get("provider_error"),
    }
    ocr_success = sum("success" in row["ocr_statuses"] or "no_text_detected" in row["ocr_statuses"] for row in rows)
    ocr_failed = sum("failed" in row["ocr_statuses"] for row in rows)
    ocr_degraded = sum(any(status in {"failed", "unavailable"} for status in row["ocr_statuses"]) for row in rows)
    ocr_exercised = sum(bool(row["ocr_statuses"]) for row in rows)
    report = {
        "dataset": str(dataset_path),
        "dataset_version": "fixture-benchmark-v2",
        "case_count": total,
        "configured_embedding_provider": global_provider_metadata["configured_embedding_provider"],
        "effective_embedding_provider": global_provider_metadata["effective_embedding_provider"],
        "embedding_model": global_provider_metadata["embedding_model"],
        "fallback_reason": global_provider_metadata["fallback_reason"],
        "thresholds": {
            "min_category_accuracy": settings.evaluation_min_category_accuracy,
            "min_hitrate_at_3": settings.evaluation_min_hitrate_at_3,
            "min_severity_exact_match": settings.evaluation_min_severity_exact_match,
            "min_security_review_recall": settings.evaluation_min_security_review_recall,
            "min_citation_grounding_rate": settings.evaluation_min_citation_grounding_rate,
            "max_false_auto_approval_rate": settings.evaluation_max_false_auto_approval_rate,
            "source": "baseline fixture run; non-zero guardrail for default offline workflow",
        },
        "retrieval": {
            "HitRate@1": hybrid_summary["HitRate@1"],
            "HitRate@3": hybrid_summary["HitRate@3"],
            "HitRate@5": hybrid_summary["HitRate@5"],
            "MRR": hybrid_summary["MRR"],
            "nDCG@3": hybrid_summary["nDCG@3"],
            "EvidenceCoverage": round(citation_grounding, 4),
            "EvidencePrecision": hybrid_summary["EvidencePrecision"],
            "UnsupportedCitationRate": hybrid_summary["UnsupportedCitationRate"],
            "InsufficientEvidenceRate": round(insufficient_rate, 4),
            "avg_latency_ms": hybrid_summary["avg_latency_ms"],
            "configured_embedding_provider": global_provider_metadata["configured_embedding_provider"],
            "effective_embedding_provider": global_provider_metadata["effective_embedding_provider"],
            "embedding_provider": global_provider_metadata["effective_embedding_provider"],
            "embedding_model": global_provider_metadata["embedding_model"],
            "fallback_reason": global_provider_metadata["fallback_reason"],
        },
        "retrieval_modes": mode_summaries,
        "retrieval_mode_cases": retrieval_mode_rows,
        "triage": {
            "CategoryAccuracy": round(category_accuracy, 4),
            "SeverityExactMatch": round(severity_exact, 4),
            "HighRiskSecurityReviewRecall": round(review_recall, 4),
            "FalseAutoApprovalRate": round(false_auto_approval_rate, 4),
            "CitationGroundingRate": round(citation_grounding, 4),
        },
        "system": {
            "StageLatency": summarize_latencies(all_stages),
            "ProviderUsage": {
                "rule_fallback": sum(row["provider"] == "rule_fallback" for row in rows),
                "local_hybrid_retrieval": sum("local hybrid retrieval" in str(row["retrieval_mode"]) for row in rows),
                "configured_embedding_provider": global_provider_metadata["configured_embedding_provider"],
                "effective_embedding_provider": global_provider_metadata["effective_embedding_provider"],
                "embedding_model": global_provider_metadata["embedding_model"],
                "fallback_reason": global_provider_metadata["fallback_reason"],
            },
            "IndexVersion": settings.index_version,
            "OCR": {
                "success": ocr_success,
                "failed": ocr_failed,
                "degraded": ocr_degraded,
                "not_exercised": total - ocr_exercised,
            },
        },
        "cases": rows,
    }
    report["passed"] = (
        report["triage"]["CategoryAccuracy"] >= settings.evaluation_min_category_accuracy
        and report["retrieval"]["HitRate@3"] >= settings.evaluation_min_hitrate_at_3
        and report["triage"]["SeverityExactMatch"] >= settings.evaluation_min_severity_exact_match
        and report["triage"]["HighRiskSecurityReviewRecall"] >= settings.evaluation_min_security_review_recall
        and report["triage"]["CitationGroundingRate"] >= settings.evaluation_min_citation_grounding_rate
        and report["triage"]["FalseAutoApprovalRate"] <= settings.evaluation_max_false_auto_approval_rate
    )
    return report
