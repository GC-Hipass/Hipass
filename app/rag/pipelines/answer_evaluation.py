"""답변 평가 RAG 파이프라인.

각 질문에 대해:
  1) 검색 문맥 조회
  2) 모범답안 생성 (LLM Provider)
  3) 사용자 답변 임베딩 + 모범답안 임베딩 -> semantic similarity
  4) 핵심 키워드 포함 여부 분석
  5) LLM Provider로 정성 평가 + scores JSON 반환
  6) 최종 점수 합산 (가중 평균)

전체 5문항이 끝나면 final analysis (요약/강점/약점/추천)를 한 번 더 호출.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import LLMEvaluationFailed
from app.rag.prompts import build_evaluation_prompt, build_ideal_answer_prompt
from app.rag.prompts.evaluation_prompts import (
    EVALUATION_SYSTEM_PROMPT,
    FINAL_ANALYSIS_SYSTEM_PROMPT,
    IDEAL_ANSWER_SYSTEM_PROMPT,
    build_final_analysis_prompt,
)
from app.rag.providers import EmbeddingProvider, LLMProvider, get_embedding_provider, get_llm_provider
from app.rag.retrieval import HybridRetriever

logger = logging.getLogger(__name__)


_SCORE_WEIGHTS = {
    "semantic": 0.30,
    "keyword": 0.25,
    "groundedness": 0.20,
    "logic": 0.15,
    "specificity": 0.10,
}


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


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _extract_keywords(text: str, *, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", text)
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def _keyword_coverage(reference: str, candidate: str) -> float:
    keys = _extract_keywords(reference)
    if not keys:
        return 0.0
    cand_low = candidate.lower()
    hit = sum(1 for k in keys if k.lower() in cand_low)
    return hit / len(keys)


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


class AnswerEvaluationPipeline:
    """공개 인터페이스: run(session_meta, qa_list) -> SessionEvaluation."""

    def __init__(
        self,
        db: Session,
        *,
        retriever: HybridRetriever | None = None,
        llm: LLMProvider | None = None,
        embedder: EmbeddingProvider | None = None,
    ):
        self._db = db
        self._retriever = retriever or HybridRetriever(db)
        self._llm = llm or get_llm_provider()
        self._embedder = embedder or get_embedding_provider()

    def _evaluate_one(
        self,
        *,
        session_id: int,
        company: str,
        job_role: str,
        difficulty: str,
        qa: QuestionAnswer,
    ) -> QuestionEvaluation:
        contexts = self._retriever.retrieve_evaluation_context(
            session_id=session_id,
            question=qa.question,
            company=company,
            job_role=job_role,
            difficulty=difficulty,
        )

        # 1) 모범답안 생성
        ideal_answer = self._llm.generate(
            build_ideal_answer_prompt(question=qa.question, contexts=contexts),
            system=IDEAL_ANSWER_SYSTEM_PROMPT,
            temperature=0.4,
        ).strip()

        # 2) semantic + keyword 점수 (LLM 호출 실패 시 폴백 용)
        try:
            ideal_emb = self._embedder.embed(ideal_answer or qa.question)
            user_emb = self._embedder.embed(qa.answer or " ")
            semantic_local = _cosine(ideal_emb, user_emb) * 100
        except Exception:  # noqa: BLE001
            semantic_local = 0.0
        keyword_local = _keyword_coverage(ideal_answer, qa.answer) * 100

        # 3) LLM 정성 평가
        prompt = build_evaluation_prompt(
            company=company,
            job_role=job_role,
            difficulty=difficulty,
            question=qa.question,
            user_answer=qa.answer,
            ideal_answer=ideal_answer,
            contexts=contexts,
        )
        try:
            raw = self._llm.generate_json(prompt, system=EVALUATION_SYSTEM_PROMPT, temperature=0.3)
        except Exception as e:  # noqa: BLE001
            logger.exception("evaluation LLM failed")
            raise LLMEvaluationFailed(f"답변 평가 실패: {e}") from e

        if not isinstance(raw, dict):
            raise LLMEvaluationFailed("답변 평가 응답이 객체가 아닙니다.")

        scores = raw.get("scores", {}) or {}

        def _pick(key: str, fallback: float) -> float:
            v = scores.get(key)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = fallback
            return max(0.0, min(100.0, v))

        s_semantic = _pick("semantic", semantic_local)
        s_keyword = _pick("keyword", keyword_local)
        s_grounded = _pick("groundedness", 60.0)
        s_logic = _pick("logic", 60.0)
        s_specific = _pick("specificity", 50.0)

        weighted = (
            s_semantic * _SCORE_WEIGHTS["semantic"]
            + s_keyword * _SCORE_WEIGHTS["keyword"]
            + s_grounded * _SCORE_WEIGHTS["groundedness"]
            + s_logic * _SCORE_WEIGHTS["logic"]
            + s_specific * _SCORE_WEIGHTS["specificity"]
        )

        return QuestionEvaluation(
            order=qa.order,
            question_id=qa.question_id,
            question=qa.question,
            answer=qa.answer,
            score=int(round(weighted)),
            feedback=str(raw.get("feedback", "")).strip(),
            strengths=list(raw.get("strengths", []) or []),
            weaknesses=list(raw.get("weaknesses", []) or []),
            improvements=list(raw.get("improvements", []) or []),
        )

    def _final_analysis(self, qa_results: list[QuestionEvaluation]) -> dict[str, Any]:
        prompt = build_final_analysis_prompt(
            [
                {
                    "order": r.order,
                    "question": r.question,
                    "answer": r.answer,
                    "score": r.score,
                    "feedback": r.feedback,
                }
                for r in qa_results
            ]
        )
        try:
            raw = self._llm.generate_json(
                prompt, system=FINAL_ANALYSIS_SYSTEM_PROMPT, temperature=0.4
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("final analysis failed")
            raise LLMEvaluationFailed(f"최종 분석 실패: {e}") from e

        if not isinstance(raw, dict):
            raise LLMEvaluationFailed("최종 분석 응답이 객체가 아닙니다.")
        return raw

    def run(
        self,
        *,
        session_id: int,
        company: str,
        job_role: str,
        difficulty: str,
        qa_list: list[QuestionAnswer],
    ) -> SessionEvaluation:
        per_question: list[QuestionEvaluation] = []
        for qa in qa_list:
            per_question.append(
                self._evaluate_one(
                    session_id=session_id,
                    company=company,
                    job_role=job_role,
                    difficulty=difficulty,
                    qa=qa,
                )
            )

        if not per_question:
            raise LLMEvaluationFailed("평가할 답변이 없습니다.")

        total = int(round(sum(r.score for r in per_question) / len(per_question)))
        analysis = self._final_analysis(per_question)

        return SessionEvaluation(
            total_score=total,
            grade=_grade_from_score(total),
            qa_results=per_question,
            summary=str(analysis.get("summary", "")).strip(),
            strengths=list(analysis.get("strengths", []) or []),
            weaknesses=list(analysis.get("weaknesses", []) or []),
            recommendation=str(analysis.get("recommendation", "")).strip(),
        )
