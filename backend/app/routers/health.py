from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.ocr_readiness import check_ocr_readiness
from app.database import get_session
from app.models import User
from app.services.rag_service import index_status

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "ai-incidentops-copilot"}


@router.get("/health/ready")
def ready(session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    db_error = None
    try:
        session.exec(text("SELECT 1")).one()
        session.exec(select(User.id).limit(1)).all()
        db_ready = True
    except Exception as exc:
        db_ready = False
        db_error = str(exc)
    index = index_status(session)
    ocr = check_ocr_readiness()
    status = "ready" if db_ready and index.get("ready") and ocr.get("ready") else "degraded"
    return {
        "status": status,
        "database": {"ready": db_ready, "error": db_error},
        "index": index,
        "ocr": ocr,
        "providers": {
            "embedding": settings.embedding_provider,
            "reranker": settings.reranker_provider,
            "triage": settings.triage_provider,
            "llm": settings.llm_provider,
            "vision": settings.vision_provider,
        },
    }


@router.get("/system/status")
def system_status(session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    ocr = check_ocr_readiness()
    return {
        "auth_mode": settings.auth_mode,
        "upload_max_bytes": settings.max_upload_bytes,
        "index": index_status(session),
        "ocr": ocr,
        "providers": {
            "ocr": settings.ocr_provider,
            "embedding": settings.embedding_provider,
            "reranker": settings.reranker_provider,
            "triage": settings.triage_provider,
            "llm": settings.llm_provider,
            "vision": settings.vision_provider,
        },
        "redaction": {"enabled": settings.enable_pii_redaction, "redact_internal_ips": settings.redact_internal_ips},
    }
