from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import TTSFailed

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    audio_bytes: bytes
    content_type: str
    duration_seconds: float | None


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> TTSResult: ...


def estimate_duration_mp3(audio_bytes: bytes) -> float | None:
    try:
        from mutagen.mp3 import MP3

        return MP3(io.BytesIO(audio_bytes)).info.length
    except Exception:  # noqa: BLE001
        return None


class ClovaVoiceProvider(TTSProvider):
    """Ncloud Clova Voice (Premium)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=30.0)

    def synthesize(self, text: str) -> TTSResult:
        s = self._settings
        if not s.clova_voice_client_id or not s.clova_voice_client_secret:
            raise TTSFailed("Clova Voice 자격 증명이 설정되지 않았습니다.")

        headers = {
            "X-NCP-APIGW-API-KEY-ID": s.clova_voice_client_id,
            "X-NCP-APIGW-API-KEY": s.clova_voice_client_secret,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "speaker": s.clova_voice_speaker,
            "text": text,
            "format": "mp3",
            "speed": "0",
            "volume": "0",
            "pitch": "0",
        }
        try:
            resp = self._client.post(s.clova_voice_api_url, headers=headers, data=data)
            resp.raise_for_status()
            audio = resp.content
            return TTSResult(
                audio_bytes=audio,
                content_type="audio/mpeg",
                duration_seconds=estimate_duration_mp3(audio),
            )
        except httpx.HTTPError as e:
            logger.exception("clova voice tts failed")
            raise TTSFailed(str(e)) from e


@lru_cache(maxsize=1)
def get_tts_provider() -> TTSProvider:
    return ClovaVoiceProvider(get_settings())
