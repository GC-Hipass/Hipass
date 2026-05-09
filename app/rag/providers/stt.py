from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import STTFailed

logger = logging.getLogger(__name__)


class STTProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, *, content_type: str) -> str: ...


class ClovaSpeechProvider(STTProvider):
    """Ncloud Clova Speech (CSR)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=120.0)

    @property
    def name(self) -> str:
        return "clova_speech"

    def transcribe(self, audio_bytes: bytes, *, content_type: str) -> str:
        s = self._settings
        if not s.clova_speech_api_url or not s.clova_speech_secret:
            raise STTFailed("Clova Speech 환경변수가 설정되지 않았습니다.")

        # Clova Speech recognizer/upload 엔드포인트 호출.
        # 실제 스펙에 맞춰 params/json/headers는 운영 환경에서 보정해야 한다.
        headers = {
            "X-CLOVASPEECH-API-KEY": s.clova_speech_secret,
            "Content-Type": "application/octet-stream",
        }
        params = {"lang": s.clova_speech_language}
        try:
            resp = self._client.post(
                f"{s.clova_speech_api_url.rstrip('/')}/recognizer/upload",
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("text") or data.get("result", {}).get("text", "")
            if not isinstance(text, str):
                raise STTFailed(f"STT 응답 형식 오류: {data}")
            return text.strip()
        except httpx.HTTPError as e:
            logger.exception("clova speech stt failed")
            raise STTFailed(str(e)) from e


@lru_cache(maxsize=1)
def get_stt_provider() -> STTProvider:
    return ClovaSpeechProvider(get_settings())
