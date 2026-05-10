"""ObjectStorage 키 규칙을 한 곳에 모은다."""
from __future__ import annotations

import re

from app.rag.providers import ObjectStorage, get_document_storage, get_voice_storage


def safe_filename(filename: str) -> str:
    """파일명에서 특수문자를 제거하고 공백을 밑줄로 치환한다."""
    filename = re.sub(r"[^\w\s\.-]", "", filename).strip()
    filename = re.sub(r"\s+", "_", filename)
    return filename


def question_audio_key(question_id: int) -> str:
    return f"tts/questions/{question_id}.mp3"


def answer_audio_key(session_id: int, question_id: int, ext: str) -> str:
    ext = ext.lstrip(".")
    return f"answers/sessions/{session_id}/q{question_id}.{ext}"


def upload_document_key(session_id: int, filename: str) -> str:
    return f"uploads/sessions/{session_id}/{safe_filename(filename)}"


def get_voice_store() -> ObjectStorage:
    """TTS 질문 오디오, 답변 녹음 파일 스토리지."""
    return get_voice_storage()


def get_document_store() -> ObjectStorage:
    """업로드 문서 스토리지."""
    return get_document_storage()
