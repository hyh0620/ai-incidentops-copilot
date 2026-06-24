from app.analysis.contracts import EvidenceItem
from app.core.config import get_settings
from app.evidence.redaction import redact_text
from app.services.multimodal_analyzer import analyze_screenshot_with_vision_model


def build_ocr_evidence(source_name: str, file_path: str, source_id: str | None = None) -> EvidenceItem:
    settings = get_settings()
    result = analyze_screenshot_with_vision_model(source_name, file_path)
    raw_text = result.get("extracted_text", "")
    redacted = redact_text(raw_text, settings.redact_internal_ips) if raw_text and settings.enable_pii_redaction else None
    safe_text = redacted.text if redacted else raw_text
    return EvidenceItem(
        id=f"ev-ocr-{source_id or source_name}",
        source_type="ocr",
        source_name=source_name,
        source_id=source_id,
        excerpt=safe_text[:1200] if safe_text else result.get("error") or "",
        available=bool(safe_text),
        redacted=bool(redacted and redacted.redacted),
        signal_tags=result.get("detected_keywords", []),
        confidence=(float(result["confidence"]) / 100.0) if result.get("confidence") else None,
        metadata={
            "ocr_status": result.get("ocr_status"),
            "ocr_provider": result.get("ocr_provider"),
            "error": result.get("error"),
            "detected_error_codes": result.get("detected_error_codes", []),
            "redaction_counts": redacted.counts if redacted else {},
        },
    )
