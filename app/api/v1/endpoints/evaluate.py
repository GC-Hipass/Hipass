from fastapi import APIRouter, File, Form, Path, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.schemas.answer import AnswerResponse
from app.services import answer_service, evaluation_service, session_service

router = APIRouter()


@router.post("/{session_id}/evaluate", response_model=AnswerResponse)
async def submit_answer(
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
    evaluation_payload = None
    if is_session_completed:
        evaluation = evaluation_service.evaluate_session(db, session=session)
        evaluation_payload = evaluation_service.to_payload(evaluation)

    db.commit()

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
        is_evaluated=evaluation_payload is not None,
        evaluation=evaluation_payload,
    )
