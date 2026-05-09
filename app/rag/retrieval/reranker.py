from __future__ import annotations

from app.rag.vectorstore import RetrievedChunk


def rerank(chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    """단순 스코어 기준 정렬 후 중복 본문 제거.

    실제 reranker(예: Cohere/CrossEncoder) 연동은 여기에 추가.
    """
    seen: set[str] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in sorted(chunks, key=lambda c: c.score, reverse=True):
        key = chunk.content.strip()[:200]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped[:top_k]
