"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_conversations_client_id", "conversations", ["client_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("conversation_id", sa.String(32),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        _ts("created_at"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    op.create_table(
        "sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        _ts("last_ingested_at", nullable=True),
        _ts("created_at"),
    )
    op.create_index("ix_sources_domain", "sources", ["domain"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_id", sa.String(32), sa.ForeignKey("sources.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("pages_discovered", sa.Integer(), nullable=False),
        sa.Column("pages_fetched", sa.Integer(), nullable=False),
        sa.Column("pages_indexed", sa.Integer(), nullable=False),
        sa.Column("pages_unchanged", sa.Integer(), nullable=False),
        sa.Column("pages_skipped", sa.Integer(), nullable=False),
        sa.Column("pages_failed", sa.Integer(), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("started_at", nullable=True),
        _ts("finished_at", nullable=True),
    )
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source_id", sa.String(32), sa.ForeignKey("sources.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("published_at", sa.String(64), nullable=True),
        _ts("fetched_at"),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("source_id", "url", name="uq_document_source_url"),
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_source_id", "chunks", ["source_id"])
    op.create_index("ix_chunks_document_ordinal", "chunks", ["document_id", "ordinal"])

    op.create_table(
        "itineraries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(32),
                  sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_itineraries_client_id", "itineraries", ["client_id"])
    op.create_index("ix_itineraries_conversation_id", "itineraries", ["conversation_id"])


def downgrade() -> None:
    for table in ("itineraries", "chunks", "documents", "ingestion_jobs", "sources", "messages",
                  "conversations"):
        op.drop_table(table)
