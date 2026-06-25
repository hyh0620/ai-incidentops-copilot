import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.analysis.contracts import RetrievalCandidate, RetrievalResult
from app.core.config import get_settings
from app.models import KnowledgeBaseArticle, KnowledgeBaseChunk
from app.retrieval.reranker import HeuristicReranker
from app.retrieval.tokenizer import tokenize
from app.services import rag_service


GENERIC_SUPPORT_TERMS = {
    "error",
    "failed",
    "failure",
    "issue",
    "problem",
    "help",
    "need",
    "user",
    "system",
    "internal",
    "service",
    "component",
    "fixture",
    "benchmark",
    "状态",
    "系统",
    "用户",
    "异常",
    "报错",
    "问题",
    "帮助",
    "内部",
    "服务",
}
DOMAIN_SUPPORT_TERMS = {
    "vpn",
    "network",
    "wifi",
    "connect",
    "database",
    "timeout",
    "api",
    "exception",
    "mfa",
    "password",
    "login",
    "access",
    "denied",
    "unauthorized",
    "suspicious",
    "phishing",
    "malware",
    "disk",
    "cpu",
    "memory",
    "server",
    "gitlab",
    "ci",
    "pipeline",
    "policy",
    "blocked",
    "email",
    "mail",
    "gateway",
    "网络",
    "连接",
    "数据库",
    "超时",
    "验证码",
    "密码",
    "登录",
    "拒绝",
    "权限",
    "可疑",
    "钓鱼",
    "磁盘",
    "内存",
    "策略",
    "阻止",
    "邮件",
}
STRONG_IDENTIFIER_RE = re.compile(
    r"^(?:http[45]\d{2}|[45]\d{2}|ora-\d+|sqlstate[a-z0-9]+|econnreset|etimedout|eacces|[a-z][a-z0-9_.]*(?:exception|error))$",
    re.IGNORECASE,
)
NO_INCIDENT_CONTEXT_RE = re.compile(
    r"(没有报告实际故障|未报告实际故障|非故障|培训材料|演练材料|测试文本|not an incident|training material)",
    re.IGNORECASE,
)


@dataclass
class RetrievalContext:
    session: Session
    query: str
    predicted_category: str | None
    keywords: list[str]
    index_dir: Path
    chunks: list[KnowledgeBaseChunk]
    articles: dict[int, KnowledgeBaseArticle]
    manifest: dict[str, Any] | None
    backend: rag_service.EmbeddingBackend
    enriched_query: str
    degraded_reasons: list[str] = field(default_factory=list)


def prepare_retrieval_context(
    session: Session,
    query: str,
    predicted_category: str | None,
    keywords: list[str],
    index_dir: Path | None = None,
    force_fallback: bool = False,
) -> RetrievalContext:
    settings = get_settings()
    index_dir = index_dir or rag_service.DEFAULT_INDEX_DIR
    chunks = session.exec(select(KnowledgeBaseChunk).order_by(KnowledgeBaseChunk.id)).all()
    manifest = rag_service._load_manifest(index_dir)
    degraded: list[str] = []
    if not chunks:
        if settings.allow_auto_rebuild_index:
            manifest = rag_service.rebuild_kb_index(session, index_dir=index_dir, force_fallback=force_fallback)
            chunks = session.exec(select(KnowledgeBaseChunk).order_by(KnowledgeBaseChunk.id)).all()
            degraded.append("index_missing_auto_rebuilt")
        else:
            degraded.append("index_missing_or_no_chunks")
    status = rag_service.index_status(session, index_dir=index_dir)
    if status.get("stale"):
        degraded.append("index_stale")
    backend = rag_service.get_embedding_backend(force_fallback=force_fallback)
    if backend.error:
        degraded.append(backend.error)
    articles = {int(article.id): article for article in session.exec(select(KnowledgeBaseArticle)).all() if article.id is not None}
    return RetrievalContext(
        session=session,
        query=query,
        predicted_category=predicted_category,
        keywords=keywords,
        index_dir=index_dir,
        chunks=chunks,
        articles=articles,
        manifest=manifest,
        backend=backend,
        enriched_query=" ".join([query, predicted_category or "", " ".join(keywords)]).strip(),
        degraded_reasons=degraded,
    )


def dense_candidate_retrieval(context: RetrievalContext) -> dict[int, float]:
    if not context.chunks or not context.enriched_query:
        return {}
    return rag_service._dense_scores(context.enriched_query, context.chunks, context.index_dir, context.backend, context.manifest)


def lexical_candidate_retrieval(context: RetrievalContext) -> dict[int, float]:
    if not context.chunks or not context.enriched_query:
        return {}
    return rag_service._lexical_scores(context.enriched_query, context.chunks)


def rrf_fusion(context: RetrievalContext, dense: dict[int, float], lexical: dict[int, float]) -> dict[int, float]:
    settings = get_settings()
    dense_ranks = rag_service._rank_map(dense)
    lexical_ranks = rag_service._rank_map(lexical)
    return {
        int(chunk.id): rag_service._rrf(dense_ranks.get(int(chunk.id), 999), settings.rrf_k)
        + rag_service._rrf(lexical_ranks.get(int(chunk.id), 999), settings.rrf_k)
        for chunk in context.chunks
        if chunk.id is not None
    }


def build_candidates(
    context: RetrievalContext,
    dense: dict[int, float],
    lexical: dict[int, float],
    fusion: dict[int, float],
) -> list[RetrievalCandidate]:
    settings = get_settings()
    chunk_by_id = {int(chunk.id): chunk for chunk in context.chunks if chunk.id is not None}
    ordered_chunk_ids = sorted(fusion, key=lambda chunk_id: fusion[chunk_id], reverse=True)
    pool_ids = ordered_chunk_ids[: max(settings.retrieval_top_k, settings.retrieval_candidate_pool)]
    candidates: list[RetrievalCandidate] = []
    for chunk_id in pool_ids:
        chunk = chunk_by_id[chunk_id]
        article = context.articles.get(chunk.article_id)
        if not article:
            continue
        excerpt = rag_service._excerpt(chunk.content, context.enriched_query)
        metadata = {
            "id": article.id,
            "article_id": article.id,
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "title": article.title,
            "category": article.category,
            "summary": article.summary,
            "chunk_summary": chunk.content[:180],
            "evidence_excerpt": excerpt,
            "evidence_excerpt_snapshot": excerpt,
            "dense_score": round(dense.get(chunk_id, 0.0), 4),
            "lexical_score": round(lexical.get(chunk_id, 0.0), 4),
            "fusion_score": round(fusion.get(chunk_id, 0.0), 6),
            "final_score": round(fusion.get(chunk_id, 0.0), 6),
            "rerank_score": None,
            "ranking_stage": "rrf_fusion",
            "insufficient": fusion.get(chunk_id, 0.0) < settings.min_evidence_threshold,
            "retrieval_mode": "local hybrid retrieval",
            "embedding_provider": context.backend.provider,
            "embedding_model": context.backend.model_name,
            "fallback_reason": context.backend.fallback_reason,
            "index_version": context.manifest.get("index_version") if context.manifest else settings.index_version,
            "corpus_hash": context.manifest.get("corpus_hash") if context.manifest else None,
            "content_hash": chunk.content_hash,
            "article_version": article.version,
            "kb_version": chunk.kb_version,
            "source_filename": article.source_filename,
            "source_type": article.source_type,
            "page_number": chunk.page_number,
            "ingestion_run_id": chunk.ingestion_run_id,
            "historical_snapshot": False,
        }
        candidates.append(
            RetrievalCandidate(
                article_id=int(article.id),
                chunk_id=int(chunk.id),
                title=article.title,
                category=article.category,
                excerpt=excerpt,
                dense_score=metadata["dense_score"],
                lexical_score=metadata["lexical_score"],
                fusion_score=metadata["fusion_score"],
                provider=context.backend.provider,
                metadata=metadata,
            )
        )
    return candidates


def dedupe_candidates(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    seen: set[tuple[int, str]] = set()
    deduped: list[RetrievalCandidate] = []
    for candidate in candidates:
        key = (candidate.article_id, candidate.metadata.get("content_hash", str(candidate.chunk_id)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def rerank_candidates(query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    settings = get_settings()
    if settings.reranker_provider == "none":
        return candidates
    return HeuristicReranker().rerank(query, candidates)


def _support_terms(query: str, candidate: RetrievalCandidate) -> tuple[list[str], list[str]]:
    query_terms = {
        term
        for term in tokenize(query)
        if term not in GENERIC_SUPPORT_TERMS and (len(term) >= 3 or term in DOMAIN_SUPPORT_TERMS)
    }
    candidate_text = " ".join(
        [
            candidate.title,
            candidate.category,
            candidate.excerpt,
            str(candidate.metadata.get("summary", "")),
            str(candidate.metadata.get("chunk_summary", "")),
        ]
    )
    candidate_terms = set(tokenize(candidate_text))
    support = sorted(query_terms & candidate_terms)
    strong = sorted(
        term
        for term in support
        if STRONG_IDENTIFIER_RE.match(term) or term in DOMAIN_SUPPORT_TERMS
    )
    return support, strong


def _has_citation_support(query: str, candidate: RetrievalCandidate, predicted_category: str | None = None) -> bool:
    support, strong = _support_terms(query, candidate)
    identifier_terms = sorted(term for term in strong if STRONG_IDENTIFIER_RE.match(term))
    candidate.metadata["support_terms"] = support
    candidate.metadata["strong_support_terms"] = strong
    candidate.metadata["identifier_support_terms"] = identifier_terms
    if not support:
        candidate.metadata["citation_rejected_reason"] = "no_diagnostic_term_overlap"
        return False
    if identifier_terms:
        return True
    if predicted_category and candidate.category == predicted_category and strong:
        return True
    if len(strong) >= 2 or len(support) >= 3:
        return True
    candidate.metadata["citation_rejected_reason"] = "weak_or_cross_category_overlap"
    return False


def threshold_evidence(
    candidates: list[RetrievalCandidate],
    query: str = "",
    predicted_category: str | None = None,
    increment_hits: bool = False,
    session: Session | None = None,
) -> list[RetrievalCandidate]:
    settings = get_settings()
    results: list[RetrievalCandidate] = []
    seen_articles: set[int] = set()
    if query and NO_INCIDENT_CONTEXT_RE.search(query):
        for candidate in candidates:
            candidate.metadata["insufficient"] = True
            candidate.metadata["citation_rejected_reason"] = "non_incident_context"
        return []
    for candidate in candidates:
        final_score = candidate.rerank_score if candidate.rerank_score is not None else candidate.fusion_score
        candidate.metadata["final_score"] = final_score
        candidate.metadata["rerank_score"] = candidate.rerank_score
        candidate.metadata["ranking_stage"] = candidate.ranking_stage
        candidate.metadata["insufficient"] = final_score < settings.min_evidence_threshold
        if final_score < settings.min_evidence_threshold:
            continue
        if query and not _has_citation_support(query, candidate, predicted_category):
            candidate.metadata["insufficient"] = True
            continue
        if candidate.article_id in seen_articles and len(results) >= settings.retrieval_top_k:
            continue
        seen_articles.add(candidate.article_id)
        results.append(candidate)
        if increment_hits and session is not None:
            article = session.get(KnowledgeBaseArticle, candidate.article_id)
            if article:
                article.hit_count += 1
                session.add(article)
        if len(results) >= settings.retrieval_top_k:
            break
    if increment_hits and session is not None:
        session.commit()
    return results


def retrieval_result_from_candidates(
    context: RetrievalContext,
    candidates: list[RetrievalCandidate],
    final_sources: list[RetrievalCandidate],
    retrieval_mode: str = "local hybrid retrieval",
) -> RetrievalResult:
    settings = get_settings()
    return RetrievalResult(
        candidates=candidates,
        final_sources=final_sources,
        retrieval_mode=retrieval_mode,
        index_version=context.manifest.get("index_version") if context.manifest else settings.index_version,
        corpus_hash=context.manifest.get("corpus_hash") if context.manifest else None,
        insufficient_evidence=len(final_sources) == 0,
        threshold=settings.min_evidence_threshold,
        diagnostics={
            "embedding_provider": context.backend.provider,
            "embedding_model": context.backend.model_name,
            "provider_error": context.backend.error,
            "fallback_reason": context.backend.fallback_reason,
            "degraded_reasons": context.degraded_reasons,
            "candidate_count": len(candidates),
            "final_source_count": len(final_sources),
        },
    )


def retrieve_evidence(session: Session, query: str, predicted_category: str | None, keywords: list[str]) -> RetrievalResult:
    settings = get_settings()
    context = prepare_retrieval_context(
        session,
        query=query,
        predicted_category=predicted_category,
        keywords=keywords,
        force_fallback=settings.embedding_provider == "local_hash_embedding_fallback",
    )
    dense = dense_candidate_retrieval(context)
    lexical = lexical_candidate_retrieval(context)
    fusion = rrf_fusion(context, dense, lexical)
    candidates = dedupe_candidates(build_candidates(context, dense, lexical, fusion))
    reranked = rerank_candidates(context.enriched_query, candidates)
    final_sources = threshold_evidence(reranked, query=context.enriched_query, predicted_category=context.predicted_category)
    return retrieval_result_from_candidates(context, reranked, final_sources)


def retrieve_evidence_by_mode(
    session: Session,
    query: str,
    predicted_category: str | None,
    keywords: list[str],
    retrieval_mode: str,
    index_dir: Path | None = None,
    force_fallback: bool | None = None,
) -> RetrievalResult:
    settings = get_settings()
    active_force_fallback = settings.embedding_provider == "local_hash_embedding_fallback" if force_fallback is None else force_fallback
    context = prepare_retrieval_context(
        session,
        query=query,
        predicted_category=predicted_category,
        keywords=keywords,
        index_dir=index_dir,
        force_fallback=active_force_fallback,
    )
    if retrieval_mode == "bm25_only":
        dense = {}
        lexical = lexical_candidate_retrieval(context)
        ranking_scores = lexical
    elif retrieval_mode == "dense_only":
        dense = dense_candidate_retrieval(context)
        lexical = {}
        ranking_scores = dense
    elif retrieval_mode == "hybrid_rrf":
        dense = dense_candidate_retrieval(context)
        lexical = lexical_candidate_retrieval(context)
        ranking_scores = rrf_fusion(context, dense, lexical)
    else:
        raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")

    candidates = dedupe_candidates(build_candidates(context, dense, lexical, ranking_scores))
    for candidate in candidates:
        score = ranking_scores.get(candidate.chunk_id, 0.0)
        candidate.fusion_score = score
        candidate.ranking_stage = retrieval_mode
        candidate.metadata["fusion_score"] = round(score, 6)
        candidate.metadata["final_score"] = round(score, 6)
        candidate.metadata["ranking_stage"] = retrieval_mode
        candidate.metadata["retrieval_mode"] = retrieval_mode
    final_sources = threshold_evidence(candidates, query=context.enriched_query, predicted_category=context.predicted_category)
    return retrieval_result_from_candidates(context, candidates, final_sources, retrieval_mode=retrieval_mode)
