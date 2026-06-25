from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./incidentops.db"

    max_upload_bytes: int = 10 * 1024 * 1024
    max_kb_upload_bytes: int = 10 * 1024 * 1024
    allowed_image_mime_types: str = "image/png,image/jpeg,image/webp,image/gif"
    allowed_log_mime_types: str = "text/plain,application/json,text/csv,application/csv"
    allowed_kb_file_extensions: str = ".md,.txt,.pdf"
    upload_dir: Path = BASE_DIR / "uploads"
    kb_source_dir: Path = BASE_DIR / "uploads" / "kb_sources"

    ocr_provider: Literal["pytesseract_ocr", "disabled"] = "pytesseract_ocr"
    ocr_required_languages: str = "eng,chi_sim"
    embedding_provider: Literal["local_hash_embedding_fallback", "sentence_transformers"] = "local_hash_embedding_fallback"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    sentence_transformer_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    reranker_provider: Literal["heuristic_reranker", "none"] = "heuristic_reranker"
    reranker_model: str = ""
    analysis_provider: Literal["rule_fallback", "openai_compatible"] = "rule_fallback"
    triage_provider: Literal["rule_fallback", "openai_compatible"] = "rule_fallback"
    llm_provider: Literal["none", "openai_compatible"] = "none"
    vision_provider: Literal["none", "openai_compatible"] = "none"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = ""
    llm_analysis_timeout_seconds: float = 30.0
    llm_analysis_max_evidence_chunks: int = 8
    mcp_demo_user_id: int | None = None

    retrieval_top_k: int = 3
    retrieval_candidate_pool: int = 12
    rrf_k: int = 60
    min_evidence_threshold: float = 0.02
    chunk_size: int = 520
    chunk_overlap: int = 80
    chunking_version: str = "boundary-aware-v2"
    index_version: str = "hybrid-faiss-bm25-rrf-v2"
    vector_index_dir: Path = BASE_DIR / "vector_store"
    allow_auto_rebuild_index: bool = False
    allow_dev_create_all: bool = False

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_allow_credentials: bool = True
    auth_mode: Literal["demo"] = "demo"
    log_level: str = "INFO"
    enable_pii_redaction: bool = True
    redact_internal_ips: bool = False

    evaluation_min_category_accuracy: float = Field(default=0.80, ge=0.01)
    evaluation_min_hitrate_at_3: float = Field(default=0.70, ge=0.01)
    evaluation_min_severity_exact_match: float = Field(default=0.70, ge=0.01)
    evaluation_min_security_review_recall: float = Field(default=0.80, ge=0.01)
    evaluation_min_citation_grounding_rate: float = Field(default=0.70, ge=0.01)
    evaluation_max_false_auto_approval_rate: float = Field(default=0.10, ge=0.0)

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if "*" in origins and self.cors_allow_credentials:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return origins

    @property
    def allowed_image_mime_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_image_mime_types.split(",") if item.strip()}

    @property
    def allowed_log_mime_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_log_mime_types.split(",") if item.strip()}

    @property
    def allowed_kb_extension_set(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_kb_file_extensions.split(",") if item.strip()}

    @property
    def ocr_required_language_list(self) -> list[str]:
        return [item.strip() for item in self.ocr_required_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
