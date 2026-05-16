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
_WHITESPACE_RE = re.compile(r"\s+")
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
_TOPIC_STOPWORDS = {
    "개발",
    "기술",
    "api",
    "서버",
    "질문",
    "문서",
    "내용",
    "경험",
    "프로젝트",
    "직무",
    "지원",
    "지원자",
    "회사",
    "기업",
    "서비스",
    "설명",
    "구체적",
    "구체적으로",
    "핵심",
    "역량",
    "문제",
    "해결",
    "과정",
    "역할",
    "적용",
    "사용",
    "업로드",
    "관련",
    "기반",
    "이해",
    "가치",
    "인재상",
    "면접",
    "한국어",
    "존댓말",
    "실제",
    "본인",
    "당사",
    "귀사",
    "배포",
}
_PERSONALITY_THEME_KEYWORDS = {
    "collaboration": ("협업", "갈등", "소통", "팀", "동료", "의견"),
    "failure": ("실수", "실패", "회고", "개선", "복기"),
    "stress": ("스트레스", "압박", "우선순위", "마감"),
    "growth": ("성장", "학습", "보완", "도전", "부족"),
}
_PERSONALITY_THEME_QUESTIONS = {
    "collaboration": "협업 과정에서 의견 차이나 갈등이 있었을 때 어떻게 조율하고 해결했는지 구체적으로 말씀해주세요.",
    "failure": "실수나 실패를 겪었을 때 어떤 방식으로 대응했고, 이후 어떻게 개선했는지 말씀해주세요.",
    "stress": "압박이나 스트레스가 큰 상황에서 우선순위를 어떻게 정하고 대응했는지 말씀해주세요.",
    "growth": "최근 스스로 부족하다고 느낀 부분을 어떤 방식으로 학습하고 보완했는지 말씀해주세요.",
}
_JOB_ROLE_DEFAULT_TECH_TOPICS = {
    "ai": ["모델 평가 지표", "데이터 전처리", "과적합 방지", "추론 최적화"],
    "app": ["REST API 설계", "트랜잭션 관리", "비동기 처리", "서비스 아키텍처"],
    "web": ["브라우저 렌더링", "상태 관리", "비동기 처리", "성능 최적화"],
    "devops": ["CI/CD", "컨테이너 오케스트레이션", "모니터링", "인프라 자동화"],
}
_DOCUMENT_QUESTION_TEMPLATES = (
    "업로드 문서에 언급된 '{topic}' 관련 경험에서 맡은 역할과 핵심 기여를 구체적으로 말씀해주세요.",
    "문서에 나온 '{topic}' 경험에서 가장 어려웠던 문제와 해결 과정을 설명해주세요.",
    "업로드 문서에서 '{topic}'를 선택하거나 도입한 이유를 설명해주세요.",
)
_TECHNICAL_QUESTION_TEMPLATES = {
    "easy": "{topic}이 무엇인지, 그리고 언제 사용하는지 설명해주세요.",
    "normal": "{topic}의 핵심 개념과 실무 적용 예시를 설명해주세요.",
    "hard": "{topic}의 핵심 개념뿐 아니라 선택 시 트레이드오프와 한계까지 설명해주세요.",
}


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


def _normalize_question_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


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


def _topic_with_particle(topic: str) -> str:
    stripped = topic.strip()
    if not stripped:
        return topic
    last = stripped[-1]
    if not ("가" <= last <= "힣"):
        return f"'{topic}'와"
    has_batchim = (ord(last) - ord("가")) % 28 != 0
    particle = "과" if has_batchim else "와"
    return f"'{topic}'{particle}"


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

    def _extract_candidate_topics(
        self,
        chunks: list[RetrievedChunk],
        *,
        limit: int = 12,
        include_korean: bool = True,
    ) -> list[str]:
        merged = _merge_chunk_text(chunks)
        seen: set[str] = set()
        candidates: list[str] = []

        for match in re.finditer(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9.+#/_-]{1,}(?![A-Za-z0-9])", merged):
            token = match.group(0).strip(".,:;()[]{}\"'")
            lower = token.lower()
            if lower in seen or lower in _TOPIC_STOPWORDS:
                continue
            seen.add(lower)
            candidates.append(token)
            if len(candidates) >= limit:
                return candidates

        if not include_korean:
            return candidates

        for match in re.finditer(r"[가-힣]{2,}", merged):
            token = match.group(0).strip()
            token = re.sub(r"(을|를|은|는|이|가|과|와|도|로|에|의)$", "", token)
            if token.endswith(("하고", "하며", "하는", "했던", "했다", "되는", "되어", "입니다")):
                continue
            compact = token.replace(" ", "")
            if compact in _TOPIC_STOPWORDS or compact.isdigit():
                continue
            if compact.lower() in seen:
                continue
            seen.add(compact.lower())
            candidates.append(token)
            if len(candidates) >= limit:
                break

        return candidates

    def _pick_topic(
        self,
        *,
        original_question: str,
        candidates: list[str],
        fallbacks: list[str],
        used_topics: set[str],
    ) -> str:
        lowered_question = original_question.lower()

        for topic in candidates:
            key = topic.lower()
            if key in used_topics:
                continue
            if key in lowered_question:
                used_topics.add(key)
                return topic

        for topic in candidates:
            key = topic.lower()
            if key in used_topics:
                continue
            used_topics.add(key)
            return topic

        for topic in fallbacks:
            key = topic.lower()
            if key in used_topics:
                continue
            used_topics.add(key)
            return topic

        fallback = fallbacks[0] if fallbacks else "핵심 경험"
        used_topics.add(fallback.lower())
        return fallback

    def _pick_personality_theme(self, original_question: str, state: _State) -> str:
        source = f"{original_question}\n{_merge_chunk_text(state.get('personality_ctx', []))}".lower()
        for theme, keywords in _PERSONALITY_THEME_KEYWORDS.items():
            if any(keyword in source for keyword in keywords):
                return theme
        return "collaboration"

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
                f"{company}의 인재상 가운데 {_topic_with_particle(company_value)} 가장 잘 맞는 본인의 경험은 무엇이며, "
                f"{job_role} 직무에서 이를 어떻게 이어갈 수 있을지 말씀해주세요."
            )
        return (
            f"{company}의 {job_role} 직무에 지원한 이유와, "
            "본인의 경험이 회사에 어떻게 기여할 수 있는지 구체적으로 말씀해주세요."
        )

    def _build_safe_personality_question(self, state: _State, original_question: str) -> str:
        theme = self._pick_personality_theme(original_question, state)
        return _PERSONALITY_THEME_QUESTIONS.get(
            theme,
            _PERSONALITY_THEME_QUESTIONS["collaboration"],
        )

    def _build_safe_technical_question(self, state: _State, original_question: str) -> str:
        candidates = self._extract_candidate_topics(state.get("technical_ctx", []))
        fallbacks = _JOB_ROLE_DEFAULT_TECH_TOPICS.get(state["job_role"].lower(), ["기술 문제 해결"])
        topic = self._pick_topic(
            original_question=original_question,
            candidates=candidates,
            fallbacks=fallbacks,
            used_topics=set(),
        )
        template = _TECHNICAL_QUESTION_TEMPLATES.get(
            state["difficulty"].lower(),
            _TECHNICAL_QUESTION_TEMPLATES["normal"],
        )
        return template.format(topic=topic)

    def _build_safe_document_question(
        self,
        state: _State,
        original_question: str,
        *,
        document_index: int,
        used_topics: set[str],
    ) -> str:
        candidates = self._extract_candidate_topics(
            state.get("uploaded_ctx", []),
            include_korean=False,
        )
        if not candidates:
            candidates = self._extract_candidate_topics(state.get("uploaded_ctx", []))
        fallbacks = [
            "가장 자신 있는 프로젝트",
            "핵심 기술 선택",
            "문제 해결 경험",
        ]
        topic = self._pick_topic(
            original_question=original_question,
            candidates=candidates,
            fallbacks=fallbacks,
            used_topics=used_topics,
        )
        template = _DOCUMENT_QUESTION_TEMPLATES[min(document_index, len(_DOCUMENT_QUESTION_TEMPLATES) - 1)]
        return template.format(topic=topic)

    def _stabilize_questions(
        self,
        state: _State,
        questions: list[GeneratedQuestion],
    ) -> list[GeneratedQuestion]:
        stabilized: list[GeneratedQuestion] = []
        document_index = 0
        used_document_topics: set[str] = set()

        for question in questions:
            normalized = _normalize_question_text(question.question)
            if question.question_type == "personality":
                normalized = self._build_safe_personality_question(state, normalized)
            elif question.question_type == "technical":
                normalized = self._build_safe_technical_question(state, normalized)
            elif question.question_type == "document":
                normalized = self._build_safe_document_question(
                    state,
                    normalized,
                    document_index=document_index,
                    used_topics=used_document_topics,
                )
                document_index += 1
            elif question.question_type == "company":
                normalized = self._build_safe_company_question(state)

            stabilized.append(
                GeneratedQuestion(
                    order=question.order,
                    question_type=question.question_type,
                    question=_normalize_question_text(normalized),
                )
            )

        return stabilized

    def _validate_question_content(self, state: _State, questions: list[GeneratedQuestion]) -> None:
        for question in questions:
            text = _normalize_question_text(question.question)
            if not text:
                raise LLMEvaluationFailed("빈 질문이 생성되었습니다.")
            if _contains_first_person(text):
                raise LLMEvaluationFailed(f"면접 질문에 1인칭 자기서술이 포함되었습니다: {text}")
            if _contains_unsupported_company_assumption(text, company=state["company"]):
                raise LLMEvaluationFailed(
                    f"지원자의 회사 경험을 근거 없이 가정한 질문이 포함되었습니다: {text}"
                )
            if "\n" in question.question or "\r" in question.question:
                raise LLMEvaluationFailed(f"질문에 줄바꿈이 포함되었습니다: {text}")

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
                    temperature=0.2,
                )
                questions = self._parse_questions(raw)
                self._validate_question_structure(
                    questions,
                    question_count=state.get("question_count", 5),
                )
                questions = self._stabilize_questions(state, questions)
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
