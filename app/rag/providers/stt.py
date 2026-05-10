from __future__ import annotations

import json
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
    """Ncloud Clova Speech providers.

    Supports both:
    - CLOVA Speech local-file recognition (`.../recognizer/upload`)
    - CLOVA Speech Recognition CSR (`.../stt`)
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=120.0)

    @property
    def name(self) -> str:
        return "clova_speech"

    def transcribe(self, audio_bytes: bytes, *, content_type: str) -> str:
        s = self._settings
        if not s.clova_speech_api_url or not s.clova_speech_secret:
            raise STTFailed("Clova Speech environment variables are not configured.")

        url = s.clova_speech_api_url.rstrip("/")
        if url.endswith("/stt"):
            return self._transcribe_csr(
                url,
                audio_bytes=audio_bytes,
                language=s.clova_speech_language,
            )
        return self._transcribe_upload(
            url,
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=s.clova_speech_language,
        )

    def _transcribe_upload(
        self,
        url: str,
        *,
        audio_bytes: bytes,
        content_type: str,
        language: str,
    ) -> str:
        headers = {"X-CLOVASPEECH-API-KEY": self._settings.clova_speech_secret}
        params_payload = {
            "language": language,
            "completion": "sync",
            "callback": "",
            "fullText": True,
        }
        try:
            resp = self._client.post(
                self._upload_url(url),
                headers=headers,
                data={
                    "params": json.dumps(params_payload, ensure_ascii=False),
                    "type": "application/json",
                },
                files={
                    "media": (
                        self._filename_from_content_type(content_type),
                        audio_bytes,
                        content_type,
                    )
                },
            )
            resp.raise_for_status()
            text = self._extract_text(resp.json())
            if not text:
                raise STTFailed("Unexpected empty STT response.")
            return text
        except httpx.HTTPError as e:
            logger.exception("clova speech upload stt failed")
            raise STTFailed(str(e)) from e

    def _transcribe_csr(
        self,
        url: str,
        *,
        audio_bytes: bytes,
        language: str,
    ) -> str:
        headers = {
            "X-CLOVASPEECH-API-KEY": self._settings.clova_speech_secret,
            "Content-Type": "application/octet-stream",
        }
        try:
            resp = self._client.post(
                url,
                params={"lang": self._to_csr_language(language)},
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            text = self._extract_text(resp.json())
            if not text:
                raise STTFailed("Unexpected empty STT response.")
            return text
        except httpx.HTTPError as e:
            logger.exception("clova speech csr failed")
            raise STTFailed(str(e)) from e

    @staticmethod
    def _upload_url(base_url: str) -> str:
        if base_url.endswith("/recognizer/upload"):
            return base_url
        if base_url.endswith("/recognizer"):
            return f"{base_url}/upload"
        return f"{base_url}/recognizer/upload"

    @staticmethod
    def _filename_from_content_type(content_type: str) -> str:
        normalized = (content_type or "").split(";")[0].strip().lower()
        ext_map = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".mp4",
            "audio/m4a": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
        }
        return f"speech{ext_map.get(normalized, '.wav')}"

    @staticmethod
    def _to_csr_language(language: str) -> str:
        return {
            "ko-KR": "Kor",
            "en-US": "Eng",
            "ja": "Jpn",
            "zh-cn": "Chn",
            "zh-tw": "Chn",
        }.get(language, "Kor")

    @staticmethod
    def _extract_text(data: object) -> str:
        if isinstance(data, dict):
            text = data.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

            result = data.get("result")
            if isinstance(result, dict):
                result_text = result.get("text")
                if isinstance(result_text, str) and result_text.strip():
                    return result_text.strip()

            segments = data.get("segments")
            if isinstance(segments, list):
                parts: list[str] = []
                for item in segments:
                    if isinstance(item, dict):
                        segment_text = item.get("text")
                        if isinstance(segment_text, str) and segment_text.strip():
                            parts.append(segment_text.strip())
                if parts:
                    return " ".join(parts)
        return ""


class MockSTTProvider(STTProvider):
    """Local mock STT for development without external credentials."""

    @property
    def name(self) -> str:
        return "mock_stt"

    def transcribe(self, audio_bytes: bytes, *, content_type: str) -> str:
        logger.debug("MockSTTProvider.transcribe called (%d bytes)", len(audio_bytes))
        return "테스트 답변입니다. 해당 질문에 대해 최선을 다해 답변하겠습니다."


@lru_cache(maxsize=1)
def get_stt_provider() -> STTProvider:
    s = get_settings()
    if not s.clova_speech_api_url or not s.clova_speech_secret:
        logger.warning("Clova Speech credentials not set -> using MockSTTProvider")
        return MockSTTProvider()
    return ClovaSpeechProvider(s)
