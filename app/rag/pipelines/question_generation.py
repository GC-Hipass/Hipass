"""질문 생성 RAG 파이프라인.

LangGraph로 retrieval orchestration을 구성한다. 각 단계는 순수 함수로,
state(dict)를 받아 state를 갱신해 반환한다.

START
  ↓ Load Session Options
  ↓ Retrieve Personality Context
  ↓ Retrieve Technical Context
  ↓ Retrieve Uploaded Document Context
  ↓ Retrieve Company Context
  ↓ Generate 5 Questions (LLM Provider)
  ↓ Validate Question Types
END
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.exceptions import LLMEvaluationFailed
from app.rag.prompts import build_question_generation_prompt
from app.rag.prompts.question_prompts import QUESTION_SYSTEM_PROMPT
from app.rag.providers import LLMProvider, get_llm_provider
from app.rag.retrieval import HybridRetriever
from app.rag.vectorstore import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class GeneratedQuestion:
    order: int
    question_type: str  # personality | technical | document | company
    question: str


class _State(TypedDict, total=False):
    # 입력
    session_id: int
    company: str
    difficulty: str
    job_role: str
    question_count: int
    # 중간 결과
    personality_ctx: list[RetrievedChunk]
    technical_ctx: list[RetrievedChunk]
    uploaded_ctx: list[RetrievedChunk]
    company_ctx: list[RetrievedChunk]
    # 출력
    questions: list[GeneratedQuestion]


_REQUIRED_TYPES = {"personality": 1, "technical": 1, "document": 2, "company": 1}


class QuestionGenerationPipeline:
    """공개 인터페이스: run(...) -> list[GeneratedQuestion]."""

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
        self._graph = self._build_graph()

    # ---------------- Graph Nodes ----------------

    def _node_personality(self, state: _State) -> _State:
        state["personality_ctx"] = self._retriever.retrieve_knowledge(
            source_type="personality_question",
            queries=["인성 면접 질문", "지원자 가치관 검증"],
        )
        return state

    def _node_technical(self, state: _State) -> _State:
        state["technical_ctx"] = self._retriever.retrieve_knowledge(
            source_type="technical_knowledge",
            queries=[
                f"{state['job_role']} 핵심 개발 지식",
                f"{state['difficulty']} 난이도 {state['job_role']} 기술 면접 주제",
            ],
            job_role=state["job_role"],
            difficulty=state["difficulty"],
        )
        return state

    def _node_uploaded(self, state: _State) -> _State:
        state["uploaded_ctx"] = self._retriever.retrieve_uploaded(
            session_id=state["session_id"],
            queries=[
                f"{state['job_role']} 직무 면접에서 검증할 핵심 역량",
                f"{state['company']} {state['job_role']} 관련 경험과 프로젝트",
            ],
        )
        return state

    def _node_company(self, state: _State) -> _State:
        state["company_ctx"] = self._retriever.retrieve_knowledge(
            source_type="company_profile",
            queries=[f"{state['company']} 인재상", f"{state['company']} 핵심 가치"],
            company=state["company"],
        )
        return state

    def _node_generate(self, state: _State) -> _State:
        prompt = build_question_generation_prompt(
            company=state["company"],
            difficulty=state["difficulty"],
            job_role=state["job_role"],
            uploaded_chunks=state.get("uploaded_ctx", []),
            company_chunks=state.get("company_ctx", []),
            technical_chunks=state.get("technical_ctx", []),
            personality_chunks=state.get("personality_ctx", []),
            question_count=state.get("question_count", 5),
        )
        try:
            raw = self._llm.generate_json(prompt, system=QUESTION_SYSTEM_PROMPT, temperature=0.6)
        except Exception as e:  # noqa: BLE001
            logger.exception("question generation LLM failed")
            raise LLMEvaluationFailed(f"질문 생성 실패: {e}") from e

        if not isinstance(raw, list):
            raise LLMEvaluationFailed("질문 생성 응답이 배열이 아닙니다.")

        questions: list[GeneratedQuestion] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                questions.append(
                    GeneratedQuestion(
                        order=int(item["order"]),
                        question_type=str(item["question_type"]).lower(),
                        question=str(item["question"]).strip(),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                raise LLMEvaluationFailed(f"질문 형식 오류: {item} ({e})") from e

        questions.sort(key=lambda q: q.order)
        state["questions"] = questions
        return state

    def _node_validate(self, state: _State) -> _State:
        questions = state.get("questions", [])
        if len(questions) != state.get("question_count", 5):
            raise LLMEvaluationFailed(
                f"질문 개수가 {state.get('question_count', 5)}개가 아닙니다: {len(questions)}"
            )

        counts: dict[str, int] = {}
        for q in questions:
            counts[q.question_type] = counts.get(q.question_type, 0) + 1
        for qtype, expected in _REQUIRED_TYPES.items():
            if counts.get(qtype, 0) != expected:
                raise LLMEvaluationFailed(
                    f"질문 유형 분포 오류: {counts} (기대 {_REQUIRED_TYPES})"
                )
        return state

    def _build_graph(self) -> Any:
        graph: StateGraph = StateGraph(_State)
        graph.add_node("personality", self._node_personality)
        graph.add_node("technical", self._node_technical)
        graph.add_node("uploaded", self._node_uploaded)
        graph.add_node("company_retrieve", self._node_company)
        graph.add_node("generate", self._node_generate)
        graph.add_node("validate", self._node_validate)

        graph.add_edge(START, "personality")
        graph.add_edge("personality", "technical")
        graph.add_edge("technical", "uploaded")
        graph.add_edge("uploaded", "company_retrieve")
        graph.add_edge("company_retrieve", "generate")
        graph.add_edge("generate", "validate")
        graph.add_edge("validate", END)
        return graph.compile()

    # ---------------- Public API ----------------

    def run(
        self,
        *,
        session_id: int,
        company: str,
        difficulty: str,
        job_role: str,
        question_count: int = 5,
    ) -> list[GeneratedQuestion]:
        initial: _State = {
            "session_id": session_id,
            "company": company,
            "difficulty": difficulty,
            "job_role": job_role,
            "question_count": question_count,
        }
        result = self._graph.invoke(initial)
        return result["questions"]
