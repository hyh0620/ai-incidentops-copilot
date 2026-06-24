from app.analysis.contracts import EvidenceItem
from app.core.config import get_settings
from app.evidence.redaction import redact_text


def build_text_evidence(title: str, description: str, affected_system: str | None) -> EvidenceItem:
    settings = get_settings()
    raw = "\n".join([title, description, affected_system or ""]).strip()
    redacted = redact_text(raw, settings.redact_internal_ips) if settings.enable_pii_redaction else None
    text = redacted.text if redacted else raw
    return EvidenceItem(
        id="ev-text-0",
        source_type="text",
        source_name="ticket_text",
        source_id=None,
        excerpt=text[:1200],
        available=bool(text),
        redacted=bool(redacted and redacted.redacted),
        signal_tags=[],
        confidence=1.0 if text else 0.0,
        metadata={"redaction_counts": redacted.counts if redacted else {}},
    )
