from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 서버
    app_name: str = "navercloud-ai-interview"
    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    # DB
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/interview"

    # Ncloud 공통
    ncloud_access_key: str = ""
    ncloud_secret_key: str = ""

    # Clova X (LLM)
    clova_x_api_url: str = "https://clovastudio.stream.ntruss.com"
    clova_x_api_key: str = ""
    clova_x_model: str = "HCX-005"

    # Clova Voice (TTS)
    clova_voice_api_url: str = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
    clova_voice_client_id: str = ""
    clova_voice_client_secret: str = ""
    clova_voice_speaker: str = "nara"

    # Clova Speech (STT)
    clova_speech_api_url: str = ""
    clova_speech_secret: str = ""
    clova_speech_language: str = "ko-KR"

    # Embedding
    # ncloud: Ncloud Embedding API 호출. mock: 결정적 의사 임베딩 (오프라인 테스트용).
    embedding_provider: Literal["ncloud", "mock"] = "ncloud"
    ncloud_embedding_api_url: str = ""
    ncloud_embedding_api_key: str = ""
    ncloud_embedding_model: str = "bge-m3"
    embedding_dimension: int = 1024

    # Object Storage — 공통
    object_storage_endpoint: str = ""
    object_storage_region: str = "kr-standard"

    # Object Storage — 음성 파일 전용
    object_storage_bucket_voice: str = ""
    object_storage_access_key_voice: str = ""
    object_storage_secret_key_voice: str = ""
    local_storage_dir_voice: str = "./_storage/audio"

    # Object Storage — 문서 파일 전용
    object_storage_bucket_document: str = ""
    object_storage_access_key_document: str = ""
    object_storage_secret_key_document: str = ""
    local_storage_dir_document: str = "./_storage/documents"

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 8
    rerank_top_k: int = 4
    question_count: int = 5
    recording_seconds: int = 30

    @property
    def use_voice_storage(self) -> bool:
        return bool(self.object_storage_endpoint and self.object_storage_bucket_voice)

    @property
    def use_document_storage(self) -> bool:
        return bool(self.object_storage_endpoint and self.object_storage_bucket_document)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
