from __future__ import annotations

import re
from typing import Literal

# 1. 정규식 정의 (한국어/영어 및 노이즈 제거)
_EXCESS_NEWLINE_RE = re.compile(r"\n{3,}")
_PDF_PAGE_NUM_RE = re.compile(r"^\s*-?\s*\d+\s*-?\s*$", re.MULTILINE)
_EN_ABBR_RE = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof|vs|etc|No|Fig|vol|pp|ed)\.", re.IGNORECASE)
_SEMANTIC_BOUNDARY_RE = re.compile(
    r"""
    (?:\n\s*\n+)         # large blank gaps
    |(?<=[。！？])                                      # 한자권 종결
    |(?<=[!?])(?=\s)                                    # 영어 종결
    |(?<=\.)(?=\s+[A-Z가-힣])                           # 마침표+공백+대문자/한글
    |(?<=[다까요죠니다군요네요습니다겠습니다]\.)\s+      # 한국어 종결어미 특화
    """,
    re.VERBOSE
)


# 2. 내부 로직 함수 (표 처리 및 분할)
def _preprocess(text: str, source_type: str) -> str:
    """문서 유형별 노이즈 제거."""
    if source_type == "pdf": 
        text = _PDF_PAGE_NUM_RE.sub("", text)
    elif source_type == "docx": 
        text = text.replace("\t", "  ")
    return _EXCESS_NEWLINE_RE.sub("\n\n", text).strip()

def _is_markdown_table(block: str) -> bool:
    """3단 검증으로 실제 표인지 확인."""
    lines = [l for l in block.splitlines() if l.strip()]
    if len(lines) < 3: return False
    has_header = bool(re.search(r"\|.*\|", lines[0]))
    has_sep = bool(re.match(r"^\s*\|?([\s\-:]+\|)+[\s\-:]*\|?\s*$", lines[1]))
    return has_header and has_sep

def _chunk_table(table_text: str, chunk_size: int) -> list[str]:
    """표 분할 시 헤더를 모든 청크 상단에 복사."""
    if len(table_text) <= chunk_size: return [table_text]
    lines = table_text.splitlines()
    header = "\n".join(lines[:2])
    data_lines = lines[2:]
    
    chunks, current_rows = [], []
    for row in data_lines:
        candidate = header + "\n" + "\n".join(current_rows + [row])
        if len(candidate) > chunk_size and current_rows:
            chunks.append(header + "\n" + "\n".join(current_rows))
            current_rows = [row]
        else: current_rows.append(row)
    if current_rows: chunks.append(header + "\n" + "\n".join(current_rows))
    return chunks

def _split_sentences(text: str) -> list[str]:
    """약어 보호 처리 후 문장 분리."""
    protected = _EN_ABBR_RE.sub(lambda m: m.group(0).replace(".", "[[DOT]]"), text)
    parts = _SEMANTIC_BOUNDARY_RE.split(protected)
    return [p.replace("[[DOT]]", ".").strip() for p in parts if p.strip()]

def _pack_units(units: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """문장 단위들을 결합하며 overlap 적용."""
    chunks, current_parts, current_len = [], [], 0
    for unit in units:
        unit_len = len(unit)
        sep_len = 2 if current_parts else 0
        if current_len + sep_len + unit_len > chunk_size and current_parts:
            chunks.append("\n\n".join(current_parts))
            # overlap: 직전 텍스트의 끝부분 추출
            overlap_text = chunks[-1][-chunk_overlap:] if chunk_overlap > 0 else ""
            current_parts = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)
            sep_len = 2 if current_parts else 0
        current_parts.append(unit)
        current_len += sep_len + unit_len
    if current_parts: chunks.append("\n\n".join(current_parts))
    return chunks

# 3. 메인 공개 API (기존 인터페이스 유지)
def chunk_text(
    text: str, 
    *, 
    chunk_size: int = 500, 
    chunk_overlap: int = 50, 
    source_type: Literal["pdf", "docx", "txt"] = "txt"
) -> list[str]:
    """
    고도화된 청킹 로직을 수행하고 문자열 리스트(list[str])를 반환합니다.
    DB 연동 시 문제 없도록 기존 인터페이스를 완벽히 준수합니다.
    """
    if not text or not text.strip(): return []
    
    # 전처리
    text = _preprocess(text, source_type)
    
    # 텍스트/표 블록 구분
    lines = text.split("\n")
    blocks, current, in_table = [], [], False
    for line in lines:
        maybe_table = "|" in line
        if maybe_table != in_table and current:
            joined = "\n".join(current)
            blocks.append((joined, in_table and _is_markdown_table(joined)))
            current = []
        in_table, current = maybe_table, current + [line]
    if current:
        joined = "\n".join(current)
        blocks.append((joined, in_table and _is_markdown_table(joined)))

    final_chunks = []
    for block_text, is_table in blocks:
        if not block_text.strip(): continue
        
        if is_table:
            # 표 전용 청킹
            final_chunks.extend(_chunk_table(block_text, chunk_size))
        else:
            # 일반 텍스트 청킹
            sentences = _split_sentences(block_text)
            sized = []
            for s in sentences:
                if len(s) > chunk_size: # 문장 하나가 chunk_size보다 큰 경우 예외처리
                    sized.extend([s[i:i+chunk_size] for i in range(0, len(s), chunk_size)])
                else: sized.append(s)
            final_chunks.extend(_pack_units(sized, chunk_size, chunk_overlap))

    return [c.strip() for c in final_chunks if c.strip()]