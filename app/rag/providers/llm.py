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
            f"/testapp/v1/chat-completions/{self._settings.clova_x_model}"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.clova_x_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "messages": messages,
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2048,
            "temperature": temperature,
            "repeatPenalty": 5.0,
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


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return ClovaXProvider(get_settings())
