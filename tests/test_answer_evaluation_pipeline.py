from __future__ import annotations

import unittest

from app.rag.pipelines.answer_evaluation import AnswerEvaluationPipeline, QuestionAnswer
from app.rag.providers.llm import LLMProvider


class _FakeRetriever:
    def retrieve_evaluation_context(
        self,
        *,
        session_id: int,
        question: str,
        company: str,
        job_role: str,
        difficulty: str,
    ) -> list[object]:
        return []


class _UnusedLLM(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str:
        self.calls += 1
        raise AssertionError("LLM should not be called for blank answers")


class AnswerEvaluationPipelineTests(unittest.TestCase):
    def test_blank_answers_are_scored_without_llm(self) -> None:
        llm = _UnusedLLM()
        pipeline = AnswerEvaluationPipeline(None, retriever=_FakeRetriever(), llm=llm)

        result = pipeline.run(
            session_id=1,
            company="naver",
            job_role="web",
            difficulty="normal",
            qa_list=[
                QuestionAnswer(order=1, question_id=1, question="질문1", answer=""),
                QuestionAnswer(order=2, question_id=2, question="질문2", answer="   "),
            ],
        )

        self.assertEqual(llm.calls, 0)
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.grade, "F")
        self.assertTrue(all(item.score == 0 for item in result.qa_results))
        self.assertTrue(all("답변이 제출되지" in item.feedback for item in result.qa_results))


if __name__ == "__main__":
    unittest.main()
