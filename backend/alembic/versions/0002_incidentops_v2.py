"""incidentops v2 analysis, evidence, and lifecycle columns

Revision ID: 0002_incidentops_v2
Revises: 0001_initial
Create Date: 2026-06-24
"""

from datetime import datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0002_incidentops_v2"
down_revision = "0001_initial"
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
    _add("ticketattachment", sa.Column("mime_type", sa.String(), nullable=True))
    _add("ticketattachment", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    _add("ticketattachment", sa.Column("checksum", sa.String(), nullable=True))

    _add("knowledgebasearticle", sa.Column("source_name", sa.String(), nullable=True))
    _add("knowledgebasearticle", sa.Column("source_type", sa.String(), nullable=False, server_default="manual"))
    _add("knowledgebasearticle", sa.Column("source_checksum", sa.String(), nullable=True))
    _add("knowledgebasearticle", sa.Column("version", sa.String(), nullable=False, server_default="v1"))
    _add("knowledgebasearticle", sa.Column("updated_at", sa.DateTime(), nullable=True))
    _add("knowledgebasearticle", sa.Column("ingestion_status", sa.String(), nullable=False, server_default="ready"))
    _add("knowledgebasearticle", sa.Column("index_status", sa.String(), nullable=False, server_default="stale"))

    _add("aireview", sa.Column("run_id", sa.String(), nullable=True))
    _add("aireview", sa.Column("review_reasons", sa.JSON(), nullable=True))
    _add("aireview", sa.Column("correction_reason", sa.Text(), nullable=True))

    _add("aianalysisaudit", sa.Column("run_id", sa.String(), nullable=True))
    _add("aianalysisaudit", sa.Column("trace_id", sa.String(), nullable=True))
    _add("aianalysisaudit", sa.Column("index_version", sa.String(), nullable=True))
    _add("aianalysisaudit", sa.Column("corpus_hash", sa.String(), nullable=True))
    _add("aianalysisaudit", sa.Column("chunking_config", sa.JSON(), nullable=True))
    _add("aianalysisaudit", sa.Column("stage_traces", sa.JSON(), nullable=True))
    _add("aianalysisaudit", sa.Column("final_decision", sa.JSON(), nullable=True))
    _add("aianalysisaudit", sa.Column("resolution", sa.JSON(), nullable=True))
    _add("aianalysisaudit", sa.Column("candidate_sources", sa.JSON(), nullable=True))
    _add("aianalysisaudit", sa.Column("previous_diff", sa.JSON(), nullable=True))

    bind = op.get_bind()
    now = datetime.utcnow().isoformat()
    bind.execute(sa.text("UPDATE knowledgebasearticle SET updated_at = COALESCE(updated_at, :now)"), {"now": now})
    rows = bind.execute(sa.text("SELECT id FROM aianalysisaudit WHERE run_id IS NULL OR trace_id IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE aianalysisaudit SET run_id = COALESCE(run_id, :run_id), trace_id = COALESCE(trace_id, :trace_id) WHERE id = :id"),
            {"run_id": f"legacy-{row.id}-{uuid4().hex[:8]}", "trace_id": f"legacy-{uuid4().hex[:12]}", "id": row.id},
        )


def downgrade() -> None:
    # SQLite cannot reliably drop columns without table rebuild; keep downgrade intentionally no-op.
    pass
