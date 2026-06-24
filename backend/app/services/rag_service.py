import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlmodel import Session, select

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - exercised when faiss is unavailable
    faiss = None

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - rank_bm25 is optional at runtime
    BM25Okapi = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - sentence-transformers can be absent in tests
    SentenceTransformer = None

from app.core.config import get_settings
from app.models import KnowledgeBaseArticle, KnowledgeBaseChunk
from app.retrieval.chunker import boundary_aware_chunks
from app.retrieval.reranker import HeuristicReranker
from app.retrieval.tokenizer import tokenize


settings = get_settings()
DEFAULT_MODEL = settings.embedding_model
DEFAULT_INDEX_DIR = Path(settings.vector_index_dir)
INDEX_FILE = "kb.faiss"
MANIFEST_FILE = "kb_manifest.json"
CHUNK_SIZE = 520
CHUNK_OVERLAP = 80
HASH_EMBED_DIM = 384


def _tokens(text: str) -> list[str]:
    return tokenize(text)


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    return boundary_aware_chunks(text, chunk_size, overlap)


def _hash_embed(texts: list[str], dim: int = HASH_EMBED_DIM) -> np.ndarray:
    vectors = np.zeros((len(texts), dim), dtype="float32")
    for row, text in enumerate(texts):
        for token in _tokens(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vectors[row, index] += sign
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@dataclass
class EmbeddingBackend:
    provider: str
    dimension: int
    model: Any | None = None
    error: str | None = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.model is not None:
            vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vectors, dtype="float32")
        return _hash_embed(texts, self.dimension)


_EMBEDDING_BACKEND: EmbeddingBackend | None = None


def get_embedding_backend(force_fallback: bool = False) -> EmbeddingBackend:
    global _EMBEDDING_BACKEND
    if force_fallback:
        return EmbeddingBackend(provider="local_hash_embedding_fallback", dimension=HASH_EMBED_DIM)
    if _EMBEDDING_BACKEND is not None:
        return _EMBEDDING_BACKEND

    configured = get_settings().embedding_provider
    if configured == "sentence_transformers" and SentenceTransformer is not None:
        try:
            model = SentenceTransformer(DEFAULT_MODEL)
            dimension = int(model.get_sentence_embedding_dimension() or HASH_EMBED_DIM)
            _EMBEDDING_BACKEND = EmbeddingBackend(provider=f"sentence_transformers:{DEFAULT_MODEL}", dimension=dimension, model=model)
            return _EMBEDDING_BACKEND
        except Exception as exc:
            _EMBEDDING_BACKEND = EmbeddingBackend(
                provider="local_hash_embedding_fallback",
                dimension=HASH_EMBED_DIM,
                error=f"sentence-transformers unavailable: {exc}",
            )
            return _EMBEDDING_BACKEND

    _EMBEDDING_BACKEND = EmbeddingBackend(provider="local_hash_embedding_fallback", dimension=HASH_EMBED_DIM)
    return _EMBEDDING_BACKEND


def build_kb_chunks(session: Session) -> list[KnowledgeBaseChunk]:
    articles = session.exec(select(KnowledgeBaseArticle).order_by(KnowledgeBaseArticle.id)).all()
    chunks: list[KnowledgeBaseChunk] = []
    desired_hashes: set[str] = set()
    settings = get_settings()
    existing_by_hash = {chunk.content_hash: chunk for chunk in session.exec(select(KnowledgeBaseChunk)).all()}
    for article in articles:
        source_text = "\n".join(
            [
                f"标题：{article.title}",
                f"分类：{article.category}",
                f"摘要：{article.summary}",
                f"标签：{', '.join(article.tags)}",
                article.content,
            ]
        )
        for index, content in enumerate(chunk_text(source_text, settings.chunk_size, settings.chunk_overlap)):
            content_hash = _content_hash(f"{article.id}:{index}:{content}")
            desired_hashes.add(content_hash)
            metadata = {
                    "title": article.title,
                    "category": article.category,
                    "tags": article.tags,
                    "summary": article.summary,
                    "source_name": article.source_name,
                    "source_type": article.source_type,
                    "article_version": article.version,
                    "chunking_version": settings.chunking_version,
            }
            chunk = existing_by_hash.get(content_hash)
            if chunk is None:
                chunk = KnowledgeBaseChunk(
                    article_id=article.id,
                    chunk_index=index,
                    content=content,
                    metadata_json=metadata,
                    content_hash=content_hash,
                    created_at=datetime.utcnow(),
                )
            else:
                chunk.article_id = article.id
                chunk.chunk_index = index
                chunk.content = content
                chunk.metadata_json = metadata
            session.add(chunk)
            chunks.append(chunk)
        article.index_status = "ready"
        article.updated_at = datetime.utcnow()
        session.add(article)
    session.commit()
    if desired_hashes:
        stale_chunks = session.exec(select(KnowledgeBaseChunk)).all()
        for chunk in stale_chunks:
            if chunk.content_hash not in desired_hashes:
                session.delete(chunk)
        session.commit()
    for chunk in chunks:
        session.refresh(chunk)
    return chunks


def _write_faiss_index(vectors: np.ndarray, index_dir: Path) -> bool:
    if faiss is None or len(vectors) == 0:
        return False
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / INDEX_FILE))
    return True


def _replace_index_dir_contents(tmp_dir: Path, index_dir: Path) -> None:
    """Replace index artifacts without deleting a Docker volume mount point."""
    index_dir.mkdir(parents=True, exist_ok=True)
    for child in index_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in tmp_dir.iterdir():
        shutil.move(str(child), str(index_dir / child.name))
    shutil.rmtree(tmp_dir)


def rebuild_kb_index(session: Session, index_dir: Path | None = None, force_fallback: bool = False) -> dict[str, Any]:
    index_dir = index_dir or DEFAULT_INDEX_DIR
    settings = get_settings()
    chunks = build_kb_chunks(session)
    backend = get_embedding_backend(force_fallback=force_fallback)
    texts = [chunk.content for chunk in chunks]
    vectors = backend.encode(texts) if texts else np.zeros((0, backend.dimension), dtype="float32")
    tmp_dir = index_dir.with_name(f"{index_dir.name}.tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    faiss_written = _write_faiss_index(vectors, tmp_dir)
    corpus_hash = _content_hash("\n".join(chunk.content_hash for chunk in chunks))
    source_versions = [
        {
            "article_id": chunk.article_id,
            "chunk_id": chunk.id,
            "content_hash": chunk.content_hash,
        }
        for chunk in chunks
    ]
    manifest = {
        "index_version": settings.index_version,
        "corpus_hash": corpus_hash,
        "provider": backend.provider,
        "provider_error": backend.error,
        "retrieval_mode": "local hybrid retrieval",
        "faiss_enabled": faiss_written,
        "dimension": int(vectors.shape[1]) if len(vectors) else backend.dimension,
        "chunk_count": len(chunks),
        "chunk_ids": [chunk.id for chunk in chunks],
        "chunking_config": {
            "version": settings.chunking_version,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        },
        "source_versions": source_versions,
        "build_status": "ready",
        "rebuilt_at": datetime.utcnow().isoformat(),
    }
    (tmp_dir / MANIFEST_FILE).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _replace_index_dir_contents(tmp_dir, index_dir)
    return manifest


def index_status(session: Session, index_dir: Path | None = None) -> dict[str, Any]:
    index_dir = index_dir or DEFAULT_INDEX_DIR
    manifest = _load_manifest(index_dir)
    chunks = session.exec(select(KnowledgeBaseChunk)).all()
    chunk_ids = [chunk.id for chunk in chunks]
    stale_articles = session.exec(select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.index_status == "stale")).all()
    if not manifest:
        return {"status": "missing", "ready": False, "stale": True, "chunk_count": len(chunks)}
    manifest_ids = manifest.get("chunk_ids", [])
    consistent = sorted(manifest_ids) == sorted(chunk_ids)
    stale = bool(stale_articles) or not consistent
    return {
        "status": "ready" if not stale else "stale",
        "ready": not stale,
        "stale": stale,
        "manifest": manifest,
        "chunk_count": len(chunks),
        "db_chunk_count": len(chunks),
        "manifest_chunk_count": len(manifest_ids),
        "consistent": consistent,
        "stale_article_count": len(stale_articles),
    }


def _load_manifest(index_dir: Path) -> dict[str, Any] | None:
    path = index_dir / MANIFEST_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _dense_scores(query: str, chunks: list[KnowledgeBaseChunk], index_dir: Path, backend: EmbeddingBackend, manifest: dict[str, Any] | None) -> dict[int, float]:
    if not chunks:
        return {}
    query_vector = backend.encode([query])
    scores: dict[int, float] = {}
    if faiss is not None and manifest and manifest.get("faiss_enabled") and (index_dir / INDEX_FILE).exists():
        index = faiss.read_index(str(index_dir / INDEX_FILE))
        k = min(len(chunks), max(10, len(chunks)))
        distances, positions = index.search(query_vector.astype("float32"), k)
        chunk_ids = manifest.get("chunk_ids", [])
        for score, position in zip(distances[0], positions[0]):
            if position < 0 or position >= len(chunk_ids):
                continue
            scores[int(chunk_ids[position])] = float(score)
        return scores

    vectors = backend.encode([chunk.content for chunk in chunks])
    distances = np.matmul(vectors, query_vector[0])
    for chunk, score in zip(chunks, distances):
        scores[int(chunk.id)] = float(score)
    return scores


def _lexical_scores(query: str, chunks: list[KnowledgeBaseChunk]) -> dict[int, float]:
    if not chunks:
        return {}
    corpus_tokens = [_tokens(chunk.content) for chunk in chunks]
    query_tokens = _tokens(query)
    if BM25Okapi is not None and any(corpus_tokens):
        bm25 = BM25Okapi(corpus_tokens)
        raw_scores = bm25.get_scores(query_tokens)
    else:
        query_set = set(query_tokens)
        raw_scores = np.asarray([len(query_set & set(tokens)) for tokens in corpus_tokens], dtype="float32")
    max_score = float(np.max(raw_scores)) if len(raw_scores) else 0.0
    if max_score <= 0:
        max_score = 1.0
    return {int(chunk.id): float(score / max_score) for chunk, score in zip(chunks, raw_scores)}


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _excerpt(content: str, query: str, width: int = 220) -> str:
    tokens = _tokens(query)
    lowered = content.lower()
    positions = [lowered.find(token.lower()) for token in tokens if token and lowered.find(token.lower()) >= 0]
    if positions:
        start = max(0, min(positions) - 60)
    else:
        start = 0
    snippet = content[start : start + width].strip()
    return snippet if len(snippet) < len(content) else content.strip()


def _rank_map(scores: dict[int, float]) -> dict[int, int]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return {chunk_id: index + 1 for index, (chunk_id, _) in enumerate(ordered)}


def hybrid_search_articles(
    session: Session,
    query: str,
    predicted_category: str | None = None,
    keywords: list[str] | None = None,
    top_k: int = 3,
    increment_hits: bool = False,
    index_dir: Path | None = None,
    force_fallback: bool = False,
) -> list[dict[str, Any]]:
    keywords = keywords or []
    index_dir = index_dir or DEFAULT_INDEX_DIR
    settings = get_settings()
    chunks = session.exec(select(KnowledgeBaseChunk).order_by(KnowledgeBaseChunk.id)).all()
    manifest = _load_manifest(index_dir)
    if not chunks:
        if settings.allow_auto_rebuild_index:
            manifest = rebuild_kb_index(session, index_dir=index_dir, force_fallback=force_fallback)
            chunks = session.exec(select(KnowledgeBaseChunk).order_by(KnowledgeBaseChunk.id)).all()
        else:
            return []
    status = index_status(session, index_dir=index_dir)
    if status.get("stale") and not settings.allow_auto_rebuild_index:
        return []

    backend = get_embedding_backend(force_fallback=force_fallback)
    enriched_query = " ".join([query, predicted_category or "", " ".join(keywords)])
    dense = _dense_scores(enriched_query, chunks, index_dir, backend, manifest)
    lexical = _lexical_scores(enriched_query, chunks)
    dense_ranks = _rank_map(dense)
    lexical_ranks = _rank_map(lexical)

    final_scores: dict[int, float] = {}
    for chunk in chunks:
        chunk_id = int(chunk.id)
        final_scores[chunk_id] = _rrf(dense_ranks.get(chunk_id, 999), settings.rrf_k) + _rrf(lexical_ranks.get(chunk_id, 999), settings.rrf_k)

    ordered_chunk_ids = sorted(final_scores, key=lambda chunk_id: final_scores[chunk_id], reverse=True)
    chunk_by_id = {int(chunk.id): chunk for chunk in chunks}
    article_cache = {article.id: article for article in session.exec(select(KnowledgeBaseArticle)).all()}
    results: list[dict[str, Any]] = []
    pool_ids = ordered_chunk_ids[: max(top_k, settings.retrieval_candidate_pool)]
    preliminary: list[dict[str, Any]] = []
    for chunk_id in pool_ids:
        chunk = chunk_by_id[chunk_id]
        article = article_cache.get(chunk.article_id)
        if not article:
            continue
        preliminary.append(
            {
                "id": article.id,
                "article_id": article.id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "title": article.title,
                "category": article.category,
                "summary": article.summary,
                "chunk_summary": chunk.content[:180],
                "evidence_excerpt": _excerpt(chunk.content, enriched_query),
                "dense_score": round(dense.get(chunk_id, 0.0), 4),
                "lexical_score": round(lexical.get(chunk_id, 0.0), 4),
                "fusion_score": round(final_scores.get(chunk_id, 0.0), 6),
                "final_score": round(final_scores.get(chunk_id, 0.0), 6),
                "rerank_score": None,
                "ranking_stage": "rrf_fusion",
                "insufficient": final_scores.get(chunk_id, 0.0) < settings.min_evidence_threshold,
                "retrieval_mode": "local hybrid retrieval",
                "embedding_provider": backend.provider,
                "index_version": manifest.get("index_version") if manifest else settings.index_version,
                "corpus_hash": manifest.get("corpus_hash") if manifest else None,
            }
        )
    candidates = []
    for item in preliminary:
        from app.analysis.contracts import RetrievalCandidate

        candidates.append(
            RetrievalCandidate(
                article_id=item["article_id"],
                chunk_id=item["chunk_id"],
                title=item["title"],
                category=item["category"],
                excerpt=item["evidence_excerpt"],
                dense_score=item["dense_score"],
                lexical_score=item["lexical_score"],
                fusion_score=item["fusion_score"],
                provider=item["embedding_provider"],
                metadata=item,
            )
        )
    reranked = HeuristicReranker().rerank(enriched_query, candidates)
    seen_articles: set[int] = set()
    for candidate in reranked:
        item = dict(candidate.metadata)
        item["rerank_score"] = candidate.rerank_score
        item["ranking_stage"] = candidate.ranking_stage
        item["final_score"] = candidate.rerank_score or candidate.fusion_score
        item["insufficient"] = item["final_score"] < settings.min_evidence_threshold
        if item["article_id"] in seen_articles and len(results) >= top_k:
            continue
        seen_articles.add(item["article_id"])
        if not item["insufficient"]:
            article = article_cache.get(item["article_id"])
            if increment_hits and article:
                article.hit_count += 1
                session.add(article)
            results.append(item)
        if len(results) >= top_k:
            break

    if increment_hits:
        session.commit()
    return results


def keyword_search_articles(
    session: Session,
    query: str,
    predicted_category: str | None = None,
    keywords: list[str] | None = None,
    top_k: int = 3,
    increment_hits: bool = False,
) -> list[dict[str, Any]]:
    return hybrid_search_articles(
        session,
        query=query,
        predicted_category=predicted_category,
        keywords=keywords,
        top_k=top_k,
        increment_hits=increment_hits,
    )


def embed_query(query: str) -> list[float]:
    return get_embedding_backend().encode([query])[0].tolist()


def search_vector_store(embedding: list[float], top_k: int = 3) -> list[dict[str, Any]]:
    return [{"error": "Use hybrid_search_articles with DB chunk metadata instead of raw vector-only lookup.", "top_k": top_k}]


def rerank_results(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=lambda item: item.get("final_score", 0), reverse=True)
