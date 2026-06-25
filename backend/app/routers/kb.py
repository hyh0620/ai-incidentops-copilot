import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import Principal, get_current_principal, require_admin
from app.database import get_session
from app.models import KBIngestionRun, KnowledgeBaseArticle
from app.schemas import KBIngestionRunRead, KBSearchRequest, KnowledgeBaseArticleCreate, KnowledgeBaseArticleRead
from app.services.kb_ingestion_service import save_and_ingest_upload
from app.services.rag_service import index_status, keyword_search_articles, rebuild_kb_index

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.get("", response_model=list[KnowledgeBaseArticleRead])
def list_articles(session: Session = Depends(get_session)) -> list[KnowledgeBaseArticle]:
    return session.exec(select(KnowledgeBaseArticle).order_by(KnowledgeBaseArticle.category, KnowledgeBaseArticle.title)).all()


@router.post("", response_model=KnowledgeBaseArticleRead)
def create_article(
    payload: KnowledgeBaseArticleCreate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> KnowledgeBaseArticle:
    require_admin(principal, session)
    article = KnowledgeBaseArticle(**payload.model_dump())
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


@router.get("/index/status")
def get_kb_index_status(session: Session = Depends(get_session)) -> dict:
    return index_status(session)


@router.get("/ingestions", response_model=list[KBIngestionRunRead])
def list_ingestion_runs(
    session: Session = Depends(get_session),
) -> list[KBIngestionRun]:
    return session.exec(select(KBIngestionRun).order_by(KBIngestionRun.started_at.desc()).limit(20)).all()


@router.get("/evaluation/summary")
def evaluation_summary() -> dict:
    candidates = [
        Path.cwd() / "artifacts" / "evaluation_report.json",
        Path.cwd().parent / "artifacts" / "evaluation_report.json",
    ]
    for path in candidates:
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            return {
                "available": True,
                "path": str(path),
                "dataset_version": report.get("dataset_version"),
                "retrieval_modes": report.get("retrieval_modes", {}),
                "generated_from": "synthetic regression benchmark",
            }
    return {"available": False, "retrieval_modes": {}, "generated_from": "synthetic regression benchmark"}


@router.post("/ingest", response_model=KBIngestionRunRead)
async def ingest_kb_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> KBIngestionRun:
    require_admin(principal, session)
    run = await save_and_ingest_upload(session, file)
    if run.status == "failed":
        raise HTTPException(status_code=400, detail=run.error_message or "知识库摄取失败")
    return run


@router.post("/index/rebuild")
def rebuild_index(
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    settings = get_settings()
    return rebuild_kb_index(session, force_fallback=settings.embedding_provider == "local_hash_embedding_fallback")


@router.post("/search")
def search_articles(payload: KBSearchRequest, session: Session = Depends(get_session)) -> list[dict]:
    return keyword_search_articles(
        session,
        query=payload.query,
        predicted_category=payload.category,
        keywords=[],
        top_k=payload.top_k,
        increment_hits=True,
    )


@router.get("/{article_id}", response_model=KnowledgeBaseArticleRead)
def get_article(article_id: int, session: Session = Depends(get_session)) -> KnowledgeBaseArticle:
    article = session.get(KnowledgeBaseArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="知识库文章不存在")
    article.hit_count += 1
    session.add(article)
    session.commit()
    session.refresh(article)
    return article
