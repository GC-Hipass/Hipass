from __future__ import annotations

from importlib import import_module

__all__ = [
    "AnswerEvaluationPipeline",
    "GeneratedQuestion",
    "QuestionAnswer",
    "QuestionEvaluation",
    "QuestionGenerationPipeline",
    "SessionEvaluation",
]


def __getattr__(name: str):
    if name in {"GeneratedQuestion", "QuestionGenerationPipeline"}:
        module = import_module("app.rag.pipelines.question_generation")
        return getattr(module, name)
    if name in {
        "AnswerEvaluationPipeline",
        "QuestionAnswer",
        "QuestionEvaluation",
        "SessionEvaluation",
    }:
        module = import_module("app.rag.pipelines.answer_evaluation")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
