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
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.exceptions import LLMEvaluationFailed
from app.rag.prompts import build_question_generation_prompt
from app.rag.prompts.question_prompts import QUESTION_SYSTEM_PROMPT
from app.rag.providers.llm import LLMProvider, get_llm_provider
from app.rag.vectorstore import RetrievedChunk

if TYPE_CHECKING:
    from app.rag.retrieval.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

_FIRST_PERSON_PRONOUNS = ("나는", "저는", "제가")
_COMPANY_DISPLAY_NAMES = {
    "naver": "NAVER",
    "sk": "SK",
    "samsung": "삼성",
}
_JOB_ROLE_DISPLAY_NAMES = {
    "ai": "AI",
    "app": "백엔드/앱",
    "web": "프론트엔드/웹",
    "devops": "DevOps/인프라",
}
_COMPANY_VALUE_KEYWORDS = {
    "naver": ["자율과 책임", "자기주도", "협업", "도전", "기술로 임팩트"],
    "sk": ["패기", "자발성", "SUPEX", "협업", "전문성"],
    "samsung": ["인재제일", "최고지향", "변화선도", "정도경영", "상생추구"],
}
_COMPANY_ASSUMPTION_VERBS = (
    "학습",
    "배우",
    "근무",
    "재직",
    "수행",
    "참여",
    "경험",
    "개발",
    "사용",
    "적용",
    "운영",
)
_MAX_GENERATION_ATTEMPTS = 3


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


def _display_company(company: str) -> str:
    return _COMPANY_DISPLAY_NAMES.get(company.lower(), company.upper())


def _display_job_role(job_role: str) -> str:
    return _JOB_ROLE_DISPLAY_NAMES.get(job_role.lower(), job_role)


def _merge_chunk_text(chunks: list[RetrievedChunk]) -> str:
    return "\n".join(chunk.content for chunk in chunks)


def _contains_first_person(question: str) -> bool:
    return any(pronoun in question for pronoun in _FIRST_PERSON_PRONOUNS)


def _contains_unsupported_company_assumption(question: str, *, company: str) -> bool:
    company_markers = {
        company.lower(),
        _display_company(company).lower(),
        "당사",
        "귀사",
    }
    lowered = question.lower()
    if not any(marker in lowered for marker in company_markers):
        return False

    compact = re.sub(r"\s+", " ", question)
    return bool(
        re.search(
            r"에서[^.?!\n]{0,40}(?:"
            + "|".join(_COMPANY_ASSUMPTION_VERBS)
            + r")[가-힣]*",
            compact,
        )
    )


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
        if retriever is None:
            from app.rag.retrieval.hybrid_retriever import HybridRetriever

            retriever = HybridRetriever(db)
        self._retriever = retriever
        self._llm = llm or get_llm_provider()
        self._graph = self._build_graph()

    def _validate_question_structure(
        self,
        questions: list[GeneratedQuestion],
        *,
        question_count: int,
    ) -> None:
        if len(questions) != question_count:
            raise LLMEvaluationFailed(
                f"질문 개수가 {question_count}개가 아닙니다: {len(questions)}"
            )

        counts: dict[str, int] = {}
        for q in questions:
            counts[q.question_type] = counts.get(q.question_type, 0) + 1
        for qtype, expected in _REQUIRED_TYPES.items():
            if counts.get(qtype, 0) != expected:
                raise LLMEvaluationFailed(
                    f"질문 유형 분포 오류: {counts} (기대 {_REQUIRED_TYPES})"
                )

    def _pick_company_value(self, state: _State) -> str | None:
        company = state["company"].lower()
        merged = _merge_chunk_text(state.get("company_ctx", []))
        for keyword in _COMPANY_VALUE_KEYWORDS.get(company, []):
            if keyword.lower() in merged.lower():
                return keyword
        return None

    def _build_safe_company_question(self, state: _State) -> str:
        company = _display_company(state["company"])
        job_role = _display_job_role(state["job_role"])
        company_value = self._pick_company_value(state)
        if company_value:
            return (
                f"{company}의 인재상 가운데 '{company_value}'와 가장 잘 맞는 본인의 경험은 무엇이며, "
                f"{job_role} 직무에서 이를 어떻게 이어갈 수 있을지 말씀해주세요."
            )
        return (
            f"{company}의 {job_role} 직무에 지원한 이유와, "
            "본인의 경험이 회사에 어떻게 기여할 수 있는지 구체적으로 말씀해주세요."
        )

    def _replace_company_question(
        self,
        questions: list[GeneratedQuestion],
        *,
        state: _State,
    ) -> list[GeneratedQuestion]:
        safe_question = self._build_safe_company_question(state)
        replaced: list[GeneratedQuestion] = []
        for question in questions:
            if question.question_type == "company":
                replaced.append(
                    GeneratedQuestion(
                        order=question.order,
                        question_type=question.question_type,
                        question=safe_question,
                    )
                )
                continue
            replaced.append(question)
        return replaced

    def _validate_question_content(self, state: _State, questions: list[GeneratedQuestion]) -> None:
        for question in questions:
            text = question.question.strip()
            if not text:
                raise LLMEvaluationFailed("빈 질문이 생성되었습니다.")
            if _contains_first_person(text):
                raise LLMEvaluationFailed(f"면접 질문에 1인칭 자기서술이 포함되었습니다: {text}")
            if _contains_unsupported_company_assumption(text, company=state["company"]):
                raise LLMEvaluationFailed(
                    f"지원자의 회사 경험을 근거 없이 가정한 질문이 포함되었습니다: {text}"
                )

    def _parse_questions(self, raw: Any) -> list[GeneratedQuestion]:
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
        return questions

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
        validation_feedback: str | None = None
        last_error: LLMEvaluationFailed | None = None

        for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
            prompt = build_question_generation_prompt(
                company=state["company"],
                difficulty=state["difficulty"],
                job_role=state["job_role"],
                uploaded_chunks=state.get("uploaded_ctx", []),
                company_chunks=state.get("company_ctx", []),
                technical_chunks=state.get("technical_ctx", []),
                personality_chunks=state.get("personality_ctx", []),
                question_count=state.get("question_count", 5),
                validation_feedback=validation_feedback,
            )
            try:
                raw = self._llm.generate_json(
                    prompt,
                    system=QUESTION_SYSTEM_PROMPT,
                    temperature=0.6,
                )
                questions = self._parse_questions(raw)
                self._validate_question_structure(
                    questions,
                    question_count=state.get("question_count", 5),
                )
                questions = self._replace_company_question(questions, state=state)
                self._validate_question_content(state, questions)
                state["questions"] = questions
                return state
            except LLMEvaluationFailed as e:
                last_error = e
                validation_feedback = (
                    "이전 결과에 다음 문제가 있었습니다. 반드시 수정해서 처음부터 다시 생성하세요.\n"
                    f"- {e.message}"
                )
                logger.warning(
                    "question generation validation failed (attempt=%s/%s): %s",
                    attempt,
                    _MAX_GENERATION_ATTEMPTS,
                    e.message,
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("question generation LLM failed")
                raise LLMEvaluationFailed(f"질문 생성 실패: {e}") from e

        if last_error is not None:
            raise last_error
        raise LLMEvaluationFailed("질문 생성에 실패했습니다.")

    def _node_validate(self, state: _State) -> _State:
        questions = state.get("questions", [])
        self._validate_question_structure(
            questions,
            question_count=state.get("question_count", 5),
        )
        self._validate_question_content(state, questions)
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
