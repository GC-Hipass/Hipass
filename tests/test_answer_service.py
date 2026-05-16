from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import answer_service


class _FakeScalarResult:
    def scalar_one_or_none(self):
        return None


class _FakeDB:
    def __init__(self) -> None:
        self.added = []
        self.flushed = 0

    def get(self, model, pk):  # noqa: ANN001
        return SimpleNamespace(id=pk, session_id=1, order=2)

    def execute(self, stmt):  # noqa: ANN001
        return _FakeScalarResult()

    def add(self, item):  # noqa: ANN001
        self.added.append(item)

    def flush(self) -> None:
        self.flushed += 1


class _FakeVoiceStore:
    def put(self, key: str, content: bytes, *, content_type: str) -> str:
        return f"stored://{key}"


class _FakeSTT:
    name = "fake_stt"

    def __init__(self, transcript: str):
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, audio_bytes: bytes, *, content_type: str) -> str:
        self.calls += 1
        return self.transcript


class AnswerServiceTests(unittest.TestCase):
    def test_zero_second_recording_is_saved_without_stt(self) -> None:
        db = _FakeDB()
        fake_stt = _FakeSTT("should not be used")

        with patch("app.services.answer_service.storage_service.get_voice_store", return_value=_FakeVoiceStore()):
            with patch("app.services.answer_service.get_stt_provider", return_value=fake_stt):
                answer = answer_service.store_answer(
                    db,
                    session_id=1,
                    question_id=10,
                    audio_bytes=b"fake-audio",
                    audio_filename="answer.wav",
                    content_type="audio/wav",
                    recording_duration_seconds=0,
                )

        self.assertEqual(fake_stt.calls, 0)
        self.assertEqual(answer.answer_text, "")
        self.assertEqual(answer.stt_provider, "fake_stt")

    def test_empty_stt_transcript_is_accepted(self) -> None:
        db = _FakeDB()
        fake_stt = _FakeSTT("")

        with patch("app.services.answer_service.storage_service.get_voice_store", return_value=_FakeVoiceStore()):
            with patch("app.services.answer_service.get_stt_provider", return_value=fake_stt):
                answer = answer_service.store_answer(
                    db,
                    session_id=1,
                    question_id=11,
                    audio_bytes=b"fake-audio",
                    audio_filename="answer.wav",
                    content_type="audio/wav",
                    recording_duration_seconds=7,
                )

        self.assertEqual(fake_stt.calls, 1)
        self.assertEqual(answer.answer_text, "")
        self.assertEqual(answer.audio_path, "stored://answers/sessions/1/q11.wav")


if __name__ == "__main__":
    unittest.main()
