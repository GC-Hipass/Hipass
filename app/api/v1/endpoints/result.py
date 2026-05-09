from fastapi import APIRouter, Path
from sqlalchemy.orm import Session

from app.api.deps import DBSession
from app.core.exceptions import SessionNotCompleted
from app.schemas.evaluation import EvaluationResultResponse
from app.services import evaluation_service, session_service

router = APIRouter()


@router.get("/{session_id}/result", response_model=EvaluationResultResponse)
def get_result(
    session_id: int = Path(..., ge=1),
    db: Session = DBSession,
) -> EvaluationResultResponse:
    session_service.get_session(db, session_id)  # 존재 확인
    evaluation = evaluation_service.get_evaluation_or_none(db, session_id)
    if evaluation is None:
        raise SessionNotCompleted("아직 평가 결과가 생성되지 않았습니다.")

    payload = evaluation_service.to_payload(evaluation)
    return EvaluationResultResponse(
        session_id=session_id,
        evaluation_id=payload.evaluation_id,
        total_score=payload.total_score,
        grade=payload.grade,
        qa_list=payload.qa_list,
        analysis=payload.analysis,
    )
