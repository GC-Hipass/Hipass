from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

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


class NcloudEmbeddingProvider(EmbeddingProvider):
    """Ncloud 임베딩 모델 클라이언트.

    실제 Ncloud Embedding API 스펙에 맞게 _request payload를 조정한다.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = httpx.Client(timeout=30.0)

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dimension

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._settings.ncloud_embedding_api_url or not self._settings.ncloud_embedding_api_key:
            raise EmbeddingFailed("Ncloud Embedding 환경변수가 설정되지 않았습니다.")

        headers = {
            "Authorization": f"Bearer {self._settings.ncloud_embedding_api_key}",
            "Content-Type": "application/json",
        }
        results: list[list[float]] = []
        # Ncloud 임베딩은 단건/배치 스펙이 모델별로 다름. 여기서는 단건 호출 루프.
        for text in texts:
            try:
                resp = self._client.post(
                    self._settings.ncloud_embedding_api_url,
                    headers=headers,
                    json={"text": text},
                )
                resp.raise_for_status()
                data = resp.json()
                vec = data.get("result", {}).get("embedding") or data.get("embedding")
                if not vec:
                    raise EmbeddingFailed(f"임베딩 응답이 비어 있습니다: {data}")
                results.append(vec)
            except httpx.HTTPError as e:
                logger.exception("embedding request failed")
                raise EmbeddingFailed(str(e)) from e
        return results


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    return NcloudEmbeddingProvider(get_settings())
