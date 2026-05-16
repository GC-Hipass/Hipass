"""RAG의 외부 의존성을 인터페이스로 추상화한 계층.

각 provider는 ABC를 구현한다. 구현체를 갈아끼울 때는 factory에서만 변경.
"""
from __future__ import annotations

from importlib import import_module

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


def __getattr__(name: str):
    if name in {"EmbeddingProvider", "get_embedding_provider"}:
        module = import_module("app.rag.providers.embedding")
        return getattr(module, name)
    if name in {"LLMProvider", "get_llm_provider"}:
        module = import_module("app.rag.providers.llm")
        return getattr(module, name)
    if name in {"ObjectStorage", "get_document_storage", "get_voice_storage"}:
        module = import_module("app.rag.providers.object_storage")
        return getattr(module, name)
    if name in {"STTProvider", "get_stt_provider"}:
        module = import_module("app.rag.providers.stt")
        return getattr(module, name)
    if name in {"TTSProvider", "TTSResult", "get_tts_provider"}:
        module = import_module("app.rag.providers.tts")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
