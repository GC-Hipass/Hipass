from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import QuestionNotFound, TTSFailed
from app.db.models import InterviewQuestion, InterviewSession
from app.rag.pipelines import QuestionGenerationPipeline
from app.rag.providers import get_tts_provider
from app.services import storage_service

logger = logging.getLogger(__name__)


def generate_questions_and_tts(
    db: Session, *, session: InterviewSession
) -> list[InterviewQuestion]:
    """RAG로 질문 5개 생성 + Clova Voice로 TTS 생성 + 저장."""
    pipeline = QuestionGenerationPipeline(db)
    generated = pipeline.run(
        session_id=session.id,
        company=session.company,
        difficulty=session.difficulty,
        job_role=session.job_role,
        question_count=session.question_count,
    )

    questions: list[InterviewQuestion] = []
    for g in generated:
        q = InterviewQuestion(
            session_id=session.id,
            order=g.order,
            question_type=g.question_type,
            question=g.question,
        )
        db.add(q)
        questions.append(q)
    db.flush()  # id 확보

    tts = get_tts_provider()
    storage = storage_service.get_storage()
    for q in questions:
        try:
            result = tts.synthesize(q.question)
        except TTSFailed:
            raise
        except Exception as e:  # noqa: BLE001
            raise TTSFailed(str(e)) from e

        key = storage_service.question_audio_key(q.id)
        path = storage.put(key, result.audio_bytes, content_type=result.content_type)
        q.tts_audio_path = path
        q.tts_duration_seconds = result.duration_seconds
    db.flush()

    return questions


def get_question_by_order(db: Session, *, session_id: int, order: int) -> InterviewQuestion:
    stmt = select(InterviewQuestion).where(
        InterviewQuestion.session_id == session_id, InterviewQuestion.order == order
    )
    q = db.execute(stmt).scalar_one_or_none()
    if not q:
        raise QuestionNotFound(f"세션 {session_id}의 {order}번째 질문을 찾을 수 없습니다.")
    return q


def get_question_by_id(db: Session, question_id: int) -> InterviewQuestion:
    q = db.get(InterviewQuestion, question_id)
    if not q:
        raise QuestionNotFound(f"질문 {question_id}을(를) 찾을 수 없습니다.")
    return q


def get_question_audio(db: Session, question_id: int) -> tuple[bytes, str]:
    q = get_question_by_id(db, question_id)
    if not q.tts_audio_path:
        raise QuestionNotFound(f"질문 {question_id}의 TTS가 생성되지 않았습니다.")
    storage = storage_service.get_storage()
    key = storage_service.question_audio_key(question_id)
    return storage.get(key), "audio/mpeg"
