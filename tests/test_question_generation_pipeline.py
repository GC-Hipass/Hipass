from __future__ import annotations

import json
import unittest

from app.rag.pipelines.question_generation import QuestionGenerationPipeline
from app.rag.providers.llm import LLMProvider
from app.rag.vectorstore import RetrievedChunk


class _SequenceLLM(LLMProvider):
    def __init__(self, responses: list[list[dict[str, object]]]):
        self._responses = responses
        self.calls = 0

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str:
        if self.calls >= len(self._responses):
            raise AssertionError("unexpected extra LLM call")
        response = self._responses[self.calls]
        self.calls += 1
        return json.dumps(response, ensure_ascii=False)


class _FakeRetriever:
    def retrieve_knowledge(
        self,
        *,
        source_type: str,
        queries: list[str],
        company: str | None = None,
        job_role: str | None = None,
        difficulty: str | None = None,
    ) -> list[RetrievedChunk]:
        if source_type == "personality_question":
            return [
                RetrievedChunk(
                    content="협업 과정에서 갈등을 조율한 경험과 가치관을 확인한다.",
                    score=1.0,
                    source="knowledge",
                    metadata={},
                )
            ]
        if source_type == "technical_knowledge":
            return [
                RetrievedChunk(
                    content="FastAPI, REST API, Docker, 비동기 처리 이해를 확인한다.",
                    score=1.0,
                    source="knowledge",
                    metadata={},
                )
            ]
        if source_type == "company_profile":
            return [
                RetrievedChunk(
                    content=(
                        "NAVER는 자율과 책임, 수평적 협업을 중시한다. "
                        "클로바 같은 제품명이 문맥에 있어도 company 질문은 가치 적합성만 물어야 한다."
                    ),
                    score=1.0,
                    source="knowledge",
                    metadata={},
                )
            ]
        return []

    def retrieve_uploaded(self, *, session_id: int, queries: list[str]) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                content="FastAPI 기반 API 서버를 개발하고 Docker로 배포한 프로젝트 경험이 있습니다.",
                score=1.0,
                source="uploaded",
                metadata={},
            )
        ]


class QuestionGenerationPipelineTests(unittest.TestCase):
    def test_company_question_is_replaced_with_safe_template(self) -> None:
        llm = _SequenceLLM(
            [
                [
                    {"order": 1, "question_type": "personality", "question": "협업 중 갈등을 해결한 경험을 말씀해주세요."},
                    {"order": 2, "question_type": "technical", "question": "FastAPI에서 비동기 처리를 어떻게 이해하고 계신지 설명해주세요."},
                    {"order": 3, "question_type": "document", "question": "문서에 나온 FastAPI 프로젝트에서 맡은 역할을 설명해주세요."},
                    {"order": 4, "question_type": "document", "question": "Docker 배포 과정에서 겪은 문제와 해결 방법을 말씀해주세요."},
                    {"order": 5, "question_type": "company", "question": "나는 Naver에서 학습한 AI 기술과 관련된 문제를 해결하는 데 도움이 될 수 있습니다. 예를 들어, CLOVA, Naver Cloud Academy 등에 대해 설명해주세요."},
                ]
            ]
        )
        pipeline = QuestionGenerationPipeline(None, retriever=_FakeRetriever(), llm=llm)

        questions = pipeline.run(
            session_id=1,
            company="naver",
            difficulty="normal",
            job_role="ai",
        )

        company_question = next(q.question for q in questions if q.question_type == "company")
        self.assertIn("NAVER", company_question)
        self.assertIn("자율과 책임", company_question)
        self.assertNotIn("CLOVA", company_question)
        self.assertNotIn("Naver Cloud Academy", company_question)
        self.assertNotIn("나는", company_question)

    def test_invalid_first_person_question_triggers_retry(self) -> None:
        llm = _SequenceLLM(
            [
                [
                    {"order": 1, "question_type": "personality", "question": "협업 중 갈등을 해결한 경험을 말씀해주세요."},
                    {"order": 2, "question_type": "technical", "question": "REST API 설계 원칙을 설명해주세요."},
                    {"order": 3, "question_type": "document", "question": "나는 FastAPI 프로젝트에서 맡은 역할을 설명해주세요."},
                    {"order": 4, "question_type": "document", "question": "Docker 배포 과정에서 겪은 문제와 해결 방법을 말씀해주세요."},
                    {"order": 5, "question_type": "company", "question": "NAVER의 인재상 중 본인과 가장 잘 맞는 요소를 말씀해주세요."},
                ],
                [
                    {"order": 1, "question_type": "personality", "question": "협업 중 갈등을 해결한 경험을 말씀해주세요."},
                    {"order": 2, "question_type": "technical", "question": "REST API 설계 원칙과 실제 적용 경험을 설명해주세요."},
                    {"order": 3, "question_type": "document", "question": "문서에 나온 FastAPI 프로젝트에서 맡은 역할을 설명해주세요."},
                    {"order": 4, "question_type": "document", "question": "Docker 배포 과정에서 겪은 문제와 해결 방법을 말씀해주세요."},
                    {"order": 5, "question_type": "company", "question": "NAVER의 인재상 중 본인과 가장 잘 맞는 요소를 말씀해주세요."},
                ],
            ]
        )
        pipeline = QuestionGenerationPipeline(None, retriever=_FakeRetriever(), llm=llm)

        questions = pipeline.run(
            session_id=1,
            company="naver",
            difficulty="normal",
            job_role="web",
        )

        self.assertEqual(llm.calls, 2)
        self.assertTrue(all("나는" not in question.question for question in questions))


if __name__ == "__main__":
    unittest.main()
