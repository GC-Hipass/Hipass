import time

from fastapi import APIRouter, Path
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.core.exceptions import QuestionNotFound
from app.schemas.question import QuestionResponse
from app.services import question_service, session_service

router = APIRouter()

QUESTION_WAIT_TIMEOUT_SECONDS = 180
QUESTION_WAIT_INTERVAL_SECONDS = 1


@router.get("/{session_id}/questions/{order}", response_model=QuestionResponse)
def get_question(
    session_id: int = Path(..., ge=1),
    order: int = Path(..., ge=1, le=10),
    db: Session = DBSession,
) -> QuestionResponse:
    deadline = time.monotonic() + QUESTION_WAIT_TIMEOUT_SECONDS

    while True:
        db.expire_all()
        session = session_service.get_session(db, session_id)
        try:
            question = question_service.get_question_by_order(db, session_id=session_id, order=order)
            break
        except QuestionNotFound:
            if session.status == "question_generation_failed":
                raise
            if time.monotonic() >= deadline:
                raise
            time.sleep(QUESTION_WAIT_INTERVAL_SECONDS)

    return QuestionResponse(
        session_id=session.id,
        question_id=question.id,
        order=question.order,
        question=question.question,
        tts_audio_url=f"/api/v1/audio/questions/{question.id}",
        tts_duration_seconds=question.tts_duration_seconds,
        recording_seconds=session.recording_seconds,
    )
