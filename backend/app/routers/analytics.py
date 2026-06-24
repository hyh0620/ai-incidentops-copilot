from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.security import Principal, get_current_principal, require_admin
from app.database import get_session
from app.schemas import AnalyticsSummary
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> dict:
    require_admin(principal, session)
    return analytics_service.summary(session)


@router.get("/categories")
def get_categories(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.category_distribution(session)


@router.get("/severity")
def get_severity(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.severity_distribution(session)


@router.get("/trend")
def get_trend(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.seven_day_trend(session)


@router.get("/top-issues")
def get_top_issues(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.top_issues(session)


@router.get("/kb-hits")
def get_kb_hits(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.kb_hits(session)


@router.get("/ai-confidence")
def get_ai_confidence(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> list[dict]:
    require_admin(principal, session)
    return analytics_service.ai_confidence_distribution(session)


@router.get("/resolution")
def get_resolution(session: Session = Depends(get_session), principal: Principal = Depends(get_current_principal)) -> dict:
    require_admin(principal, session)
    return analytics_service.average_resolution(session)
