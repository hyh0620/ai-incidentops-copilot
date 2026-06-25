"""kb ingestion runs and versioned chunk metadata

Revision ID: 0003_kb_ingestion_platform
Revises: 0002_incidentops_v2
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_kb_ingestion_platform"
down_revision = "0002_incidentops_v2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("kbingestionrun"):
        op.create_table(
            "kbingestionrun",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("source_filename", sa.String(), nullable=True),
            sa.Column("source_type", sa.String(), nullable=True),
            sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("embedding_provider", sa.String(), nullable=False, server_default="local_hash_embedding_fallback"),
            sa.Column("embedding_model", sa.String(), nullable=True),
            sa.Column("kb_version", sa.String(), nullable=False, server_default="kb-v1"),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("fallback_reason", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_kbingestionrun_status", "kbingestionrun", ["status"])
        op.create_index("ix_kbingestionrun_source_filename", "kbingestionrun", ["source_filename"])
        op.create_index("ix_kbingestionrun_source_type", "kbingestionrun", ["source_type"])
        op.create_index("ix_kbingestionrun_embedding_provider", "kbingestionrun", ["embedding_provider"])
        op.create_index("ix_kbingestionrun_embedding_model", "kbingestionrun", ["embedding_model"])
        op.create_index("ix_kbingestionrun_kb_version", "kbingestionrun", ["kb_version"])
        op.create_index("ix_kbingestionrun_started_at", "kbingestionrun", ["started_at"])
        op.create_index("ix_kbingestionrun_completed_at", "kbingestionrun", ["completed_at"])

    _add("knowledgebasearticle", sa.Column("source_filename", sa.String(), nullable=True))
    _add("knowledgebasearticle", sa.Column("page_count", sa.Integer(), nullable=True))
    _add("knowledgebasearticle", sa.Column("ingestion_run_id", sa.Integer(), nullable=True))
    _add("knowledgebasearticle", sa.Column("kb_version", sa.String(), nullable=False, server_default="kb-v1"))

    _add("knowledgebasechunk", sa.Column("page_number", sa.Integer(), nullable=True))
    _add("knowledgebasechunk", sa.Column("kb_version", sa.String(), nullable=False, server_default="kb-v1"))
    _add("knowledgebasechunk", sa.Column("ingestion_run_id", sa.Integer(), nullable=True))

    bind.execute(sa.text("UPDATE knowledgebasearticle SET kb_version = COALESCE(kb_version, version, 'kb-v1')"))
    bind.execute(sa.text("UPDATE knowledgebasechunk SET kb_version = COALESCE(kb_version, 'kb-v1')"))


def downgrade() -> None:
    # SQLite column drops require table rebuilds; keep downgrade no-op for local demo migrations.
    pass
