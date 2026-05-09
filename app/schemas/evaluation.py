from pydantic import BaseModel


class QAItem(BaseModel):
    order: int
    question_id: int
    question: str
    answer: str
    score: int
    feedback: str


class Analysis(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendation: str


class EvaluationPayload(BaseModel):
    evaluation_id: int
    total_score: int
    grade: str
    qa_list: list[QAItem]
    analysis: Analysis


class EvaluationResultResponse(BaseModel):
    session_id: int
    evaluation_id: int
    total_score: int
    grade: str
    qa_list: list[QAItem]
    analysis: Analysis
