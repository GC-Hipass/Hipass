import time

from fastapi import APIRouter, Path
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.core.exceptions import SessionNotCompleted
from app.schemas.evaluation import EvaluationResultResponse
from app.services import evaluation_service, session_service

router = APIRouter()

RESULT_WAIT_TIMEOUT_SECONDS = 300
RESULT_WAIT_INTERVAL_SECONDS = 2


@router.get("/{session_id}/result", response_model=EvaluationResultResponse)
def get_result(
    session_id: int = Path(..., ge=1),
    db: Session = DBSession,
) -> EvaluationResultResponse:
    deadline = time.monotonic() + RESULT_WAIT_TIMEOUT_SECONDS

    while True:
        db.expire_all()
        session = session_service.get_session(db, session_id)
        evaluation = evaluation_service.get_evaluation_or_none(db, session_id)
        if evaluation is not None:
            break
        if session.status == "evaluation_failed":
            raise SessionNotCompleted("Evaluation failed.")
        if time.monotonic() >= deadline:
            raise SessionNotCompleted("Evaluation result is not ready yet.")
        time.sleep(RESULT_WAIT_INTERVAL_SECONDS)

    payload = evaluation_service.to_payload(evaluation)
    return EvaluationResultResponse(
        session_id=session_id,
        evaluation_id=payload.evaluation_id,
        total_score=payload.total_score,
        grade=payload.grade,
        qa_list=payload.qa_list,
        analysis=payload.analysis,
    )
