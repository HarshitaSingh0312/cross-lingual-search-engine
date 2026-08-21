import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # matches existing doc_id (e.g. "en_233")
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), index=True)
    domain: Mapped[str] = mapped_column(String(32), default="wikipedia")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    embedding: Mapped["Embedding"] = relationship(back_populates="document", uselist=False)


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    model_name: Mapped[str] = mapped_column(String(128), default=settings.embedding_model_name)
    vector: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    document: Mapped["Document"] = relationship(back_populates="embedding")

    __table_args__ = (
        # HNSW index for fast approximate cosine-distance search at query time.
        Index(
            "ix_embeddings_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )
