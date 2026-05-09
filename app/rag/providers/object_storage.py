from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...


class LocalObjectStorage(ObjectStorage):
    """개발용. LOCAL_STORAGE_DIR/<key>로 저장."""

    def __init__(self, settings: Settings):
        self._root = Path(settings.local_storage_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # key 트래버설 방지
        path = (self._root / key).resolve()
        if not str(path).startswith(str(self._root)):
            raise ValueError(f"invalid key: {key}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path(key)
        path.write_bytes(data)
        return str(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class NcloudObjectStorage(ObjectStorage):
    """Ncloud Object Storage (S3 호환).

    boto3가 필요하므로 환경에 boto3가 있을 때만 활성화된다.
    """

    def __init__(self, settings: Settings):
        try:
            import boto3
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Ncloud Object Storage 사용에는 boto3가 필요합니다.") from e

        self._bucket = settings.object_storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            region_name=settings.object_storage_region,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
        )

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra)
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    if settings.use_object_storage:
        return NcloudObjectStorage(settings)
    return LocalObjectStorage(settings)
