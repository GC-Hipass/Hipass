from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import SessionNotCompleted
from app.db.models import (
    InterviewAnswer,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSession,
)
from app.rag.pipelines import (
    AnswerEvaluationPipeline,
    QuestionAnswer,
    SessionEvaluation,
)
from app.schemas.evaluation import Analysis, EvaluationPayload, QAItem
from app.services import session_service

logger = logging.getLogger(__name__)


def _to_qa_list(
    db: Session, session_id: int
) -> list[QuestionAnswer]:
    stmt = (
        select(InterviewAnswer, InterviewQuestion)
        .join(InterviewQuestion, InterviewAnswer.question_id == InterviewQuestion.id)
        .where(InterviewAnswer.session_id == session_id)
        .order_by(InterviewAnswer.order.asc())
    )
    rows = db.execute(stmt).all()
    return [
        QuestionAnswer(
            order=ans.order,
            question_id=ans.question_id,
            question=q.question,
            answer=ans.answer_text,
        )
        for ans, q in rows
    ]


def _persist_evaluation(
    db: Session, *, session: InterviewSession, result: SessionEvaluation
) -> InterviewEvaluation:
    qa_result_json = [
        {
            "order": r.order,
            "question_id": r.question_id,
            "question": r.question,
            "answer": r.answer,
            "score": r.score,
            "feedback": r.feedback,
            "strengths": r.strengths,
            "weaknesses": r.weaknesses,
            "improvements": r.improvements,
        }
        for r in result.qa_results
    ]
    analysis_json = {
        "summary": result.summary,
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "recommendation": result.recommendation,
    }
    evaluation = InterviewEvaluation(
        session_id=session.id,
        total_score=result.total_score,
        grade=result.grade,
        qa_result_json=qa_result_json,
        analysis_json=analysis_json,
    )
    db.add(evaluation)
    db.flush()
    return evaluation


def evaluate_session(db: Session, *, session: InterviewSession) -> InterviewEvaluation:
    """5개 답변 모두 완료된 세션에 대해 RAG 평가를 실행하고 결과를 저장한다."""
    qa_list = _to_qa_list(db, session.id)
    if len(qa_list) != session.question_count:
        raise SessionNotCompleted(
            f"답변 {len(qa_list)}/{session.question_count} — 평가 불가"
        )

    pipeline = AnswerEvaluationPipeline(db)
    result = pipeline.run(
        session_id=session.id,
        company=session.company,
        job_role=session.job_role,
        difficulty=session.difficulty,
        qa_list=qa_list,
    )

    session_service.update_status(db, session, "completed")
    evaluation = _persist_evaluation(db, session=session, result=result)
    session_service.update_status(db, session, "evaluated")
    return evaluation


def get_evaluation_or_none(db: Session, session_id: int) -> InterviewEvaluation | None:
    stmt = select(InterviewEvaluation).where(InterviewEvaluation.session_id == session_id)
    return db.execute(stmt).scalar_one_or_none()


def to_payload(evaluation: InterviewEvaluation) -> EvaluationPayload:
    qa_items = [
        QAItem(
            order=int(item["order"]),
            question_id=int(item["question_id"]),
            question=item["question"],
            answer=item["answer"],
            score=int(item["score"]),
            feedback=item.get("feedback", ""),
        )
        for item in (evaluation.qa_result_json or [])
    ]
    a = evaluation.analysis_json or {}
    analysis = Analysis(
        summary=a.get("summary", ""),
        strengths=list(a.get("strengths", [])),
        weaknesses=list(a.get("weaknesses", [])),
        recommendation=a.get("recommendation", ""),
    )
    return EvaluationPayload(
        evaluation_id=evaluation.id,
        total_score=evaluation.total_score,
        grade=evaluation.grade,
        qa_list=qa_items,
        analysis=analysis,
    )
