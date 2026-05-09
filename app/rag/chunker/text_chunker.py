from __future__ import annotations

import re

_PARAGRAPH_RE = re.compile(r"\n{2,}")


def _split_paragraphs(text: str) -> list[str]:
    parts = _PARAGRAPH_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """문단 단위로 묶어 chunk_size를 넘지 않게 분할하고, overlap만큼 슬라이딩.

    한국어 문서의 단순 split도 잘 동작하도록 문단 → 문장 폴백 구조.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be in [0, chunk_size)")

    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            # 너무 긴 문단은 크기 단위로 슬라이스
            for i in range(0, len(para), chunk_size - chunk_overlap):
                piece = para[i : i + chunk_size]
                if piece.strip():
                    chunks.append(piece)
            continue

        if not buf:
            buf = para
            continue

        candidate = f"{buf}\n\n{para}"
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            chunks.append(buf)
            # overlap 적용
            tail = buf[-chunk_overlap:] if chunk_overlap else ""
            buf = f"{tail}\n\n{para}".strip()

    if buf:
        chunks.append(buf)

    # 빈 chunk 제거
    return [c for c in chunks if c.strip()]
