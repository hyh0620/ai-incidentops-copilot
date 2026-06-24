from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import Principal, get_current_principal, require_admin
from app.database import get_session
from app.models import RemediationTask, Ticket, TicketTimelineEvent
from app.schemas import RemediationTaskCreate, RemediationTaskRead, RemediationTaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[RemediationTaskRead])
def list_tasks(
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[RemediationTask]:
    require_admin(principal, session)
    return session.exec(select(RemediationTask).order_by(RemediationTask.created_at.desc())).all()


@router.post("", response_model=RemediationTaskRead)
def create_task(
    payload: RemediationTaskCreate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> RemediationTask:
    require_admin(principal, session)
    ticket = session.get(Ticket, payload.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    task = RemediationTask(**payload.model_dump())
    session.add(task)
    session.add(TicketTimelineEvent(ticket_id=payload.ticket_id, event_type="task_created", content=f"创建处置任务：{payload.title}"))
    session.commit()
    session.refresh(task)
    return task


@router.patch("/{task_id}", response_model=RemediationTaskRead)
def update_task(
    task_id: int,
    payload: RemediationTaskUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> RemediationTask:
    require_admin(principal, session)
    task = session.get(RemediationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(task, field, value)
    session.add(task)
    if "status" in changes:
        session.add(TicketTimelineEvent(ticket_id=task.ticket_id, event_type="task_status_changed", content=f"任务 {task.title} 状态更新为 {task.status.value}"))
    session.commit()
    session.refresh(task)
    return task
