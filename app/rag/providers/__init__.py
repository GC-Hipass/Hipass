"""RAG의 외부 의존성을 인터페이스로 추상화한 계층.

각 provider는 ABC를 구현한다. 구현체를 갈아끼울 때는 factory에서만 변경.
"""
from app.rag.providers.embedding import EmbeddingProvider, get_embedding_provider
from app.rag.providers.llm import LLMProvider, get_llm_provider
from app.rag.providers.object_storage import ObjectStorage, get_document_storage, get_voice_storage
from app.rag.providers.stt import STTProvider, get_stt_provider
from app.rag.providers.tts import TTSProvider, TTSResult, get_tts_provider

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "ObjectStorage",
    "STTProvider",
    "TTSProvider",
    "TTSResult",
    "get_embedding_provider",
    "get_llm_provider",
    "get_voice_storage",
    "get_document_storage",
    "get_stt_provider",
    "get_tts_provider",
]
