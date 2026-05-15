import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, Path, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.db.session import SessionLocal
from app.schemas.answer import AnswerResponse
from app.services import answer_service, evaluation_service, session_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _evaluate_session_background(*, session_id: int) -> None:
    db = SessionLocal()
    try:
        session = session_service.get_session(db, session_id)
        if evaluation_service.get_evaluation_or_none(db, session_id):
            return
        session_service.update_status(db, session, "evaluating")
        evaluation_service.evaluate_session(db, session=session)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("background evaluation failed: session=%s", session_id)
        db.rollback()
        try:
            session = session_service.get_session(db, session_id)
            session_service.update_status(db, session, "evaluation_failed")
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("failed to mark session as evaluation_failed: session=%s", session_id)
            db.rollback()
    finally:
        db.close()


@router.post("/{session_id}/evaluate", response_model=AnswerResponse)
async def submit_answer(
    background_tasks: BackgroundTasks,
    session_id: int = Path(..., ge=1),
    question_id: int = Form(..., ge=1),
    audio: UploadFile = File(...),
    recording_duration_seconds: int = Form(..., ge=0, le=600),
    db: Session = DBSession,
) -> AnswerResponse:
    session = session_service.get_session(db, session_id)
    audio_bytes = await audio.read()

    answer = answer_service.store_answer(
        db,
        session_id=session.id,
        question_id=question_id,
        audio_bytes=audio_bytes,
        audio_filename=audio.filename or "answer",
        content_type=audio.content_type,
        recording_duration_seconds=recording_duration_seconds,
    )

    answered_count = answer_service.count_answers(db, session.id)

    is_session_completed = answered_count >= session.question_count
    if is_session_completed:
        session_service.update_status(db, session, "evaluating")

    db.commit()

    if is_session_completed:
        background_tasks.add_task(_evaluate_session_background, session_id=session.id)

    return AnswerResponse(
        answer_id=answer.id,
        session_id=session.id,
        question_id=answer.question_id,
        order=answer.order,
        answer_text=answer.answer_text,
        stt_provider=answer.stt_provider,
        answered_count=answered_count,
        question_count=session.question_count,
        is_session_completed=is_session_completed,
        is_evaluated=False,
        evaluation=None,
    )
