from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import Settings, get_settings
from app.core.exceptions import EmbeddingFailed

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by a local SentenceTransformer model."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.model_name = "paraphrase-multilingual-MiniLM-L12-v2"

        try:
            logger.info("Loading local embedding model: %s...", self.model_name)
            self._model = SentenceTransformer(self.model_name, device="cpu")
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            raise EmbeddingFailed(f"Failed to load embedding model: {str(e)}")

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            embeddings = self._model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.exception("Local embedding generation failed")
            raise EmbeddingFailed(f"Embedding generation failed: {str(e)}")


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embeddings for smoke tests."""
    def __init__(self, settings: Settings):
        self._dim = settings.embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()[:8]
            seed = int.from_bytes(seed_bytes, "little")
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self._dim)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            out.append(v.astype(float).tolist())
        return out


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider as a cached singleton."""
    settings = get_settings()

    if settings.embedding_provider == "mock":
        logger.info("embedding provider: MOCK (deterministic, offline)")
        return MockEmbeddingProvider(settings)

    if settings.embedding_provider == "ncloud":
        logger.warning(
            "EMBEDDING_PROVIDER=ncloud is a legacy alias for local SentenceTransformer; "
            "Ncloud Embedding API is not implemented."
        )

    logger.info("embedding provider: LOCAL (SentenceTransformer)")
    return LocalEmbeddingProvider(settings)
