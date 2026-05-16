"""Document parsing, chunking, embedding, and vector persistence."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import EmbeddingFailed
from app.db.models import KnowledgeDocument
from app.rag.chunker import chunk_text
from app.rag.parser import extract_text
from app.rag.vectorstore import PgVectorStore
from app.schemas.common import SUPPORTED_FILE_EXTENSIONS

if TYPE_CHECKING:
    from app.rag.providers import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    chunk_count: int
    text_length: int


@dataclass
class KnowledgeIndexingResult(IndexingResult):
    knowledge_document_id: int


def _normalize_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise EmbeddingFailed(f"unsupported file type: {ext or '(none)'}")
    return ext.lstrip(".")


def _build_chunks(*, text: str, settings: Settings, file_type: str) -> list[str]:
    return chunk_text(
        text,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        source_type=file_type,
    )


class DocumentIndexer:
    """Persist uploaded documents into document_chunks."""

    def __init__(
        self,
        db: Session,
        *,
        embedder: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ):
        if embedder is None:
            from app.rag.providers import get_embedding_provider

            embedder = get_embedding_provider()
        self._db = db
        self._embedder = embedder
        self._settings = settings or get_settings()
        self._store = PgVectorStore(db)

    def index(
        self,
        *,
        document_id: int,
        session_id: int,
        raw_bytes: bytes,
        file_type: str,
        metadata: dict | None = None,
    ) -> IndexingResult:
        text = extract_text(raw_bytes, file_type)
        chunks = _build_chunks(text=text, settings=self._settings, file_type=file_type)
        if not chunks:
            raise EmbeddingFailed("failed to build document chunks")

        embeddings = self._embedder.embed_batch(chunks)
        self._store.insert_document_chunks(
            document_id=document_id,
            session_id=session_id,
            contents=chunks,
            embeddings=embeddings,
            metadata=metadata or {"file_type": file_type},
        )
        return IndexingResult(chunk_count=len(chunks), text_length=len(text))


class KnowledgeIndexer:
    """Persist seed knowledge documents into knowledge tables."""

    def __init__(
        self,
        db: Session,
        *,
        embedder: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ):
        if embedder is None:
            from app.rag.providers import get_embedding_provider

            embedder = get_embedding_provider()
        self._db = db
        self._embedder = embedder
        self._settings = settings or get_settings()
        self._store = PgVectorStore(db)

    def index_text(
        self,
        *,
        source_type: str,
        title: str,
        content: str,
        company: str | None = None,
        job_role: str | None = None,
        difficulty: str | None = None,
        metadata: dict | None = None,
        content_type: str = "txt",
    ) -> KnowledgeIndexingResult:
        text = content.strip()
        if not text:
            raise EmbeddingFailed("knowledge content is empty")

        chunks = _build_chunks(text=text, settings=self._settings, file_type=content_type)
        if not chunks:
            raise EmbeddingFailed("failed to build knowledge chunks")

        document = KnowledgeDocument(
            source_type=source_type,
            company=company,
            job_role=job_role,
            difficulty=difficulty,
            title=title,
            content=text,
            doc_metadata=metadata or {},
        )
        self._db.add(document)
        self._db.flush()

        embeddings = self._embedder.embed_batch(chunks)
        self._store.insert_knowledge_chunks(
            knowledge_document_id=document.id,
            source_type=source_type,
            company=company,
            job_role=job_role,
            difficulty=difficulty,
            contents=chunks,
            embeddings=embeddings,
            metadata=metadata or {},
        )
        return KnowledgeIndexingResult(
            knowledge_document_id=document.id,
            chunk_count=len(chunks),
            text_length=len(text),
        )

    def index_file(
        self,
        *,
        source_type: str,
        title: str,
        path: str | Path,
        company: str | None = None,
        job_role: str | None = None,
        difficulty: str | None = None,
        metadata: dict | None = None,
    ) -> KnowledgeIndexingResult:
        file_path = Path(path)
        file_type = _normalize_file_type(file_path.name)
        raw_bytes = file_path.read_bytes()
        text = extract_text(raw_bytes, file_type)
        merged_metadata = {
            "file_name": file_path.name,
            "source_path": str(file_path),
            **(metadata or {}),
        }
        return self.index_text(
            source_type=source_type,
            title=title,
            content=text,
            company=company,
            job_role=job_role,
            difficulty=difficulty,
            metadata=merged_metadata,
            content_type=file_type,
        )
