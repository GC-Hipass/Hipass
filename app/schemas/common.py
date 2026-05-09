from enum import Enum


class Company(str, Enum):
    naver = "naver"
    sk = "sk"
    samsung = "samsung"


class Difficulty(str, Enum):
    easy = "easy"
    normal = "normal"
    hard = "hard"


class JobRole(str, Enum):
    app = "app"
    web = "web"
    ai = "ai"
    devops = "devops"


class QuestionType(str, Enum):
    personality = "personality"
    technical = "technical"
    document = "document"
    company = "company"


SUPPORTED_FILE_EXTENSIONS = {".pdf", ".docx", ".txt"}
SUPPORTED_AUDIO_MIME = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
}
