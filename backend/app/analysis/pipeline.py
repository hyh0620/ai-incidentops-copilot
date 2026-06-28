from uuid import uuid4

from sqlmodel import Session, select

from app.analysis.contracts import (
    AnalysisRunDiff,
    AnalysisRunResult,
    EvidenceBundle,
    ResolutionProposal,
    ResolutionStep,
)
from app.analysis.policy import apply_review_policy
from app.analysis.trace import TraceRecorder
from app.core.config import get_settings
from app.core.time import utc_now
from app.evidence.logs import build_log_evidence
from app.evidence.ocr import build_ocr_evidence
from app.evidence.text import build_text_evidence
from app.models import AIAnalysisAudit, AttachmentFileType, Ticket, TicketAttachment
from app.retrieval.service import (
    build_candidates,
    dedupe_candidates,
    dense_candidate_retrieval,
    lexical_candidate_retrieval,
    prepare_retrieval_context,
    rerank_candidates,
    retrieval_result_from_candidates,
    rrf_fusion,
    threshold_evidence,
)
from app.triage.factory import get_triage_provider


def _latest_attachment(attachments: list[TicketAttachment], file_type: AttachmentFileType) -> TicketAttachment | None:
    candidates = [item for item in attachments if item.file_type == file_type]
    return sorted(candidates, key=lambda item: item.uploaded_at, reverse=True)[0] if candidates else None


def _diff_from_previous(session: Session, ticket: Ticket, decision_category: str, severity: str, confidence: float, evidence_ids: list[str], chunk_ids: list[int], review_reasons: list[str]) -> AnalysisRunDiff | None:
    previous = session.exec(
        select(AIAnalysisAudit).where(AIAnalysisAudit.ticket_id == ticket.id).order_by(AIAnalysisAudit.created_at.desc())
    ).first()
    if previous is None:
        return None
    prev_decision = previous.final_decision or {}
    return AnalysisRunDiff(
        category_changed=prev_decision.get("predicted_category") != decision_category,
        severity_changed=prev_decision.get("severity") != severity,
        confidence_delta=round(confidence - float(prev_decision.get("confidence", 0.0)), 4),
        evidence_changed=sorted(previous.final_decision.get("supported_by_evidence_ids", [])) != sorted(evidence_ids) if previous.final_decision else True,
        sources_changed=sorted(previous.source_chunk_ids or []) != sorted(chunk_ids),
        review_reasons_changed=sorted(prev_decision.get("review_reasons", [])) != sorted(review_reasons),
    )


class IncidentAnalysisPipeline:
    analysis_version = "incidentops-v2"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.trace = TraceRecorder()

    def run(self, ticket: Ticket) -> AnalysisRunResult:
        run_id = uuid4().hex
        evidence_items = []
        attachments: list[TicketAttachment] = []
        ocr_attempted = False
        ocr_failed = False

        with self.trace.stage("input_validation", provider="internal", input_summary=f"ticket_id={ticket.id}"):
            if ticket.id is None:
                raise ValueError("ticket must be persisted before analysis")

        with self.trace.stage("attachment_reading_and_redaction", provider="local_storage"):
            attachments = self.session.exec(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id)).all()

        with self.trace.stage("evidence_extraction", provider=f"text+logs+{self.settings.ocr_provider}") as stage:
            evidence_items.append(build_text_evidence(ticket.title, ticket.description, ticket.affected_system))
            log_attachment = _latest_attachment(attachments, AttachmentFileType.log)
            if log_attachment:
                log_text = ""
                try:
                    log_text = open(log_attachment.file_path, encoding="utf-8", errors="ignore").read(12000)
                except OSError:
                    log_text = ""
                evidence_items.append(build_log_evidence(log_attachment.file_name, log_text, str(log_attachment.id)))
            screenshot_attachment = _latest_attachment(attachments, AttachmentFileType.screenshot)
            if screenshot_attachment:
                ocr_attempted = True
                ocr_evidence = build_ocr_evidence(screenshot_attachment.file_name, screenshot_attachment.file_path, str(screenshot_attachment.id))
                ocr_failed = ocr_evidence.metadata.get("ocr_status") in {"failed", "unavailable"}
                if ocr_failed:
                    stage.degrade(str(ocr_evidence.metadata.get("error") or ocr_evidence.metadata.get("ocr_status") or "ocr_failed"))
                evidence_items.append(ocr_evidence)
            stage.output(f"evidence_items={len(evidence_items)}")
        evidence_bundle = EvidenceBundle(items=evidence_items, redaction_enabled=self.settings.enable_pii_redaction)
        evidence_bundle.redaction_summary = {
            key: sum(int(item.metadata.get("redaction_counts", {}).get(key, 0)) for item in evidence_items)
            for key in ["email", "phone", "bearer_token", "jwt", "api_key", "password", "cookie", "internal_ip"]
        }

        with self.trace.stage("pre_classification", provider="rule_fallback"):
            provider = get_triage_provider()
            empty_retrieval = retrieval_result_from_candidates(
                prepare_retrieval_context(self.session, "", None, [], force_fallback=True),
                [],
                [],
            )
            preliminary = provider.decide(ticket.title, ticket.description, ticket.user_category, ticket.urgency, evidence_bundle, empty_retrieval)

        query = "\n".join(item.excerpt for item in evidence_items if item.excerpt)
        keywords = [tag for item in evidence_items for tag in item.signal_tags]
        with self.trace.stage("retrieval_prepare", provider="local hybrid retrieval", input_summary=f"query_chars={len(query)}") as stage:
            retrieval_context = prepare_retrieval_context(
                self.session,
                query,
                preliminary.predicted_category,
                keywords,
                force_fallback=self.settings.embedding_provider == "local_hash_embedding_fallback",
            )
            if retrieval_context.degraded_reasons:
                stage.degrade("; ".join(retrieval_context.degraded_reasons))
            stage.output(f"chunks={len(retrieval_context.chunks)} provider={retrieval_context.backend.provider}")

        with self.trace.stage("dense_candidate_retrieval", provider=retrieval_context.backend.provider) as stage:
            dense_scores = dense_candidate_retrieval(retrieval_context)
            if retrieval_context.backend.error:
                stage.degrade(retrieval_context.backend.error)
            stage.output(f"candidates={len(dense_scores)}")

        with self.trace.stage("bm25_lexical_retrieval", provider="bm25_lexical") as stage:
            lexical_scores = lexical_candidate_retrieval(retrieval_context)
            stage.output(f"candidates={len(lexical_scores)}")

        with self.trace.stage("rrf_fusion", provider="rrf_fusion") as stage:
            fusion_scores = rrf_fusion(retrieval_context, dense_scores, lexical_scores)
            stage.output(f"fused={len(fusion_scores)}")

        with self.trace.stage("candidate_deduplication", provider="internal") as stage:
            retrieval_candidates = dedupe_candidates(build_candidates(retrieval_context, dense_scores, lexical_scores, fusion_scores))
            stage.output(f"deduped={len(retrieval_candidates)}")

        with self.trace.stage("rerank", provider=self.settings.reranker_provider) as stage:
            if self.settings.reranker_provider == "none":
                reranked_candidates = retrieval_candidates
                stage.skip("reranker_provider=none")
            else:
                reranked_candidates = rerank_candidates(retrieval_context.enriched_query, retrieval_candidates)
                stage.output(f"reranked={len(reranked_candidates)}")

        with self.trace.stage("evidence_thresholding", provider="policy") as stage:
            final_sources = threshold_evidence(
                reranked_candidates,
                query=retrieval_context.enriched_query,
                predicted_category=retrieval_context.predicted_category,
            )
            retrieval = retrieval_result_from_candidates(retrieval_context, reranked_candidates, final_sources)
            if retrieval.insufficient_evidence:
                stage.degrade("insufficient_evidence")
            stage.output(f"final_sources={len(final_sources)} threshold={retrieval.threshold}")

        with self.trace.stage("final_triage", provider=provider.provider) as stage:
            decision = provider.decide(ticket.title, ticket.description, ticket.user_category, ticket.urgency, evidence_bundle, retrieval)
            if decision.fallback_reason:
                stage.degrade(decision.fallback_reason)
            stage.output(
                "provider={provider} model={model} validation={validation} confidence={confidence:.2f} "
                "candidate_chunk_ids={candidate_ids} cited_chunk_ids={cited_ids} fallback_reason={fallback}".format(
                    provider=decision.provider,
                    model=decision.model_name or "-",
                    validation=decision.llm_validation_status or "not_applicable",
                    confidence=decision.confidence,
                    candidate_ids=decision.candidate_chunk_ids or [source.chunk_id for source in retrieval.candidates[: self.settings.llm_analysis_max_evidence_chunks]],
                    cited_ids=decision.cited_chunk_ids or decision.supported_by_chunk_ids,
                    fallback=decision.fallback_reason or "-",
                )
            )
            decision = apply_review_policy(decision, retrieval, ocr_failed=ocr_failed, ocr_attempted=ocr_attempted)

        with self.trace.stage("resolution", provider="policy_playbook_fallback"):
            if retrieval.insufficient_evidence:
                resolution = ResolutionProposal(
                    summary="未找到足够知识库证据，建议人工复核后再制定处置方案。",
                    insufficient_evidence=True,
                    steps=[
                        ResolutionStep(text="补充错误截图、日志片段或受影响系统信息", citation_evidence_ids=decision.supported_by_evidence_ids),
                        ResolutionStep(text="确认影响范围和业务优先级", citation_evidence_ids=decision.supported_by_evidence_ids),
                    ],
                )
            else:
                first = retrieval.final_sources[0]
                resolution = ResolutionProposal(
                    summary=f"基于知识库《{first.title}》chunk#{first.chunk_id} 证据，建议按 {decision.predicted_category} 流程处理。",
                    steps=[
                        ResolutionStep(text=f"参考 chunk#{source.chunk_id}: {source.excerpt[:120]}", citation_chunk_ids=[source.chunk_id])
                        for source in retrieval.final_sources
                    ],
                )

        with self.trace.stage("risk_policy_and_review", provider="policy"):
            decision = apply_review_policy(decision, retrieval, ocr_failed=ocr_failed, ocr_attempted=ocr_attempted)

        previous_diff = _diff_from_previous(
            self.session,
            ticket,
            decision.predicted_category,
            decision.severity,
            decision.confidence,
            decision.supported_by_evidence_ids,
            decision.supported_by_chunk_ids,
            decision.review_reasons,
        )

        return AnalysisRunResult(
            run_id=run_id,
            trace_id=self.trace.trace_id,
            ticket_id=int(ticket.id),
            analysis_version=self.analysis_version,
            created_at=utc_now(),
            evidence_bundle=evidence_bundle,
            retrieval=retrieval,
            triage=decision,
            resolution=resolution,
            stages=self.trace.stages,
            previous_diff=previous_diff,
            provider_status={
                "embedding": self.settings.embedding_provider,
                "reranker": self.settings.reranker_provider,
                "triage": decision.provider,
                "ocr": self.settings.ocr_provider,
                "analysis_provider": self.settings.analysis_provider,
                "llm_model": decision.model_name or "",
                "llm_validation_status": decision.llm_validation_status or "",
                "fallback_reason": decision.fallback_reason or "",
            },
        )
