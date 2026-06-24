from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import Principal, get_current_principal, require_admin
from app.database import get_session
from app.models import KnowledgeBaseArticle
from app.schemas import KBSearchRequest, KnowledgeBaseArticleCreate, KnowledgeBaseArticleRead
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


@router.post("/index/rebuild")
def rebuild_index(
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    return rebuild_kb_index(session, force_fallback=True)


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
