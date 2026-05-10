from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import LLMEvaluationFailed

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str: ...

    def generate_json(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.3
    ) -> Any:
        text = self.generate(prompt, system=system, temperature=temperature)
        return parse_json_loose(text)


def parse_json_loose(text: str) -> Any:
    """LLM 출력에서 JSON 블록만 안전하게 뽑아낸다."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 첫 { 또는 [부터 끝까지 시도
        first_obj = text.find("{")
        first_arr = text.find("[")
        candidates = [i for i in (first_obj, first_arr) if i != -1]
        if not candidates:
            raise
        start = min(candidates)
        return json.loads(text[start:])


class ClovaXProvider(LLMProvider):
    """Naver Clova X (HyperCLOVA X) chat completion 호출."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=60.0)

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str:
        if not self._settings.clova_x_api_key:
            raise LLMEvaluationFailed("Clova X API 키가 설정되지 않았습니다.")

        url = (
            f"{self._settings.clova_x_api_url.rstrip('/')}"
            f"/v3/chat-completions/{self._settings.clova_x_model}"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.clova_x_api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid4()),
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append(
                {"role": "system", "content": [{"type": "text", "text": system}]}
            )
        messages.append(
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        )

        body = {
            "messages": messages,
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2048,
            "temperature": temperature,
            "repetitionPenalty": 1.1,
            "stop": [],
        }
        try:
            resp = self._client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["result"]["message"]["content"]
        except httpx.HTTPError as e:
            logger.exception("clova x request failed")
            raise LLMEvaluationFailed(str(e)) from e
        except (KeyError, TypeError) as e:
            raise LLMEvaluationFailed(f"Clova X 응답 형식 오류: {e}") from e


class MockLLMProvider(LLMProvider):
    """로컬 개발용 Mock LLM. Ncloud 자격증명 없이 결정적 응답을 반환한다."""

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str:
        logger.debug("MockLLMProvider.generate (system=%s...)", (system or "")[:30])
        s = system or ""

        if "배열로만" in s:
            return json.dumps([
                {"order": 1, "question_type": "personality",
                 "question": "팀 프로젝트에서 의견 충돌이 발생했을 때 어떻게 해결하셨나요?"},
                {"order": 2, "question_type": "technical",
                 "question": "RESTful API 설계 원칙과 실제 적용 사례를 설명해주세요."},
                {"order": 3, "question_type": "document",
                 "question": "제출하신 문서에서 가장 자신 있는 프로젝트의 기술 스택과 역할을 설명해주세요."},
                {"order": 4, "question_type": "document",
                 "question": "문서에 기술된 경험 중 가장 어려웠던 기술적 문제와 해결 방법을 설명해주세요."},
                {"order": 5, "question_type": "company",
                 "question": "당사에 지원한 이유와 입사 후 이루고 싶은 목표를 말씀해주세요."},
            ], ensure_ascii=False)

        if "모범답안" in s:
            return "핵심 개념을 명확히 설명하고, 실제 경험과 연계하여 구체적인 예시를 들며 답변하는 것이 중요합니다."

        if "코칭" in s:
            return json.dumps({
                "summary": "전반적으로 기본 개념은 이해하고 있으나 구체적인 경험 연결이 부족합니다.",
                "strengths": ["핵심 키워드를 적절히 언급함", "논리적 흐름을 유지함"],
                "weaknesses": ["구체적 수치·사례 부족", "문서 근거 기반 설명 미흡"],
                "recommendation": "답변 시 정의-이유-예시 구조를 활용하고, 실제 프로젝트 경험을 수치와 함께 제시하세요.",
            }, ensure_ascii=False)

        # 기본: 답변 평가 형식
        return json.dumps({
            "scores": {"semantic": 70, "keyword": 65, "groundedness": 60, "logic": 70, "specificity": 55},
            "strengths": ["핵심 개념을 언급하였습니다"],
            "weaknesses": ["구체적인 사례가 부족합니다"],
            "improvements": ["실무 경험을 연결하여 설명하세요"],
            "feedback": "기본 개념은 이해하고 있으나 구체성이 부족합니다.",
        }, ensure_ascii=False)


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if not s.clova_x_api_key:
        logger.warning("CLOVA_X_API_KEY not set — using MockLLMProvider")
        return MockLLMProvider()
    return ClovaXProvider(s)
