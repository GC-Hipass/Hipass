from __future__ import annotations

from app.rag.vectorstore import RetrievedChunk


def _join_chunks(chunks: list[RetrievedChunk], *, limit: int = 4) -> str:
    if not chunks:
        return "(없음)"
    parts = []
    for i, c in enumerate(chunks[:limit], 1):
        parts.append(f"[{i}] {c.content.strip()}")
    return "\n\n".join(parts)


QUESTION_SYSTEM_PROMPT = (
    "너는 IT 기업의 베테랑 면접관이다. "
    "주어진 조건과 문맥을 기반으로, 지원자를 효과적으로 검증할 수 있는 한국어 면접 질문을 생성한다. "
    "출력은 반드시 JSON 배열로만 한다."
)


def build_question_generation_prompt(
    *,
    company: str,
    difficulty: str,
    job_role: str,
    uploaded_chunks: list[RetrievedChunk],
    company_chunks: list[RetrievedChunk],
    technical_chunks: list[RetrievedChunk],
    personality_chunks: list[RetrievedChunk],
    question_count: int = 5,
) -> str:
    return f"""아래 조건과 문맥에 맞춰 면접 질문 {question_count}개를 생성해라.

[기업]
{company}

[난이도]
{difficulty}

[직무]
{job_role}

[개인 문서 내용]
{_join_chunks(uploaded_chunks)}

[기업 인재상]
{_join_chunks(company_chunks)}

[개발 지식 문맥]
{_join_chunks(technical_chunks)}

[인성 평가 문맥]
{_join_chunks(personality_chunks)}

질문 구성:
1. 인성 질문 1개 (question_type: "personality")
2. 일반 개발 상식 질문 1개 (question_type: "technical")
3. 업로드 문서 기반 질문 2개 (question_type: "document")
4. 기업 특화 질문 1개 (question_type: "company")

작성 규칙:
- 각 질문은 한 문장 또는 두 문장으로 자연스러운 한국어 존댓말.
- 같은 주제를 두 번 묻지 말 것.
- 업로드 문서 기반 질문은 [개인 문서 내용]에 실제로 등장한 키워드를 활용.

다음 JSON 스키마를 정확히 따른다. 다른 텍스트는 포함하지 마라.
[
  {{"order": 1, "question_type": "personality", "question": "..."}},
  {{"order": 2, "question_type": "technical",   "question": "..."}},
  {{"order": 3, "question_type": "document",    "question": "..."}},
  {{"order": 4, "question_type": "document",    "question": "..."}},
  {{"order": 5, "question_type": "company",     "question": "..."}}
]
"""
