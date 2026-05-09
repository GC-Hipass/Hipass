from __future__ import annotations

from app.rag.vectorstore import RetrievedChunk


def _join_chunks(chunks: list[RetrievedChunk], *, limit: int = 4) -> str:
    if not chunks:
        return "(없음)"
    return "\n\n".join(f"[{i}] {c.content.strip()}" for i, c in enumerate(chunks[:limit], 1))


IDEAL_ANSWER_SYSTEM_PROMPT = (
    "너는 IT 면접 답변 전문가다. 주어진 질문과 문맥을 활용해 모범답안을 한국어로 작성한다. "
    "150자 이내로 간결하게, 핵심 키워드를 반드시 포함하도록 한다."
)


def build_ideal_answer_prompt(*, question: str, contexts: list[RetrievedChunk]) -> str:
    return f"""[질문]
{question}

[참고 문맥]
{_join_chunks(contexts)}

위 문맥을 근거로 모범답안을 작성해라. 핵심 키워드 4~6개를 포함해라.
출력은 모범답안 텍스트만 작성한다.
"""


EVALUATION_SYSTEM_PROMPT = (
    "너는 IT 기업의 면접 답변 평가자다. "
    "주어진 평가 기준과 문맥을 바탕으로 사용자 답변을 정량/정성 평가한다. "
    "출력은 반드시 단일 JSON 객체로만 한다."
)


def build_evaluation_prompt(
    *,
    company: str,
    job_role: str,
    difficulty: str,
    question: str,
    user_answer: str,
    ideal_answer: str,
    contexts: list[RetrievedChunk],
) -> str:
    return f"""아래 정보를 기반으로 답변을 평가해라.

[기업]
{company}

[직무]
{job_role}

[난이도]
{difficulty}

[질문]
{question}

[검색 문맥]
{_join_chunks(contexts)}

[모범답안]
{ideal_answer}

[사용자 답변]
{user_answer}

평가 기준 (각 0~100):
1. 의미 유사도 (semantic): 모범답안과의 의미 일치
2. 핵심 키워드 포함 (keyword): 핵심 개념 포함 여부
3. 문서 근거 일치 (groundedness): 검색 문맥과 충돌 없음
4. 논리성 (logic): 논리적 흐름과 구조
5. 구체성 (specificity): 구체적 사례, 수치, 경험 포함

다음 JSON 객체로만 응답하라. 다른 텍스트는 절대 포함하지 마라.
{{
  "scores": {{
    "semantic": 0,
    "keyword": 0,
    "groundedness": 0,
    "logic": 0,
    "specificity": 0
  }},
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvements": ["..."],
  "feedback": "총평 한 문장"
}}
"""


FINAL_ANALYSIS_SYSTEM_PROMPT = (
    "너는 면접 최종 코칭 리포트 작성자다. 5개 문항의 개별 평가를 통합해 한국어 리포트를 작성한다."
)


def build_final_analysis_prompt(qa_results: list[dict]) -> str:
    parts = []
    for r in qa_results:
        parts.append(
            f"- [{r['order']}] (score={r['score']}) Q: {r['question']}\n  A: {r['answer']}\n  feedback: {r['feedback']}"
        )
    items = "\n".join(parts)
    return f"""다음은 5개 문항에 대한 개별 평가 결과다.

{items}

위 결과를 바탕으로 다음 JSON 형식으로만 응답해라.
{{
  "summary": "전체 답변에 대한 요약 한두 문장",
  "strengths": ["잘한 점 핵심 2~4개"],
  "weaknesses": ["부족한 점 핵심 2~4개"],
  "recommendation": "지원자가 다음 면접에서 개선할 가장 중요한 행동 한두 문장"
}}
"""
