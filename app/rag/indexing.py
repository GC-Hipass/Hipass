"""문서 업로드 -> 텍스트 추출 -> chunking -> embedding -> Vector DB 저장."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import EmbeddingFailed
from app.rag.chunker import chunk_text
from app.rag.parser import extract_text
from app.rag.providers import EmbeddingProvider, get_embedding_provider
from app.rag.vectorstore import PgVectorStore

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    chunk_count: int
    text_length: int


class DocumentIndexer:
    """업로드된 문서를 RAG 인덱스에 적재."""

    def __init__(
        self,
        db: Session,
        *,
        embedder: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ):
        self._db = db
        self._embedder = embedder or get_embedding_provider()
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
        chunks = chunk_text(
            text,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )
        if not chunks:
            raise EmbeddingFailed("chunk를 생성할 수 없습니다.")

        embeddings = self._embedder.embed_batch(chunks)
        self._store.insert_document_chunks(
            document_id=document_id,
            session_id=session_id,
            contents=chunks,
            embeddings=embeddings,
            metadata=metadata or {"file_type": file_type},
        )
        return IndexingResult(chunk_count=len(chunks), text_length=len(text))
