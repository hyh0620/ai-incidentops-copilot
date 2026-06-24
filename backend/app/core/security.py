from dataclasses import dataclass

from fastapi import Header, HTTPException
from sqlmodel import Session

from app.models import Ticket, User, UserRole


@dataclass(frozen=True)
class Principal:
    user_id: int
    role: UserRole | None = None
    name: str | None = None
    email: str | None = None


def get_current_principal(
    x_demo_user_id: int | None = Header(default=None, alias="X-Demo-User-Id"),
) -> Principal:
    if x_demo_user_id is None:
        raise HTTPException(
            status_code=401,
            detail="缺少 Demo Persona 身份。请通过前端身份选择器访问，或在直接调用受保护 API 时显式提供 X-Demo-User-Id 请求头。",
        )
    return Principal(user_id=x_demo_user_id)


def resolve_principal(principal: Principal, session: Session) -> Principal:
    user = session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Demo 用户不存在，请先导入 demo 数据")
    return Principal(user_id=int(user.id), role=user.role, name=user.name, email=user.email)


def require_admin(principal: Principal, session: Session) -> Principal:
    resolved = resolve_principal(principal, session)
    if resolved.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return resolved


def require_ticket_access(ticket_id: int, principal: Principal, session: Session) -> Ticket:
    resolved = resolve_principal(principal, session)
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    if resolved.role != UserRole.admin and ticket.requester_id != resolved.user_id:
        raise HTTPException(status_code=403, detail="无权访问该工单")
    return ticket
