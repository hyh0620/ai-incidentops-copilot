from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.security import Principal, get_current_principal, require_admin
from app.database import get_session
from app.models import User
from app.schemas import UserRead

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[User]:
    require_admin(principal, session)
    return session.exec(select(User).order_by(User.created_at)).all()


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> User:
    require_admin(principal, session)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user
