from typing import Any


class AppError(Exception):
    """애플리케이션 도메인 예외 베이스. status_code, code, message를 가진다."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str | None = None, *, details: Any = None):
        self.message = message or self.code
        self.details = details
        super().__init__(self.message)


# 400
class InvalidFileType(AppError):
    status_code = 400
    code = "INVALID_FILE_TYPE"


class InvalidOption(AppError):
    status_code = 400
    code = "INVALID_OPTION"


class AnswerAlreadyExists(AppError):
    status_code = 400
    code = "ANSWER_ALREADY_EXISTS"


class InvalidAudioFile(AppError):
    status_code = 400
    code = "INVALID_AUDIO_FILE"


class SessionNotCompleted(AppError):
    status_code = 400
    code = "SESSION_NOT_COMPLETED"


# 404
class SessionNotFound(AppError):
    status_code = 404
    code = "SESSION_NOT_FOUND"


class QuestionNotFound(AppError):
    status_code = 404
    code = "QUESTION_NOT_FOUND"


# 500
class DocumentParseFailed(AppError):
    status_code = 500
    code = "DOCUMENT_PARSE_FAILED"


class EmbeddingFailed(AppError):
    status_code = 500
    code = "EMBEDDING_FAILED"


class TTSFailed(AppError):
    status_code = 500
    code = "TTS_FAILED"


class STTFailed(AppError):
    status_code = 500
    code = "STT_FAILED"


class LLMEvaluationFailed(AppError):
    status_code = 500
    code = "LLM_EVALUATION_FAILED"
