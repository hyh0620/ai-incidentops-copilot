from app.analysis.contracts import EvidenceBundle, RetrievalResult, TriageDecision
from app.analysis.policy import apply_review_policy
from app.core.ocr_readiness import OCRProbe, check_ocr_readiness, clear_ocr_readiness_cache
from app.evidence.redaction import redact_text
from app.retrieval.chunker import boundary_aware_chunks
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.tokenizer import tokenize
from app.triage.factory import get_triage_provider


class _WorkingTesseract:
    @staticmethod
    def get_tesseract_version():
        return "5.3.0"

    @staticmethod
    def get_languages(config: str = ""):
        return ["eng", "chi_sim", "osd"]


class _MissingChineseTesseract:
    @staticmethod
    def get_tesseract_version():
        return "5.3.0"

    @staticmethod
    def get_languages(config: str = ""):
        return ["eng"]


class _BrokenExecutableTesseract:
    @staticmethod
    def get_tesseract_version():
        raise RuntimeError("tesseract not found")


def test_tokenizer_keeps_chinese_and_error_identifiers():
    tokens = tokenize("数据库 ORA-12170 timeout HTTP 500 DatabaseTimeoutException ECONNRESET")

    assert "ora-12170" in tokens
    assert "http500" in tokens
    assert "databasetimeoutexception" in tokens
    assert "econnreset" in tokens
    assert any(token in tokens for token in ["数据库", "超时"])


def test_boundary_chunker_respects_boundaries_and_overlap():
    text = "# VPN 无法连接\n\n第一段说明 cannot connect。\n\n- 保留 HTTP 500 和 ORA-12170\n\n第二段说明 timeout。"
    chunks = boundary_aware_chunks(text, chunk_size=42, overlap=8)

    assert len(chunks) >= 2
    assert any("HTTP 500" in chunk for chunk in chunks)
    assert any("ORA-12170" in chunk for chunk in chunks)


def test_rrf_prioritizes_items_appearing_in_multiple_rankings():
    scores = reciprocal_rank_fusion([[1, 2, 3], [3, 1, 4]], k=60)

    assert scores[1] > scores[2]
    assert scores[3] > scores[4]


def test_pii_redaction_masks_tokens_without_removing_diagnostics():
    raw = "user=a@example.com password=Secret123 Bearer abcdefghijklmnop api_key=sk_test_123456789 ORA-12170"
    redacted = redact_text(raw)

    assert "Secret123" not in redacted.text
    assert "abcdefghijklmnop" not in redacted.text
    assert "sk_test_123456789" not in redacted.text
    assert "a@example.com" not in redacted.text
    assert "ORA-12170" in redacted.text
    assert redacted.redacted


def test_provider_factory_defaults_to_rule_fallback():
    provider = get_triage_provider()

    assert provider.provider == "rule_fallback"


def test_rule_provider_does_not_high_confidence_without_evidence():
    provider = get_triage_provider()
    decision = provider.decide(
        title="phishing suspicious unauthorized malware",
        description="",
        user_category="安全风险",
        urgency="高",
        evidence=EvidenceBundle(items=[]),
        retrieval=type(
            "Retrieval",
            (),
            {"final_sources": [], "insufficient_evidence": True},
        )(),
    )

    assert decision.confidence <= 0.69
    assert decision.supported_by_evidence_ids == []


def _decision(review_reasons: list[str] | None = None) -> TriageDecision:
    return TriageDecision(
        predicted_category="其他",
        severity="medium",
        confidence=0.82,
        rationale="fixture",
        requires_human_review=False,
        review_reasons=review_reasons or [],
        provider="rule_fallback",
        supported_by_evidence_ids=["ev-text-0"],
        supported_by_chunk_ids=[],
    )


def _retrieval(insufficient: bool = False) -> RetrievalResult:
    return RetrievalResult(
        retrieval_mode="test",
        threshold=0.02,
        insufficient_evidence=insufficient,
    )


def test_review_policy_does_not_add_ocr_reason_for_text_only_ticket():
    decision = apply_review_policy(_decision(["ocr_failed_or_unavailable"]), _retrieval(), ocr_attempted=False, ocr_failed=False)

    assert "ocr_failed_or_unavailable" not in decision.review_reasons


def test_review_policy_does_not_add_ocr_reason_for_log_only_ticket():
    decision = apply_review_policy(_decision(), _retrieval(), ocr_attempted=False, ocr_failed=True)

    assert "ocr_failed_or_unavailable" not in decision.review_reasons


def test_review_policy_does_not_add_ocr_reason_when_image_ocr_succeeds():
    decision = apply_review_policy(_decision(), _retrieval(), ocr_attempted=True, ocr_failed=False)

    assert "ocr_failed_or_unavailable" not in decision.review_reasons


def test_review_policy_adds_ocr_reason_when_image_ocr_fails():
    decision = apply_review_policy(_decision(), _retrieval(), ocr_attempted=True, ocr_failed=True)

    assert "ocr_failed_or_unavailable" in decision.review_reasons


def test_review_policy_keeps_insufficient_retrieval_evidence_reason():
    decision = apply_review_policy(_decision(), _retrieval(insufficient=True), ocr_attempted=False, ocr_failed=False)

    assert "insufficient_retrieval_evidence" in decision.review_reasons


def test_ocr_readiness_reports_ready_when_package_binary_and_languages_exist():
    clear_ocr_readiness_cache()
    result = check_ocr_readiness(
        probe=OCRProbe(provider="pytesseract_ocr", required_languages=["eng", "chi_sim"]),
        tesseract_module=_WorkingTesseract,
        use_cache=False,
    )

    assert result["python_package_available"] is True
    assert result["executable_available"] is True
    assert result["ready"] is True
    assert result["degraded_reason"] is None


def test_ocr_readiness_degrades_when_chinese_language_missing():
    clear_ocr_readiness_cache()
    result = check_ocr_readiness(
        probe=OCRProbe(provider="pytesseract_ocr", required_languages=["eng", "chi_sim"]),
        tesseract_module=_MissingChineseTesseract,
        use_cache=False,
    )

    assert result["ready"] is False
    assert result["executable_available"] is True
    assert result["required_languages"] == ["eng", "chi_sim"]
    assert "chi_sim" in result["degraded_reason"]


def test_ocr_readiness_degrades_when_executable_unavailable():
    clear_ocr_readiness_cache()
    result = check_ocr_readiness(
        probe=OCRProbe(provider="pytesseract_ocr", required_languages=["eng"]),
        tesseract_module=_BrokenExecutableTesseract,
        use_cache=False,
    )

    assert result["python_package_available"] is True
    assert result["executable_available"] is False
    assert result["ready"] is False
    assert "unavailable" in result["degraded_reason"]
