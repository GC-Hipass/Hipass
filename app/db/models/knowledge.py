from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base, TimestampMixin

_settings = get_settings()


class KnowledgeDocument(Base, TimestampMixin):
    """사전 임베딩 문서 (기업 인재상, 기술 지식, 인성 질문 등)."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # company_profile | technical_knowledge | personality_question
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    job_role: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    job_role: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(_settings.embedding_dimension), nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
