from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.evaluation.runner import run_evaluation
from app.models import KBIngestionStatus, KnowledgeBaseArticle, KnowledgeBaseChunk
from app.retrieval.service import retrieve_evidence_by_mode
from app.services.kb_ingestion_service import ingest_kb_file, validate_kb_source
from app.services.rag_service import clear_embedding_backend_cache, get_embedding_backend, rebuild_kb_index


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_markdown_document_ingestion_generates_article_chunk_and_run(session: Session, tmp_path: Path):
    run = ingest_kb_file(session, Path("tests/fixtures/kb_sample.md"), index_dir=tmp_path, force_fallback=True)
    article = session.exec(select(KnowledgeBaseArticle)).one()
    chunks = session.exec(select(KnowledgeBaseChunk)).all()

    assert run.status == KBIngestionStatus.completed
    assert run.document_count == 1
    assert run.chunk_count >= 1
    assert run.embedding_provider == "local_hash_embedding_fallback"
    assert article.source_filename == "kb_sample.md"
    assert article.source_type == "md"
    assert article.kb_version == run.kb_version
    assert chunks[0].kb_version == run.kb_version
    assert chunks[0].ingestion_run_id == run.id


def test_txt_document_ingestion_success(session: Session, tmp_path: Path):
    run = ingest_kb_file(session, Path("tests/fixtures/kb_sample.txt"), index_dir=tmp_path, force_fallback=True)
    article = session.exec(select(KnowledgeBaseArticle)).one()

    assert run.status == KBIngestionStatus.completed
    assert article.source_type == "txt"
    assert "DatabaseTimeoutException" in article.content


def test_text_pdf_ingestion_extracts_page_number(session: Session, tmp_path: Path):
    run = ingest_kb_file(session, Path("tests/fixtures/kb_sample.pdf"), index_dir=tmp_path, force_fallback=True)
    article = session.exec(select(KnowledgeBaseArticle)).one()
    chunks = session.exec(select(KnowledgeBaseChunk)).all()

    assert run.status == KBIngestionStatus.completed
    assert article.source_type == "pdf"
    assert article.page_count == 1
    assert any(chunk.page_number == 1 for chunk in chunks)
    assert any("HTTP 500" in chunk.content for chunk in chunks)


def test_empty_and_unsupported_kb_files_are_rejected():
    with pytest.raises(HTTPException):
        validate_kb_source("empty.txt", b"")
    with pytest.raises(HTTPException):
        validate_kb_source("malware.exe", b"not empty")


def test_kb_version_changes_when_same_filename_content_changes(session: Session, tmp_path: Path):
    first = tmp_path / "runbook.txt"
    second = tmp_path / "runbook-v2.txt"
    first.write_text("VPN cannot connect timeout", encoding="utf-8")
    second.write_text("VPN cannot connect timeout with gateway error", encoding="utf-8")

    run1 = ingest_kb_file(session, first, original_filename="runbook.txt", index_dir=tmp_path / "index", force_fallback=True)
    article1 = session.exec(select(KnowledgeBaseArticle)).one()
    run2 = ingest_kb_file(session, second, original_filename="runbook.txt", index_dir=tmp_path / "index", force_fallback=True)
    article2 = session.exec(select(KnowledgeBaseArticle)).one()

    assert article1.id == article2.id
    assert run1.kb_version != run2.kb_version
    assert article2.version == "v2"


def test_sentence_transformer_provider_can_be_mocked(monkeypatch: pytest.MonkeyPatch):
    import app.services.rag_service as rag_service

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts, normalize_embeddings: bool = True, show_progress_bar: bool = False):
            return np.ones((len(texts), 3), dtype="float32")

    monkeypatch.setattr(rag_service, "SentenceTransformer", FakeSentenceTransformer)
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="sentence_transformers",
            sentence_transformer_model="fixture-model",
            embedding_model="fixture-model",
        ),
    )
    clear_embedding_backend_cache()
    backend = get_embedding_backend()

    assert backend.provider == "sentence_transformers"
    assert backend.model_name == "fixture-model"
    assert backend.encode(["hello"]).shape == (1, 3)
    clear_embedding_backend_cache()


def test_sentence_transformer_failure_falls_back_to_hash(monkeypatch: pytest.MonkeyPatch):
    import app.services.rag_service as rag_service

    class BrokenSentenceTransformer:
        def __init__(self, model_name: str):
            raise RuntimeError("model load failed")

    monkeypatch.setattr(rag_service, "SentenceTransformer", BrokenSentenceTransformer)
    monkeypatch.setattr(
        rag_service,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="sentence_transformers",
            sentence_transformer_model="fixture-model",
            embedding_model="fixture-model",
        ),
    )
    clear_embedding_backend_cache()
    backend = get_embedding_backend()

    assert backend.provider == "local_hash_embedding_fallback"
    assert backend.fallback_reason == "model_load_failed"
    clear_embedding_backend_cache()


def test_bm25_dense_and_hybrid_modes_run_independently(session: Session, tmp_path: Path):
    session.add(
        KnowledgeBaseArticle(
            title="数据库连接超时",
            category="软件系统",
            summary="db timeout",
            content="DatabaseTimeoutException database connection timeout HTTP 500",
            tags=["database", "timeout"],
        )
    )
    session.commit()
    rebuild_kb_index(session, index_dir=tmp_path, force_fallback=True)

    for mode in ["bm25_only", "dense_only", "hybrid_rrf"]:
        result = retrieve_evidence_by_mode(
            session,
            "DatabaseTimeoutException database timeout",
            predicted_category=None,
            keywords=[],
            retrieval_mode=mode,
            index_dir=tmp_path,
            force_fallback=True,
        )
        assert result.retrieval_mode == mode
        assert result.diagnostics["embedding_provider"] == "local_hash_embedding_fallback"
        assert result.candidates


def test_evaluation_report_generates_retrieval_mode_metrics(tmp_path: Path):
    report = run_evaluation(Path("tests/fixtures/golden_incident_cases.json"), tmp_path / "artifacts")

    assert {"bm25_only", "dense_only", "hybrid_rrf"} <= set(report["retrieval_modes"])
    assert report["retrieval"]["embedding_provider"] == "local_hash_embedding_fallback"
    assert "UnsupportedCitationRate" in report["retrieval_modes"]["hybrid_rrf"]


def test_official_evaluation_defaults_to_hash_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local_hash_embedding_fallback")
    get_settings.cache_clear()
    clear_embedding_backend_cache()

    report = run_evaluation(Path("tests/fixtures/golden_incident_cases.json"), tmp_path / "artifacts")

    assert report["configured_embedding_provider"] == "local_hash_embedding_fallback"
    assert report["effective_embedding_provider"] == "local_hash_embedding_fallback"
    assert report["fallback_reason"] is None
    assert report["retrieval_modes"]["bm25_only"]["effective_dense_provider"] == "not_used"
    assert report["retrieval_modes"]["dense_only"]["effective_dense_provider"] == "local_hash_embedding_fallback"
    assert report["retrieval_modes"]["hybrid_rrf"]["effective_dense_provider"] == "local_hash_embedding_fallback"


def test_official_evaluation_respects_sentence_transformer_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import app.services.rag_service as rag_service

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts, normalize_embeddings: bool = True, show_progress_bar: bool = False):
            vectors = []
            for text in texts:
                seed = sum(ord(char) for char in str(text))
                vectors.append([float(seed % 7 + 1), float(seed % 11 + 1), float(seed % 13 + 1)])
            return np.array(vectors, dtype="float32")

    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence_transformers")
    monkeypatch.setenv("SENTENCE_TRANSFORMER_MODEL", "fixture-model")
    monkeypatch.setattr(rag_service, "SentenceTransformer", FakeSentenceTransformer)
    get_settings.cache_clear()
    clear_embedding_backend_cache()

    report = run_evaluation(Path("tests/fixtures/golden_incident_cases.json"), tmp_path / "artifacts")

    assert report["configured_embedding_provider"] == "sentence_transformers"
    assert report["effective_embedding_provider"] == "sentence_transformers"
    assert report["embedding_model"] == "fixture-model"
    assert report["fallback_reason"] is None
    assert report["retrieval_modes"]["bm25_only"]["effective_dense_provider"] == "not_used"
    assert report["retrieval_modes"]["dense_only"]["effective_dense_provider"] == "sentence_transformers"
    assert report["retrieval_modes"]["hybrid_rrf"]["effective_dense_provider"] == "sentence_transformers"


def test_official_evaluation_records_sentence_transformer_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import app.services.rag_service as rag_service

    class BrokenSentenceTransformer:
        def __init__(self, model_name: str):
            raise RuntimeError("model load failed")

    monkeypatch.setenv("EMBEDDING_PROVIDER", "sentence_transformers")
    monkeypatch.setenv("SENTENCE_TRANSFORMER_MODEL", "fixture-model")
    monkeypatch.setattr(rag_service, "SentenceTransformer", BrokenSentenceTransformer)
    get_settings.cache_clear()
    clear_embedding_backend_cache()

    report = run_evaluation(Path("tests/fixtures/golden_incident_cases.json"), tmp_path / "artifacts")

    assert report["configured_embedding_provider"] == "sentence_transformers"
    assert report["effective_embedding_provider"] == "local_hash_embedding_fallback"
    assert report["fallback_reason"] == "model_load_failed"
    assert report["retrieval_modes"]["bm25_only"]["effective_dense_provider"] == "not_used"
    assert report["retrieval_modes"]["dense_only"]["effective_dense_provider"] == "local_hash_embedding_fallback"
    assert report["retrieval_modes"]["dense_only"]["fallback_reason"] == "model_load_failed"
