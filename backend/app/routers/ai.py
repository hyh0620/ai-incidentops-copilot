from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import Principal, get_current_principal, require_admin
from app.core.time import utc_isoformat
from app.database import get_session
from app.models import AIReview, AIReviewStatus, Ticket, TicketTimelineEvent
from app.schemas import AIReviewUpdate

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/reviews")
def list_reviews(
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    require_admin(principal, session)
    reviews = session.exec(select(AIReview).order_by(AIReview.created_at.desc())).all()
    rows = []
    for review in reviews:
        ticket = session.get(Ticket, review.ticket_id)
        review_payload = review.model_dump()
        review_payload["created_at"] = utc_isoformat(review.created_at)
        ticket_payload = ticket.model_dump() if ticket else None
        if ticket_payload:
            ticket_payload["created_at"] = utc_isoformat(ticket.created_at)
            ticket_payload["updated_at"] = utc_isoformat(ticket.updated_at)
        rows.append(
            {
                **review_payload,
                "ticket": ticket_payload,
            }
        )
    return rows


@router.patch("/reviews/{review_id}")
def update_review(
    review_id: int,
    payload: AIReviewUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    review = session.get(AIReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="AI 复核记录不存在")
    ticket = session.get(Ticket, review.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="关联工单不存在")

    review.corrected_category = payload.corrected_category
    review.corrected_severity = payload.corrected_severity
    review.correction_reason = payload.correction_reason
    review.reviewer_note = payload.reviewer_note
    review.status = payload.status
    session.add(review)

    if payload.status == AIReviewStatus.overridden:
        if payload.corrected_category:
            ticket.predicted_category = payload.corrected_category
        if payload.corrected_severity:
            ticket.severity = payload.corrected_severity
        session.add(ticket)
        content = f"AI 复核已覆盖：{ticket.predicted_category} / {ticket.severity.value}"
    else:
        content = "AI 复核已通过" if payload.status == AIReviewStatus.approved else "AI 复核记录已更新"
    session.add(TicketTimelineEvent(ticket_id=ticket.id, event_type="ai_review_updated", content=content))
    session.commit()
    session.refresh(review)
    review_payload = review.model_dump()
    review_payload["created_at"] = utc_isoformat(review.created_at)
    ticket_payload = ticket.model_dump()
    ticket_payload["created_at"] = utc_isoformat(ticket.created_at)
    ticket_payload["updated_at"] = utc_isoformat(ticket.updated_at)
    return {**review_payload, "ticket": ticket_payload}
