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
    "질문은 반드시 면접관이 지원자에게 묻는 형식이어야 하며, 지원자가 실제로 경험하지 않은 회사 경력이나 교육 이력을 가정하면 안 된다. "
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
    validation_feedback: str | None = None,
) -> str:
    feedback_block = ""
    if validation_feedback:
        feedback_block = f"""

[이전 시도에서 수정이 필요한 점]
{validation_feedback}
"""

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
- 질문은 반드시 면접관이 지원자에게 묻는 문장으로 작성하고, 1인칭 자기서술("나는", "저는", "제가")을 쓰지 말 것.
- 같은 주제를 두 번 묻지 말 것.
- 업로드 문서 기반 질문은 [개인 문서 내용]에 실제로 등장한 키워드를 활용.
- 업로드 문서에 없는 회사 경력, 사내 프로젝트, 사내 교육, 회사 제품 사용 경험을 지원자가 이미 가진 것처럼 가정하지 말 것.
- 특히 "{company}에서 ~한 경험", "{company}에서 배운 것", "{company} 사내 프로그램 참여 경험"처럼 사실을 단정하는 질문은 금지한다.
- 기업 특화 질문(question_type: "company")은 인재상, 핵심 가치, 지원 동기, 직무 적합성, 입사 후 기여 방식만 다뤄라.
- 기업 특화 질문(question_type: "company")에서는 특정 서비스명, 제품명, 사내 프로그램명, 교육 과정명을 직접 묻지 말 것.
- [기업 인재상] 문맥에 제품/서비스/기술명이 포함되어 있더라도, 그것을 지원자의 실제 경험처럼 연결해 질문하지 말 것.
{feedback_block}

다음 JSON 스키마를 정확히 따른다. 다른 텍스트는 포함하지 마라.
[
  {{"order": 1, "question_type": "personality", "question": "..."}},
  {{"order": 2, "question_type": "technical",   "question": "..."}},
  {{"order": 3, "question_type": "document",    "question": "..."}},
  {{"order": 4, "question_type": "document",    "question": "..."}},
  {{"order": 5, "question_type": "company",     "question": "..."}}
]
"""
