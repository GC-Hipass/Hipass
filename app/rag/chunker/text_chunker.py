from __future__ import annotations

import re

_SEMANTIC_BOUNDARY_RE = re.compile(
    r"""
    (?:\n\s*\n+)         # large blank gaps
    |(?:[ \t]{2,})       # two or more spaces
    |(?:\n+)             # line breaks
    |(?<=[.!?])(?:\s+|$) # sentence endings
    """,
    re.VERBOSE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _split_semantic_units(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    return [part.strip() for part in _SEMANTIC_BOUNDARY_RE.split(normalized) if part.strip()]


def _joined_length(units: list[str]) -> int:
    if not units:
        return 0
    return sum(len(unit) for unit in units) + (len(units) - 1)


def _tail_units_for_overlap(units: list[str], max_chars: int) -> list[str]:
    if max_chars <= 0 or not units:
        return []

    tail: list[str] = []
    total = 0
    for unit in reversed(units):
        add_len = len(unit) if not tail else len(unit) + 1
        if tail and total + add_len > max_chars:
            break
        if not tail and len(unit) > max_chars:
            return []
        tail.append(unit)
        total += add_len

    tail.reverse()
    return tail


def _split_long_word(word: str, *, chunk_size: int) -> list[str]:
    return [word[i : i + chunk_size] for i in range(0, len(word), chunk_size) if word[i : i + chunk_size]]


def _expand_oversized_unit(unit: str, *, chunk_size: int) -> list[str]:
    if len(unit) <= chunk_size:
        return [unit]

    words = [word for word in _WHITESPACE_RE.split(unit) if word]
    if len(words) <= 1:
        return _split_long_word(unit, chunk_size=chunk_size)

    expanded: list[str] = []
    buf: list[str] = []

    for word in words:
        if len(word) > chunk_size:
            if buf:
                expanded.append(" ".join(buf))
                buf = []
            expanded.extend(_split_long_word(word, chunk_size=chunk_size))
            continue

        candidate = [*buf, word]
        if _joined_length(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                expanded.append(" ".join(buf))
            buf = [word]

    if buf:
        expanded.append(" ".join(buf))

    return expanded


def _pack_units(units: list[str], *, chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    for unit in units:
        if not current:
            current = [unit]
            continue

        candidate = [*current, unit]
        if _joined_length(candidate) <= chunk_size:
            current = candidate
            continue

        chunks.append(" ".join(current))
        overlap_units = _tail_units_for_overlap(current, chunk_overlap)
        candidate_with_overlap = [*overlap_units, unit] if overlap_units else [unit]

        if _joined_length(candidate_with_overlap) <= chunk_size:
            current = candidate_with_overlap
        else:
            current = [unit]

    if current:
        chunks.append(" ".join(current))

    return [chunk.strip() for chunk in chunks if chunk.strip()]


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text with semantic boundaries first, then pack into size-limited chunks.

    Preferred boundaries:
    - two or more spaces
    - line breaks
    - sentence endings (., !, ?)
    - large blank gaps
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be in [0, chunk_size)")

    semantic_units = _split_semantic_units(text)
    if not semantic_units:
        return []

    sized_units: list[str] = []
    for unit in semantic_units:
        sized_units.extend(_expand_oversized_unit(unit, chunk_size=chunk_size))

    return _pack_units(sized_units, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
