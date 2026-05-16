from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...


class FallbackObjectStorage(ObjectStorage):
    """로컬 개발 시 원격 스토리지 실패를 로컬 디스크로 폴백한다."""

    def __init__(self, primary: ObjectStorage, fallback: ObjectStorage, *, label: str):
        self._primary = primary
        self._fallback = fallback
        self._label = label

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        try:
            return self._primary.put(key, data, content_type=content_type)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "%s object storage put failed; falling back to local storage: %s",
                self._label,
                e,
            )
            return self._fallback.put(key, data, content_type=content_type)

    def get(self, key: str) -> bytes:
        try:
            return self._primary.get(key)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "%s object storage get failed; falling back to local storage: %s",
                self._label,
                e,
            )
            return self._fallback.get(key)


class LocalObjectStorage(ObjectStorage):
    """개발용. local_dir/<key>로 저장."""

    def __init__(self, local_dir: str):
        self._root = Path(local_dir).resolve()
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

    def __init__(
        self,
        endpoint: str,
        region: str,
        bucket: str,
        access_key: str,
        secret_key: str,
    ):
        try:
            import boto3
            from botocore.client import Config
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Ncloud Object Storage 사용에는 boto3가 필요합니다.") from e

        # boto3 내부 로그 억제 (INFO 레벨 노이즈 방지)
        import boto3 as _boto3
        _boto3.set_stream_logger("", logging.ERROR)

        self._bucket = bucket
        self._endpoint = endpoint
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            # Ncloud Object Storage는 SigV4 + path-style 필수
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra)

        # 업로드 후 실제 저장 여부 검증
        self._client.head_object(Bucket=self._bucket, Key=key)
        logger.info("업로드 완료: %s/%s", self._bucket, key)

        return f"{self._endpoint}/{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def debug_bucket(self) -> dict:
        """버킷 접근 가능 여부와 오브젝트 수를 반환한다."""
        result = {}
        try:
            resp = self._client.head_bucket(Bucket=self._bucket)
            result["head_bucket"] = "success"
            result["bucket_status"] = resp["ResponseMetadata"]["HTTPStatusCode"]
        except Exception as e:
            result["head_bucket"] = str(e)

        try:
            objects = self._client.list_objects_v2(Bucket=self._bucket)
            result["list_objects"] = "success"
            result["object_count"] = objects.get("KeyCount", 0)
        except Exception as e:
            result["list_objects"] = str(e)

        return result


@lru_cache(maxsize=1)
def get_voice_storage() -> ObjectStorage:
    """음성 파일(TTS 질문, 답변 녹음) 전용 스토리지."""
    s = get_settings()
    local = LocalObjectStorage(s.local_storage_dir_voice)
    if s.use_voice_storage:
        remote = NcloudObjectStorage(
            endpoint=s.object_storage_endpoint,
            region=s.object_storage_region,
            bucket=s.object_storage_bucket_voice,
            access_key=s.object_storage_access_key_voice,
            secret_key=s.object_storage_secret_key_voice,
        )
        if s.app_env == "local":
            return FallbackObjectStorage(remote, local, label="voice")
        return remote
    return local


@lru_cache(maxsize=1)
def get_document_storage() -> ObjectStorage:
    """업로드 문서 전용 스토리지."""
    s = get_settings()
    local = LocalObjectStorage(s.local_storage_dir_document)
    if s.use_document_storage:
        remote = NcloudObjectStorage(
            endpoint=s.object_storage_endpoint,
            region=s.object_storage_region,
            bucket=s.object_storage_bucket_document,
            access_key=s.object_storage_access_key_document,
            secret_key=s.object_storage_secret_key_document,
        )
        if s.app_env == "local":
            return FallbackObjectStorage(remote, local, label="document")
        return remote
    return local
