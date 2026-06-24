from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlmodel import Session

from app.core.security import Principal, get_current_principal, require_admin, require_ticket_access, resolve_principal
from app.database import get_session
from app.models import TicketSeverity, TicketStatus, UserRole
from app.schemas import AIAnalysisAuditRead, TicketAssignUpdate, TicketCreateResponse, TicketDetailRead, TicketListRead, TicketStatusUpdate, TicketUpdate
from app.services.ticket_service import (
    create_ticket_with_ai,
    get_analysis_run,
    get_analysis_trace,
    get_ticket_detail,
    list_analysis_runs,
    list_tickets,
    reanalyze_ticket,
    update_ticket,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketListRead])
def get_tickets(
    status: TicketStatus | None = None,
    severity: TicketSeverity | None = None,
    predicted_category: str | None = None,
    assigned_team: str | None = None,
    search: str | None = None,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    resolved = resolve_principal(principal, session)
    return list_tickets(
        session,
        status=status,
        severity=severity,
        predicted_category=predicted_category,
        assigned_team=assigned_team,
        search=search,
        requester_id=None if resolved.role == UserRole.admin else resolved.user_id,
    )


@router.get("/{ticket_id}", response_model=TicketDetailRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_ticket_access(ticket_id, principal, session)
    return get_ticket_detail(session, ticket_id)


@router.post("", response_model=TicketCreateResponse)
async def create_ticket(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    category: Annotated[str, Form()],
    urgency: Annotated[str, Form()],
    affected_system: Annotated[str | None, Form()] = None,
    contact_email: Annotated[str, Form()] = "demo.requester@example.com",
    requester_id: Annotated[int | None, Form()] = None,
    screenshot: UploadFile | None = File(default=None),
    log_file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    resolved = resolve_principal(principal, session)
    effective_requester_id = requester_id if resolved.role == UserRole.admin else resolved.user_id
    return await create_ticket_with_ai(
        session,
        title=title,
        description=description,
        user_category=category,
        urgency=urgency,
        affected_system=affected_system,
        contact_email=contact_email,
        screenshot=screenshot,
        log_file=log_file,
        requester_id=effective_requester_id,
    )


@router.patch("/{ticket_id}", response_model=TicketDetailRead)
def patch_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    return update_ticket(session, ticket_id, payload)


@router.post("/{ticket_id}/reanalyze", response_model=TicketCreateResponse)
async def post_reanalyze_ticket(
    ticket_id: int,
    screenshot: UploadFile | None = File(default=None),
    log_file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_ticket_access(ticket_id, principal, session)
    return await reanalyze_ticket(session, ticket_id, screenshot=screenshot, log_file=log_file)


@router.get("/{ticket_id}/analysis-runs", response_model=list[AIAnalysisAuditRead])
def get_ticket_analysis_runs(
    ticket_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[dict]:
    require_ticket_access(ticket_id, principal, session)
    return list_analysis_runs(session, ticket_id)


@router.get("/{ticket_id}/analysis-runs/{run_id}", response_model=AIAnalysisAuditRead)
def get_ticket_analysis_run(
    ticket_id: int,
    run_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_ticket_access(ticket_id, principal, session)
    return get_analysis_run(session, ticket_id, run_id)


@router.get("/{ticket_id}/analysis-runs/{run_id}/trace")
def get_ticket_analysis_run_trace(
    ticket_id: int,
    run_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_ticket_access(ticket_id, principal, session)
    return get_analysis_trace(session, ticket_id, run_id)


@router.patch("/{ticket_id}/status", response_model=TicketDetailRead)
def patch_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    return update_ticket(session, ticket_id, TicketUpdate(status=payload.status))


@router.patch("/{ticket_id}/assign", response_model=TicketDetailRead)
def patch_ticket_assign(
    ticket_id: int,
    payload: TicketAssignUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    require_admin(principal, session)
    return update_ticket(session, ticket_id, TicketUpdate(assigned_team=payload.assigned_team))
