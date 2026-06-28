import argparse
import json
from typing import Any

from sqlmodel import Session, select

from app.database import engine
from app.models import AIAnalysisAudit, AIReview, Ticket, TicketAttachment

OCR_REASON = "ocr_failed_or_unavailable"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_MIME_PREFIX = "image/"
PDF_MIME = "application/pdf"
OCR_FAILURE_STATUSES = {"failed", "unavailable", "no_text_detected"}


def _has_ocr_required_attachment(attachments: list[TicketAttachment]) -> bool:
    for attachment in attachments:
        file_name = attachment.file_name.lower()
        mime_type = (attachment.mime_type or "").lower()
        if attachment.file_type.value == "screenshot":
            return True
        if mime_type.startswith(IMAGE_MIME_PREFIX) or mime_type == PDF_MIME:
            return True
        if any(file_name.endswith(ext) for ext in IMAGE_EXTENSIONS | PDF_EXTENSIONS):
            return True
    return False


def _ocr_failure_evidence(audit: AIAnalysisAudit | None) -> list[dict[str, Any]]:
    if audit is None:
        return []
    failures = []
    for item in audit.evidence or []:
        if item.get("source_type") != "ocr":
            continue
        status = (item.get("metadata") or {}).get("ocr_status")
        if status in OCR_FAILURE_STATUSES or (not item.get("available") and status):
            failures.append(item)
    return failures


def _ocr_stage_count(audit: AIAnalysisAudit | None) -> int:
    if audit is None:
        return 0
    count = 0
    for stage in audit.stage_traces or []:
        payload = json.dumps(stage, ensure_ascii=False).lower()
        if "ocr" in payload:
            count += 1
    return count


def _remove_reason(values: list[str]) -> list[str]:
    return [reason for reason in values if reason != OCR_REASON]


def _repair_audit(audit: AIAnalysisAudit | None) -> bool:
    if audit is None:
        return False
    changed = False
    final_decision = dict(audit.final_decision or {})
    reasons = list(final_decision.get("review_reasons") or [])
    if OCR_REASON in reasons:
        final_decision["review_reasons"] = _remove_reason(reasons)
        uncertainty = final_decision.get("uncertainty")
        if isinstance(uncertainty, str) and OCR_REASON in uncertainty:
            final_decision["uncertainty"] = uncertainty.replace(OCR_REASON, "").replace(", ,", ",").strip(" ,")
        audit.final_decision = final_decision
        changed = True
    return changed


def inspect_and_repair(apply: bool = False) -> dict[str, Any]:
    inspected = []
    repaired = []
    with Session(engine) as session:
        reviews = [review for review in session.exec(select(AIReview)).all() if OCR_REASON in (review.review_reasons or [])]
        for review in reviews:
            ticket = session.get(Ticket, review.ticket_id)
            if ticket is None:
                continue
            attachments = session.exec(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id)).all()
            audit = session.exec(select(AIAnalysisAudit).where(AIAnalysisAudit.run_id == review.run_id)).first() if review.run_id else None
            if audit is None:
                audit = session.exec(
                    select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket.id).order_by(AIAnalysisAudit.created_at.desc())
                ).first()
            has_ocr_attachment = _has_ocr_required_attachment(attachments)
            ocr_failures = _ocr_failure_evidence(audit)
            should_repair = not has_ocr_attachment and not ocr_failures
            record = {
                "ticket_id": ticket.id,
                "title": ticket.title,
                "attachments": [
                    {
                        "id": attachment.id,
                        "file_name": attachment.file_name,
                        "file_type": attachment.file_type.value,
                        "mime_type": attachment.mime_type,
                    }
                    for attachment in attachments
                ],
                "has_image_or_pdf": has_ocr_attachment,
                "ocr_stage_count": _ocr_stage_count(audit),
                "ocr_failure_count": len(ocr_failures),
                "review_reasons": review.review_reasons,
                "will_repair": should_repair,
            }
            inspected.append(record)
            if apply and should_repair:
                review.review_reasons = _remove_reason(review.review_reasons or [])
                session.add(review)
                _repair_audit(audit)
                if audit is not None:
                    session.add(audit)
                repaired.append({"ticket_id": ticket.id, "title": ticket.title})
        if apply:
            session.commit()
    return {"apply": apply, "inspected_count": len(inspected), "repaired_count": len(repaired), "inspected": inspected, "repaired": repaired}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and repair stale OCR AI review reasons.")
    parser.add_argument("--apply", action="store_true", help="Apply safe repairs. Without this flag the command is dry-run only.")
    args = parser.parse_args()
    print(json.dumps(inspect_and_repair(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
