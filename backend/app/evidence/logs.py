from app.analysis.contracts import EvidenceItem
from app.core.config import get_settings
from app.evidence.redaction import redact_text
from app.services.multimodal_analyzer import analyze_log_file


def build_log_evidence(source_name: str, text: str, source_id: str | None = None) -> EvidenceItem:
    settings = get_settings()
    redacted = redact_text(text, settings.redact_internal_ips) if settings.enable_pii_redaction else None
    safe_text = redacted.text if redacted else text
    parsed = analyze_log_file(source_name, safe_text)
    return EvidenceItem(
        id=f"ev-log-{source_id or source_name}",
        source_type="log",
        source_name=source_name,
        source_id=source_id,
        excerpt=safe_text[:1600],
        available=bool(safe_text),
        redacted=bool(redacted and redacted.redacted),
        signal_tags=parsed.get("detected_keywords", []),
        confidence=0.9 if safe_text else 0.0,
        metadata={"structured_signals": parsed.get("structured_signals", {}), "redaction_counts": redacted.counts if redacted else {}},
    )
