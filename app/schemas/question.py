from pydantic import BaseModel


class QuestionResponse(BaseModel):
    session_id: int
    question_id: int
    order: int
    question: str
    tts_audio_url: str
    tts_duration_seconds: float | None
    recording_seconds: int
