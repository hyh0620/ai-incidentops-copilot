from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.security import Principal, get_current_principal, require_ticket_access
from app.database import get_session
from app.models import TicketAttachment, TicketTimelineEvent
from app.schemas import AttachmentRead
from app.services.ticket_service import reanalyze_ticket, save_upload_file

router = APIRouter(prefix="/api/tickets/{ticket_id}/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentRead)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> TicketAttachment:
    require_ticket_access(ticket_id, principal, session)
    attachment = await save_upload_file(ticket_id, file)
    session.add(attachment)
    session.add(TicketTimelineEvent(ticket_id=ticket_id, event_type="attachment_added", content=f"新增附件：{attachment.file_name}，系统将自动重新分析"))
    session.commit()
    session.refresh(attachment)
    await reanalyze_ticket(session, ticket_id)
    return attachment


@router.get("", response_model=list[AttachmentRead])
def list_attachments(
    ticket_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> list[TicketAttachment]:
    require_ticket_access(ticket_id, principal, session)
    return session.exec(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket_id)).all()


@router.get("/{attachment_id}/download")
def download_attachment(
    ticket_id: int,
    attachment_id: int,
    session: Session = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
) -> FileResponse:
    require_ticket_access(ticket_id, principal, session)
    attachment = session.get(TicketAttachment, attachment_id)
    if attachment is None or attachment.ticket_id != ticket_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    path = Path(attachment.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(path, media_type=attachment.mime_type or "application/octet-stream", filename=attachment.file_name)
