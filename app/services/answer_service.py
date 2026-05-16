from __future__ import annotations

import logging
from pathlib import PurePath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AnswerAlreadyExists,
    InvalidAudioFile,
    QuestionNotFound,
)
from app.db.models import InterviewAnswer, InterviewQuestion
from app.rag.providers import get_stt_provider
from app.schemas.common import SUPPORTED_AUDIO_MIME
from app.services import storage_service

logger = logging.getLogger(__name__)

_ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".mp4"}


def _validate_audio(filename: str, content_type: str | None) -> str:
    ext = PurePath(filename).suffix.lower()
    if ext not in _ALLOWED_EXTS and (content_type or "").lower() not in SUPPORTED_AUDIO_MIME:
        raise InvalidAudioFile(f"지원하지 않는 오디오: name={filename} type={content_type}")
    return ext.lstrip(".") or "wav"


def _ensure_question_in_session(
    db: Session, *, session_id: int, question_id: int
) -> InterviewQuestion:
    q = db.get(InterviewQuestion, question_id)
    if not q or q.session_id != session_id:
        raise QuestionNotFound(f"세션 {session_id}에 질문 {question_id}이(가) 없습니다.")
    return q


def _ensure_no_duplicate(db: Session, *, session_id: int, question_id: int) -> None:
    stmt = select(InterviewAnswer).where(
        InterviewAnswer.session_id == session_id,
        InterviewAnswer.question_id == question_id,
    )
    if db.execute(stmt).scalar_one_or_none():
        raise AnswerAlreadyExists(f"질문 {question_id}에는 이미 답변이 존재합니다.")


def store_answer(
    db: Session,
    *,
    session_id: int,
    question_id: int,
    audio_bytes: bytes,
    audio_filename: str,
    content_type: str | None,
    recording_duration_seconds: int,
) -> InterviewAnswer:
    """오디오 저장 -> Clova Speech STT -> answer_text 저장."""
    question = _ensure_question_in_session(
        db, session_id=session_id, question_id=question_id
    )
    _ensure_no_duplicate(db, session_id=session_id, question_id=question_id)

    ext = _validate_audio(audio_filename, content_type)

    storage = storage_service.get_voice_store()
    key = storage_service.answer_audio_key(session_id, question_id, ext)
    audio_path = storage.put(key, audio_bytes, content_type=content_type or "audio/mpeg")

    stt = get_stt_provider()
    answer_text = ""
    if audio_bytes:
        answer_text = stt.transcribe(audio_bytes, content_type=content_type or "audio/mpeg").strip()
    if not answer_text:
        logger.info(
            "empty answer accepted without STT error: session=%s question=%s duration=%s bytes=%s",
            session_id,
            question_id,
            recording_duration_seconds,
            len(audio_bytes),
        )

    answer = InterviewAnswer(
        session_id=session_id,
        question_id=question_id,
        order=question.order,
        audio_path=audio_path,
        answer_text=answer_text,
        stt_provider=stt.name,
        recording_duration_seconds=recording_duration_seconds,
    )
    db.add(answer)
    db.flush()
    return answer


def count_answers(db: Session, session_id: int) -> int:
    stmt = select(func.count()).select_from(InterviewAnswer).where(
        InterviewAnswer.session_id == session_id
    )
    return int(db.execute(stmt).scalar_one())


def list_answers(db: Session, session_id: int) -> list[InterviewAnswer]:
    stmt = (
        select(InterviewAnswer)
        .where(InterviewAnswer.session_id == session_id)
        .order_by(InterviewAnswer.order.asc())
    )
    return list(db.execute(stmt).scalars().all())
