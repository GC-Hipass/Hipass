from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

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

    candidate = _extract_json_candidate(text)
    return _json_loads_with_repairs(candidate)


def _extract_json_candidate(text: str) -> str:
    first_obj = text.find("{")
    first_arr = text.find("[")
    starts = [i for i in (first_obj, first_arr) if i != -1]
    if not starts:
        return text

    start = min(starts)
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False

    for idx in range(start, len(text)):
        ch = text[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]

    return text[start:]


def _json_loads_with_repairs(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        repaired = _escape_control_chars_in_strings(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            logger.debug("LLM JSON parse failed. raw=%r repaired=%r", text[:1000], repaired[:1000])
            raise first_error


def _escape_control_chars_in_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False

    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue
        if in_string and ord(ch) < 0x20:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(f"\\u{ord(ch):04x}")
            continue
        out.append(ch)

    return "".join(out)


class ExternalLLMProvider(LLMProvider):
    """내부 로컬 LLM 서버를 호출하는 Provider."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=settings.llm_request_timeout_seconds)

    def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.5) -> str:
        if not self._settings.llm_server_url:
            raise LLMEvaluationFailed("LLM_SERVER_URL이 설정되지 않았습니다.")

        base_url = self._settings.llm_server_url.rstrip("/")
        url = base_url if base_url.endswith("/generate") else f"{base_url}/generate"
        headers = {"Content-Type": "application/json"}
        if self._settings.llm_server_api_key:
            headers["X-Internal-API-Key"] = self._settings.llm_server_api_key

        body = {
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
        }
        try:
            resp = self._client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            text = data["text"]
            if not isinstance(text, str):
                raise TypeError("text must be a string")
            return text
        except httpx.HTTPError as e:
            logger.exception("external llm request failed")
            raise LLMEvaluationFailed(str(e)) from e
        except (KeyError, TypeError) as e:
            raise LLMEvaluationFailed(f"External LLM 응답 형식 오류: {e}") from e


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
    if s.llm_provider == "mock":
        logger.warning("LLM_PROVIDER=mock — using MockLLMProvider")
        return MockLLMProvider()
    logger.info("LLM_PROVIDER=external — using ExternalLLMProvider")
    return ExternalLLMProvider(s)
