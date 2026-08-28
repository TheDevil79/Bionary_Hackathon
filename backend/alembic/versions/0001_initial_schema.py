"""Initial schema: sources, evidence_chunks, claims, claim_evidence.

Revision ID: 0001
Revises: 
Create Date: 2026-08-28

Prerequisites:
  The pgvector extension must be enabled in PostgreSQL before running this migration:
    CREATE EXTENSION IF NOT EXISTS vector;
  
  For Supabase: enable it via the Supabase dashboard → Database → Extensions → vector.
"""
from __future__ import annotations

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── sources ───────────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("publisher", sa.String(256), nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("license", sa.String(128), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sources_content_hash", "sources", ["content_hash"])

    # ── evidence_chunks ───────────────────────────────────────────────────────
    op.create_table(
        "evidence_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evidence_chunks_source_id", "evidence_chunks", ["source_id"])
    # IVFFlat index for cosine ANN search — tune lists= for your corpus size
    op.execute(
        """
        CREATE INDEX ix_evidence_chunks_embedding
        ON evidence_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # ── claims ────────────────────────────────────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── claim_evidence ────────────────────────────────────────────────────────
    op.create_table(
        "claim_evidence",
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_chunks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relationship", sa.String(32), nullable=False),
        sa.Column("relevance_score", sa.Float, default=0.0),
        sa.UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence"),
    )


def downgrade() -> None:
    op.drop_table("claim_evidence")
    op.drop_table("claims")
    op.drop_index("ix_evidence_chunks_embedding", table_name="evidence_chunks")
    op.drop_table("evidence_chunks")
    op.drop_index("ix_sources_content_hash", table_name="sources")
    op.drop_table("sources")
