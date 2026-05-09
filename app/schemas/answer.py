from pydantic import BaseModel

from app.schemas.evaluation import EvaluationPayload


class AnswerResponse(BaseModel):
    answer_id: int
    session_id: int
    question_id: int
    order: int
    answer_text: str
    stt_provider: str
    answered_count: int
    question_count: int
    is_session_completed: bool
    is_evaluated: bool
    evaluation: EvaluationPayload | None = None
