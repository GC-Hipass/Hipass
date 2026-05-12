import json
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

    # Server
    app_name: str = "navercloud-ai-interview"
    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    cors_origins_raw: str = Field(default="", validation_alias="CORS_ORIGINS")
    db_bootstrap_on_start: bool = False

    # DB
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/interview"

    # Ncloud common
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
    # ncloud: calls the Ncloud Embedding API. mock: offline test mode.
    embedding_provider: Literal["ncloud", "mock"] = "ncloud"
    ncloud_embedding_api_url: str = ""
    ncloud_embedding_api_key: str = ""
    ncloud_embedding_model: str = "bge-m3"
    embedding_dimension: int = 384

    # Object Storage common
    object_storage_endpoint: str = ""
    object_storage_region: str = "kr-standard"

    # Object Storage for voice files
    object_storage_bucket_voice: str = ""
    object_storage_access_key_voice: str = ""
    object_storage_secret_key_voice: str = ""
    local_storage_dir_voice: str = "./_storage/audio"

    # Object Storage for document files
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

    @property
    def should_bootstrap_db(self) -> bool:
        return self.app_env == "local" or self.db_bootstrap_on_start

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if not raw:
            return []
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated string.")
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
