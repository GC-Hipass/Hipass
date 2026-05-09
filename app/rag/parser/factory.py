from __future__ import annotations

import io
import logging

from app.core.exceptions import DocumentParseFailed, InvalidFileType

logger = logging.getLogger(__name__)


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _extract_docx(data: bytes) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_txt(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


_DISPATCH = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "txt": _extract_txt,
}


def extract_text(data: bytes, file_type: str) -> str:
    file_type = file_type.lower().lstrip(".")
    if file_type not in _DISPATCH:
        raise InvalidFileType(f"지원하지 않는 파일 형식: {file_type}")
    try:
        text = _DISPATCH[file_type](data)
    except InvalidFileType:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("document parse failed: %s", file_type)
        raise DocumentParseFailed(str(e)) from e

    text = text.strip()
    if not text:
        raise DocumentParseFailed("문서에서 텍스트를 추출할 수 없습니다.")
    return text
