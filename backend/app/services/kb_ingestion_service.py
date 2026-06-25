import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.models import KBIngestionRun, KBIngestionStatus, KnowledgeBaseArticle, KnowledgeBaseChunk
from app.services.rag_service import DEFAULT_INDEX_DIR, rebuild_kb_index


settings = get_settings()


@dataclass
class ExtractedDocument:
    title: str
    content: str
    summary: str
    source_type: str
    page_count: int | None = None
    fallback_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _safe_file_name(file_name: str) -> str:
    cleaned = "".join(char for char in file_name if char.isalnum() or char in ("-", "_", ".", " ")).strip()
    return cleaned or f"kb-source-{uuid4().hex}.txt"


def _checksum_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文本文件必须为 UTF-8 编码") from exc


def _title_from_markdown_or_text(path: Path, text: str) -> str:
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return path.stem


def _summary(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:180] or "空文档"


def _extract_markdown_or_text(path: Path, content: bytes, source_type: str) -> ExtractedDocument:
    text = _decode_text(content)
    if not text.strip():
        raise ValueError("知识库文件为空")
    title = _title_from_markdown_or_text(path, text)
    return ExtractedDocument(
        title=title,
        content=text.strip(),
        summary=_summary(text),
        source_type=source_type,
        page_count=1,
    )


def _extract_pdf(path: Path, content: bytes) -> ExtractedDocument:
    if not content.startswith(b"%PDF"):
        raise ValueError("PDF 文件头无效")
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency is installed in normal runtime
        raise ValueError("缺少 pypdf，无法解析 PDF") from exc

    fallback_reasons: list[str] = []
    reader = PdfReader(path)
    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = ""
            fallback_reasons.append(f"pdf_page_{index}_text_extraction_failed:{exc}")
        if text.strip():
            page_texts.append(f"[page:{index}]\n{text.strip()}")
        else:
            fallback_reasons.append(f"pdf_page_{index}_empty_text_ocr_not_executed")
    if not page_texts:
        raise ValueError("PDF 未提取到有效文本；当前环境未配置 PDF 页面渲染 OCR 降级")
    text = "\n\n".join(page_texts)
    return ExtractedDocument(
        title=path.stem,
        content=text,
        summary=_summary(text),
        source_type="pdf",
        page_count=len(reader.pages),
        fallback_reasons=fallback_reasons,
    )


def validate_kb_source(file_name: str, content: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in settings.allowed_kb_extension_set:
        raise HTTPException(status_code=400, detail="不支持的知识库文件类型，仅允许 .md、.txt、.pdf")
    if not content:
        raise HTTPException(status_code=400, detail="知识库文件为空")
    if len(content) > settings.max_kb_upload_bytes:
        raise HTTPException(status_code=413, detail="知识库文件超过大小限制")
    if suffix in {".md", ".txt"}:
        if b"\x00" in content[:4096]:
            raise HTTPException(status_code=400, detail="知识库文本文件包含二进制内容")
        _decode_text(content)
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="PDF 文件头无效")
    return suffix.lstrip(".")


def extract_document(path: Path, content: bytes | None = None) -> ExtractedDocument:
    payload = content if content is not None else path.read_bytes()
    source_type = validate_kb_source(path.name, payload)
    if source_type in {"md", "txt"}:
        return _extract_markdown_or_text(path, payload, source_type)
    if source_type == "pdf":
        return _extract_pdf(path, payload)
    raise ValueError(f"不支持的知识库文件类型：{source_type}")


def _next_version(previous: str | None) -> str:
    if not previous or not previous.startswith("v"):
        return "v1"
    try:
        return f"v{int(previous[1:]) + 1}"
    except ValueError:
        return "v1"


def _upsert_article(
    session: Session,
    *,
    document: ExtractedDocument,
    source_filename: str,
    checksum: str,
    ingestion_run_id: int,
    kb_version: str,
) -> KnowledgeBaseArticle:
    article = session.exec(select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.source_checksum == checksum)).first()
    if article is None:
        article = session.exec(
            select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.source_filename == source_filename, KnowledgeBaseArticle.source_type == document.source_type)
        ).first()

    if article is None:
        article = KnowledgeBaseArticle(
            title=document.title,
            category=str(document.metadata.get("category") or "其他"),
            summary=document.summary,
            content=document.content,
            tags=list(document.metadata.get("tags") or []),
            reading_time=max(1, min(20, len(document.content) // 600 + 1)),
            source_name=source_filename,
            source_filename=source_filename,
            source_type=document.source_type,
            source_checksum=checksum,
            version="v1",
            page_count=document.page_count,
            ingestion_run_id=ingestion_run_id,
            kb_version=kb_version,
            ingestion_status="ready",
            index_status="stale",
        )
    else:
        content_changed = article.source_checksum != checksum
        article.title = document.title or article.title
        article.summary = document.summary
        article.content = document.content
        article.source_name = source_filename
        article.source_filename = source_filename
        article.source_type = document.source_type
        article.source_checksum = checksum
        article.page_count = document.page_count
        article.ingestion_run_id = ingestion_run_id
        article.kb_version = kb_version
        article.ingestion_status = "ready"
        article.index_status = "stale"
        if content_changed:
            article.version = _next_version(article.version)
    article.updated_at = datetime.utcnow()
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def ingest_kb_file(
    session: Session,
    source_path: Path,
    *,
    original_filename: str | None = None,
    rebuild_index: bool = True,
    index_dir: Path | None = None,
    force_fallback: bool | None = None,
) -> KBIngestionRun:
    started = time.perf_counter()
    source_filename = _safe_file_name(original_filename or source_path.name)
    content = source_path.read_bytes()
    source_type = validate_kb_source(source_filename, content)
    checksum = _checksum_bytes(content)
    kb_version = f"kb-{checksum[:12]}"
    run = KBIngestionRun(
        status=KBIngestionStatus.running,
        source_filename=source_filename,
        source_type=source_type,
        kb_version=kb_version,
        embedding_provider="pending",
        embedding_model=None,
        started_at=datetime.utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        document = extract_document(source_path, content)
        article = _upsert_article(
            session,
            document=document,
            source_filename=source_filename,
            checksum=checksum,
            ingestion_run_id=int(run.id),
            kb_version=kb_version,
        )
        manifest: dict[str, Any] = {}
        if rebuild_index:
            active_force_fallback = settings.embedding_provider == "local_hash_embedding_fallback" if force_fallback is None else force_fallback
            manifest = rebuild_kb_index(session, index_dir=index_dir or DEFAULT_INDEX_DIR, force_fallback=active_force_fallback)
        chunk_count = session.exec(
            select(func.count()).select_from(KnowledgeBaseChunk).where(KnowledgeBaseChunk.ingestion_run_id == run.id)
        ).one()
        fallback_reason = manifest.get("fallback_reason") or manifest.get("provider_error")
        if document.fallback_reasons:
            fallback_reason = "; ".join([*(document.fallback_reasons), *(filter(None, [fallback_reason]))])
        run.status = KBIngestionStatus.degraded if fallback_reason else KBIngestionStatus.completed
        run.document_count = 1 if article.id else 0
        run.chunk_count = int(chunk_count or 0)
        run.embedding_provider = str(manifest.get("provider") or settings.embedding_provider)
        run.embedding_model = manifest.get("embedding_model") or settings.sentence_transformer_model
        run.fallback_reason = fallback_reason
        run.completed_at = datetime.utcnow()
        run.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception as exc:
        run.status = KBIngestionStatus.failed
        run.error_message = str(exc)
        run.completed_at = datetime.utcnow()
        run.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


async def save_and_ingest_upload(session: Session, file: UploadFile) -> KBIngestionRun:
    source_filename = _safe_file_name(file.filename or "knowledge.txt")
    content = await file.read(settings.max_kb_upload_bytes + 1)
    source_type = validate_kb_source(source_filename, content)
    settings.kb_source_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex}_{source_filename}"
    target = settings.kb_source_dir / stored_name
    target.write_bytes(content)
    run = ingest_kb_file(session, target, original_filename=source_filename)
    run.source_type = source_type
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
