import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.user)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


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


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable: search is usable while logged out, so not every query has an owner.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    query_text: Mapped[str] = mapped_column(Text)
    model_used: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    results: Mapped[list["SearchResult"]] = relationship(back_populates="search_query")


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_queries.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    rank: Mapped[int] = mapped_column()
    score: Mapped[float] = mapped_column()

    search_query: Mapped["SearchQuery"] = relationship(back_populates="results")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_results.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_relevant: Mapped[bool] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        # One vote per (result, user) for logged-in users, so resubmitting updates rather than
        # duplicates. Doesn't dedupe anonymous votes (user_id NULL) - Postgres treats every NULL
        # as distinct in a unique index, and there's no identity to key an anonymous vote on anyway.
        Index("ix_feedback_result_user_unique", "search_result_id", "user_id", unique=True),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    document: Mapped["Document"] = relationship()

    __table_args__ = (Index("ix_bookmarks_user_document_unique", "user_id", "document_id", unique=True),)
