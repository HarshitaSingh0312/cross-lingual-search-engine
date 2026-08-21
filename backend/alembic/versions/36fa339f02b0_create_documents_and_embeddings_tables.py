"""create documents and embeddings tables

Revision ID: 36fa339f02b0
Revises: 
Create Date: 2026-08-21 20:10:17.685718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '36fa339f02b0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768  # LaBSE


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False, server_default="wikipedia"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_language", "documents", ["language"])

    op.create_table(
        "embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False, unique=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("vector", Vector(EMBEDDING_DIM), nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_embeddings_vector_hnsw ON embeddings "
        "USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_index("ix_documents_language", table_name="documents")
    op.drop_table("documents")
