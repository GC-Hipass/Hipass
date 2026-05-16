from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import LLMEvaluationFailed
from app.rag.providers import LLMProvider, get_llm_provider
from app.rag.retrieval import HybridRetriever

logger = logging.getLogger(__name__)


@dataclass
class QuestionAnswer:
    order: int
    question_id: int
    question: str
    answer: str


@dataclass
class QuestionEvaluation:
    order: int
    question_id: int
    question: str
    answer: str
    score: int
    feedback: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)


@dataclass
class SessionEvaluation:
    total_score: int
    grade: str
    qa_results: list[QuestionEvaluation]
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendation: str


BATCH_EVALUATION_SYSTEM_PROMPT = (
    "You are an IT interview evaluator. Return one valid JSON object only. "
    "Evaluate every answer, preserve each order and question_id, and write user-facing text in Korean."
)


def _grade_from_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _clamp_score(value: Any, fallback: int = 60) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = fallback
    return max(0, min(100, score))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _compact_contexts(chunks: list[Any], *, limit: int = 1, max_chars: int = 450) -> str:
    parts: list[str] = []
    for idx, chunk in enumerate(chunks[:limit], 1):
        content = str(getattr(chunk, "content", "")).strip()
        if content:
            parts.append(f"[{idx}] {content[:max_chars]}")
    return "\n".join(parts) if parts else "(none)"


def _build_batch_evaluation_prompt(
    *,
    company: str,
    job_role: str,
    difficulty: str,
    items: list[dict[str, Any]],
) -> str:
    blocks: list[str] = []
    for item in items:
        blocks.append(
            "\n".join(
                [
                    f"ORDER: {item['order']}",
                    f"QUESTION_ID: {item['question_id']}",
                    f"QUESTION: {item['question']}",
                    f"ANSWER: {item['answer']}",
                    f"REFERENCE_CONTEXT:\n{item['contexts']}",
                ]
            )
        )

    joined_blocks = "\n\n---\n\n".join(blocks)
    return f"""Evaluate all interview answers in one batch.

Company: {company}
Job role: {job_role}
Difficulty: {difficulty}

Questions and answers:
{joined_blocks}

Return only one valid JSON object. Do not use markdown. Do not put literal line breaks inside JSON string values.
Write all feedback and analysis in Korean.

JSON shape:
{{
  "qa_results": [
    {{
      "order": 1,
      "question_id": 1,
      "score": 0,
      "feedback": "one or two sentences",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "improvements": ["..."]
    }}
  ],
  "analysis": {{
    "summary": "overall summary",
    "strengths": ["..."],
    "weaknesses": ["..."],
    "recommendation": "next action"
  }}
}}
"""


def _fallback_question_evaluation(qa: QuestionAnswer) -> QuestionEvaluation:
    answer = (qa.answer or "").strip()
    length_score = min(35, len(answer) // 8)
    structure_bonus = 10 if any(token in answer.lower() for token in ("result", "problem", "solution")) else 0
    score = max(45, min(78, 45 + length_score + structure_bonus))
    return QuestionEvaluation(
        order=qa.order,
        question_id=qa.question_id,
        question=qa.question,
        answer=qa.answer,
        score=score,
        feedback="Automatic fallback evaluation was used because the LLM result was not available.",
        strengths=["Answer was submitted and can be reviewed."],
        weaknesses=["Detailed LLM-based feedback was not generated."],
        improvements=["Retry evaluation after the LLM server is stable."],
    )


class AnswerEvaluationPipeline:
    def __init__(
        self,
        db: Session,
        *,
        retriever: HybridRetriever | None = None,
        llm: LLMProvider | None = None,
    ):
        self._db = db
        self._retriever = retriever or HybridRetriever(db)
        self._llm = llm or get_llm_provider()

    def run(
        self,
        *,
        session_id: int,
        company: str,
        job_role: str,
        difficulty: str,
        qa_list: list[QuestionAnswer],
    ) -> SessionEvaluation:
        if not qa_list:
            raise LLMEvaluationFailed("No answers to evaluate.")

        prompt_items: list[dict[str, Any]] = []
        for qa in qa_list:
            contexts = self._retriever.retrieve_evaluation_context(
                session_id=session_id,
                question=qa.question,
                company=company,
                job_role=job_role,
                difficulty=difficulty,
            )
            prompt_items.append(
                {
                    "order": qa.order,
                    "question_id": qa.question_id,
                    "question": qa.question,
                    "answer": qa.answer,
                    "contexts": _compact_contexts(contexts),
                }
            )

        prompt = _build_batch_evaluation_prompt(
            company=company,
            job_role=job_role,
            difficulty=difficulty,
            items=prompt_items,
        )

        try:
            raw = self._llm.generate_json(
                prompt,
                system=BATCH_EVALUATION_SYSTEM_PROMPT,
                temperature=0.2,
            )
        except Exception:  # noqa: BLE001
            logger.exception("batch evaluation LLM failed; using fallback evaluation")
            raw = None

        if isinstance(raw, dict) and isinstance(raw.get("qa_results"), list):
            by_order = {
                int(item.get("order")): item
                for item in raw["qa_results"]
                if isinstance(item, dict) and item.get("order") is not None
            }
            per_question = [
                self._question_result_from_raw(qa, by_order.get(qa.order, {}))
                for qa in qa_list
            ]
            analysis = raw.get("analysis", {}) if isinstance(raw.get("analysis"), dict) else {}
        else:
            per_question = [_fallback_question_evaluation(qa) for qa in qa_list]
            analysis = {
                "summary": "Evaluation completed with fallback scoring.",
                "strengths": ["Answers were saved successfully."],
                "weaknesses": ["Detailed LLM analysis was not available."],
                "recommendation": "Retry after checking the LLM server logs.",
            }

        total = int(round(sum(r.score for r in per_question) / len(per_question)))
        return SessionEvaluation(
            total_score=total,
            grade=_grade_from_score(total),
            qa_results=per_question,
            summary=str(analysis.get("summary", "")).strip(),
            strengths=_string_list(analysis.get("strengths")),
            weaknesses=_string_list(analysis.get("weaknesses")),
            recommendation=str(analysis.get("recommendation", "")).strip(),
        )

    @staticmethod
    def _question_result_from_raw(qa: QuestionAnswer, item: dict[str, Any]) -> QuestionEvaluation:
        return QuestionEvaluation(
            order=qa.order,
            question_id=qa.question_id,
            question=qa.question,
            answer=qa.answer,
            score=_clamp_score(item.get("score"), fallback=60),
            feedback=str(item.get("feedback", "")).strip(),
            strengths=_string_list(item.get("strengths")),
            weaknesses=_string_list(item.get("weaknesses")),
            improvements=_string_list(item.get("improvements")),
        )
