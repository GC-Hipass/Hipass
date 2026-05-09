"""ObjectStorage 키 규칙을 한 곳에 모은다."""
from __future__ import annotations

from app.rag.providers import ObjectStorage, get_object_storage


def question_audio_key(question_id: int) -> str:
    return f"tts/questions/{question_id}.mp3"


def answer_audio_key(session_id: int, question_id: int, ext: str) -> str:
    ext = ext.lstrip(".")
    return f"answers/sessions/{session_id}/q{question_id}.{ext}"


def upload_document_key(session_id: int, filename: str) -> str:
    return f"uploads/sessions/{session_id}/{filename}"


def get_storage() -> ObjectStorage:
    return get_object_storage()
