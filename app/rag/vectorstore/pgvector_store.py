from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import DocumentChunk, KnowledgeChunk


@dataclass
class RetrievedChunk:
    content: str
    score: float
    source: str  # "uploaded" | "knowledge"
    metadata: dict[str, Any]


class PgVectorStore:
    """pgvector 기반 검색.

    업로드 문서 chunk와 사전 임베딩 knowledge chunk 두 컬렉션을 모두 다룬다.
    """

    def __init__(self, db: Session):
        self._db = db

    # ------------- 업로드 문서 -------------

    def insert_document_chunks(
        self,
        *,
        document_id: int,
        session_id: int,
        contents: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if len(contents) != len(embeddings):
            raise ValueError("contents and embeddings length mismatch")
        for idx, (content, vec) in enumerate(zip(contents, embeddings, strict=True)):
            self._db.add(
                DocumentChunk(
                    document_id=document_id,
                    session_id=session_id,
                    chunk_index=idx,
                    content=content,
                    embedding=vec,
                    chunk_metadata=metadata or {},
                )
            )
        self._db.flush()

    def search_uploaded(
        self,
        *,
        session_id: int,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(DocumentChunk, distance.label("distance"))
            .where(DocumentChunk.session_id == session_id)
            .order_by(distance.asc())
            .limit(top_k)
        )
        rows = self._db.execute(stmt).all()
        return [
            RetrievedChunk(
                content=row[0].content,
                score=1.0 - float(row[1]),
                source="uploaded",
                metadata=row[0].chunk_metadata or {},
            )
            for row in rows
        ]

    # ------------- 사전 지식 -------------

    def search_knowledge(
        self,
        *,
        query_embedding: list[float],
        source_type: str,
        company: str | None = None,
        job_role: str | None = None,
        difficulty: str | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
        stmt = select(KnowledgeChunk, distance.label("distance")).where(
            KnowledgeChunk.source_type == source_type
        )
        if company:
            stmt = stmt.where(
                (KnowledgeChunk.company == company) | (KnowledgeChunk.company.is_(None))
            )
        if job_role:
            stmt = stmt.where(
                (KnowledgeChunk.job_role == job_role) | (KnowledgeChunk.job_role.is_(None))
            )
        if difficulty:
            stmt = stmt.where(
                (KnowledgeChunk.difficulty == difficulty) | (KnowledgeChunk.difficulty.is_(None))
            )
        stmt = stmt.order_by(distance.asc()).limit(top_k)

        rows = self._db.execute(stmt).all()
        return [
            RetrievedChunk(
                content=row[0].content,
                score=1.0 - float(row[1]),
                source="knowledge",
                metadata={
                    **(row[0].chunk_metadata or {}),
                    "source_type": row[0].source_type,
                    "company": row[0].company,
                    "job_role": row[0].job_role,
                    "difficulty": row[0].difficulty,
                },
            )
            for row in rows
        ]

    # ------------- 키워드 검색 (Hybrid 보조) -------------

    def keyword_search_uploaded(
        self, *, session_id: int, keywords: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        if not keywords:
            return []
        ilike_conds = [DocumentChunk.content.ilike(f"%{kw}%") for kw in keywords]
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.session_id == session_id)
            .where(or_(*ilike_conds))
            .limit(top_k)
        )
        rows = self._db.execute(stmt).scalars().all()
        return [
            RetrievedChunk(
                content=row.content,
                score=0.5,
                source="uploaded",
                metadata=row.chunk_metadata or {},
            )
            for row in rows
        ]
