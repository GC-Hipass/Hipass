from __future__ import annotations

import io
import json
import logging
import struct
import wave
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


def _is_effectively_empty_transcript(text: str) -> bool:
    return not text.strip()


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

        audio_bytes = self._normalize_wav_for_stt(audio_bytes, content_type)
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
            data = resp.json()
            text = self._extract_text(data)
            if _is_effectively_empty_transcript(text):
                logger.warning(
                    "clova speech upload returned empty transcript: %s",
                    self._summarize_response(data),
                )
                return ""
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
            data = resp.json()
            text = self._extract_text(data)
            if _is_effectively_empty_transcript(text):
                logger.warning(
                    "clova speech csr returned empty transcript: %s",
                    self._summarize_response(data),
                )
                return ""
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
                        segment_text = item.get("text") or item.get("textEdited")
                        if isinstance(segment_text, str) and segment_text.strip():
                            parts.append(segment_text.strip())
                            continue

                        words = item.get("words")
                        if isinstance(words, list):
                            for word in words:
                                if (
                                    isinstance(word, list)
                                    and len(word) >= 3
                                    and isinstance(word[2], str)
                                    and word[2].strip()
                                ):
                                    parts.append(word[2].strip())
                if parts:
                    return " ".join(parts)
        return ""

    @staticmethod
    def _normalize_wav_for_stt(audio_bytes: bytes, content_type: str) -> bytes:
        normalized_type = (content_type or "").split(";")[0].strip().lower()
        is_wav = normalized_type in {"audio/wav", "audio/x-wav"} or (
            audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"
        )
        if not is_wav:
            return audio_bytes

        try:
            source = io.BytesIO(audio_bytes)
            with wave.open(source, "rb") as reader:
                params = reader.getparams()
                if reader.getcomptype() != "NONE" or reader.getsampwidth() != 2:
                    return audio_bytes
                frames = reader.readframes(reader.getnframes())

            if not frames:
                return audio_bytes

            sample_count = len(frames) // 2
            samples = struct.unpack(f"<{sample_count}h", frames)
            peak = max(abs(sample) for sample in samples)
            if peak == 0:
                return audio_bytes

            target_peak = int(32767 * 0.85)
            gain = min(12.0, target_peak / peak)
            if gain <= 1.25:
                return audio_bytes

            amplified = bytearray(len(frames))
            for index, sample in enumerate(samples):
                value = int(sample * gain)
                value = max(-32768, min(32767, value))
                struct.pack_into("<h", amplified, index * 2, value)

            output = io.BytesIO()
            with wave.open(output, "wb") as writer:
                writer.setparams(params)
                writer.writeframes(bytes(amplified))

            logger.info(
                "normalized wav for stt: peak=%d gain=%.2f sample_rate=%d channels=%d",
                peak,
                gain,
                params.framerate,
                params.nchannels,
            )
            return output.getvalue()
        except (EOFError, wave.Error, struct.error, ValueError) as e:
            logger.warning("failed to normalize wav for stt: %s", e)
            return audio_bytes

    @staticmethod
    def _summarize_response(data: object) -> str:
        if not isinstance(data, dict):
            return repr(data)[:1000]

        summary = {
            "result": data.get("result"),
            "message": data.get("message"),
            "progress": data.get("progress"),
            "text": data.get("text"),
            "confidence": data.get("confidence"),
            "segments_count": len(data.get("segments", []))
            if isinstance(data.get("segments"), list)
            else None,
        }
        return json.dumps(summary, ensure_ascii=False)


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
    if s.stt_provider == "mock":
        logger.warning("STT_PROVIDER=mock -> using MockSTTProvider")
        return MockSTTProvider()
    if not s.clova_speech_api_url or not s.clova_speech_secret:
        logger.warning("Clova Speech credentials not set -> using MockSTTProvider")
        return MockSTTProvider()
    return ClovaSpeechProvider(s)
