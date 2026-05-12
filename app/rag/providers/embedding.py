from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx
import numpy as np
from sentence_transformers import SentenceTransformer  # 모델 로드용 추가

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
    """로컬 SentenceTransformer 모델 기반 임베딩 프로바이더.
    
    모델을 메모리에 올리고 싱글톤 형태로 유지하여 API 호출 없이 로컬 CPU에서 처리합니다.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        # 모델 이름 지정
        self.model_name = "paraphrase-multilingual-MiniLM-L12-v2"
        
        try:
            logger.info(f"Loading local embedding model: {self.model_name}...")
            # 모델 로드 (최초 1회 다운로드 후 캐시됨)
            # 4GB RAM 환경이므로 device='cpu'를 명시적으로 설정하는 것이 안전합니다.
            self._model = SentenceTransformer(self.model_name, device='cpu')
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise EmbeddingFailed(f"모델 로드 실패: {str(e)}")

    @property
    def dimension(self) -> int:
        # 이 모델의 차원은 384입니다. 
        # 하드코딩 대신 모델에서 직접 가져오도록 설정합니다.
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        try:
            # 모델을 사용하여 임베딩 생성
            embeddings = self._model.encode(texts)
            # numpy array를 list로 변환하여 반환
            return embeddings.tolist()
        except Exception as e:
            logger.exception("Local embedding generation failed")
            raise EmbeddingFailed(f"임베딩 생성 오류: {str(e)}")


class MockEmbeddingProvider(EmbeddingProvider):
    """결정적 mock 임베딩 (테스트용)"""
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
    """싱글톤 방식으로 프로바이더를 제공합니다. 
    @lru_cache(maxsize=1) 덕분에 모델 로드는 한 번만 일어납니다.
    """
    settings = get_settings()
    
    if settings.embedding_provider == "mock":
        logger.info("embedding provider: MOCK (deterministic, offline)")
        return MockEmbeddingProvider(settings)
    
    # 기본값을 로컬 모델 프로바이더로 사용
    logger.info("embedding provider: LOCAL (SentenceTransformer)")
    return LocalEmbeddingProvider(settings)