from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.rag.providers import EmbeddingProvider, get_embedding_provider
from app.rag.retrieval.reranker import rerank
from app.rag.vectorstore import PgVectorStore, RetrievedChunk

_KOREAN_STOPWORDS = {"이", "그", "저", "것", "수", "등", "및", "또는", "그리고"}


def _extract_keywords(text: str, *, limit: int = 5) -> list[str]:
    tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", text)
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in _KOREAN_STOPWORDS or low in seen:
            continue
        seen.add(low)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


@dataclass
class RetrievalContext:
    uploaded: list[RetrievedChunk]
    company: list[RetrievedChunk]
    technical: list[RetrievedChunk]
    personality: list[RetrievedChunk]

    def merged(self) -> list[RetrievedChunk]:
        return [*self.uploaded, *self.company, *self.technical, *self.personality]


class HybridRetriever:
    """업로드 문서 + 사전 지식 chunk를 메타데이터 필터링 + semantic + 키워드로 검색."""

    def __init__(
        self,
        db: Session,
        *,
        embedder: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ):
        self._store = PgVectorStore(db)
        self._embedder = embedder or get_embedding_provider()
        self._settings = settings or get_settings()

    def retrieve_uploaded(self, *, session_id: int, queries: list[str]) -> list[RetrievedChunk]:
        s = self._settings
        seen: list[RetrievedChunk] = []
        for q in queries:
            emb = self._embedder.embed(q)
            seen.extend(
                self._store.search_uploaded(
                    session_id=session_id, query_embedding=emb, top_k=s.retrieval_top_k
                )
            )
            keywords = _extract_keywords(q)
            seen.extend(
                self._store.keyword_search_uploaded(
                    session_id=session_id, keywords=keywords, top_k=s.retrieval_top_k // 2 or 1
                )
            )
        return rerank(seen, top_k=s.rerank_top_k)

    def retrieve_knowledge(
        self,
        *,
        source_type: str,
        queries: list[str],
        company: str | None = None,
        job_role: str | None = None,
        difficulty: str | None = None,
    ) -> list[RetrievedChunk]:
        s = self._settings
        seen: list[RetrievedChunk] = []
        for q in queries:
            emb = self._embedder.embed(q)
            seen.extend(
                self._store.search_knowledge(
                    query_embedding=emb,
                    source_type=source_type,
                    company=company,
                    job_role=job_role,
                    difficulty=difficulty,
                    top_k=s.retrieval_top_k,
                )
            )
        return rerank(seen, top_k=s.rerank_top_k)

    def retrieve_question_context(
        self,
        *,
        session_id: int,
        company: str,
        job_role: str,
        difficulty: str,
    ) -> RetrievalContext:
        uploaded = self.retrieve_uploaded(
            session_id=session_id,
            queries=[
                f"{job_role} 직무 면접에서 검증할 핵심 역량",
                f"{company} {job_role} 관련 경험과 프로젝트",
            ],
        )
        company_ctx = self.retrieve_knowledge(
            source_type="company_profile",
            queries=[f"{company} 인재상", f"{company} 핵심 가치"],
            company=company,
        )
        technical = self.retrieve_knowledge(
            source_type="technical_knowledge",
            queries=[
                f"{job_role} 핵심 개발 지식",
                f"{difficulty} 난이도 {job_role} 기술 면접 주제",
            ],
            job_role=job_role,
            difficulty=difficulty,
        )
        personality = self.retrieve_knowledge(
            source_type="personality_question",
            queries=["인성 면접 질문", "협업 가치관"],
        )
        return RetrievalContext(
            uploaded=uploaded,
            company=company_ctx,
            technical=technical,
            personality=personality,
        )

    def retrieve_evaluation_context(
        self,
        *,
        session_id: int,
        question: str,
        company: str,
        job_role: str,
        difficulty: str,
    ) -> list[RetrievedChunk]:
        emb = self._embedder.embed(question)
        s = self._settings

        uploaded = self._store.search_uploaded(
            session_id=session_id, query_embedding=emb, top_k=s.retrieval_top_k
        )
        technical = self._store.search_knowledge(
            query_embedding=emb,
            source_type="technical_knowledge",
            job_role=job_role,
            difficulty=difficulty,
            top_k=s.retrieval_top_k,
        )
        company_ctx = self._store.search_knowledge(
            query_embedding=emb,
            source_type="company_profile",
            company=company,
            top_k=s.retrieval_top_k // 2 or 1,
        )
        return rerank([*uploaded, *technical, *company_ctx], top_k=s.rerank_top_k)
