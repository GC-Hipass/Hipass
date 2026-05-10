from __future__ import annotations

import hashlib
import logging
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidFileType
from app.db.models import Document
from app.rag.indexing import DocumentIndexer
from app.schemas.common import SUPPORTED_FILE_EXTENSIONS
from app.services import storage_service

logger = logging.getLogger(__name__)


def _file_type_from_name(filename: str) -> str:
    ext = PurePath(filename).suffix.lower()
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise InvalidFileType(f"지원하지 않는 파일 형식: {ext}")
    return ext.lstrip(".")


def store_and_index(
    db: Session,
    *,
    session_id: int,
    filename: str,
    raw_bytes: bytes,
) -> Document:
    """원본 파일을 ObjectStorage에 저장하고, RAG 인덱스를 적재한다."""
    file_type = _file_type_from_name(filename)
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    storage = storage_service.get_document_store()
    key = storage_service.upload_document_key(session_id, filename)
    storage_path = storage.put(key, raw_bytes)

    document = Document(
        session_id=session_id,
        filename=filename,
        file_type=file_type,
        file_hash=file_hash,
        storage_path=storage_path,
    )
    db.add(document)
    db.flush()

    indexer = DocumentIndexer(db)
    result = indexer.index(
        document_id=document.id,
        session_id=session_id,
        raw_bytes=raw_bytes,
        file_type=file_type,
        metadata={"filename": filename},
    )
    logger.info(
        "document indexed: session=%s document=%s chunks=%s text_len=%s",
        session_id,
        document.id,
        result.chunk_count,
        result.text_length,
    )
    return document
