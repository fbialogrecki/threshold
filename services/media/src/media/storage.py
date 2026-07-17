from __future__ import annotations

from dataclasses import dataclass
from typing import Any, BinaryIO, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

from media.settings import Settings


class ObjectStorage(Protocol):
    def put_object(
        self, *, bucket: str, key: str, body: bytes | BinaryIO, content_type: str
    ) -> None: ...

    def get_object(self, *, bucket: str, key: str) -> tuple[bytes, str]: ...

    def delete_object(self, *, bucket: str, key: str) -> None: ...


@dataclass
class StoredObject:
    body: bytes
    content_type: str


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], StoredObject] = {}

    def put_object(
        self, *, bucket: str, key: str, body: bytes | BinaryIO, content_type: str
    ) -> None:
        stored_body = body if isinstance(body, bytes) else body.read()
        self.objects[(bucket, key)] = StoredObject(body=stored_body, content_type=content_type)

    def get_object(self, *, bucket: str, key: str) -> tuple[bytes, str]:
        stored = self.objects[(bucket, key)]
        return stored.body, stored.content_type

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._settings.s3_endpoint_url,
                region_name=self._settings.s3_region,
                aws_access_key_id=self._settings.s3_access_key_id,
                aws_secret_access_key=self._settings.s3_secret_access_key,
                config=Config(
                    s3={"addressing_style": "path" if self._settings.s3_path_style else "auto"}
                ),
            )
        return self._client

    def put_object(
        self, *, bucket: str, key: str, body: bytes | BinaryIO, content_type: str
    ) -> None:
        self.client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)

    def get_object(self, *, bucket: str, key: str) -> tuple[bytes, str]:
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read(), response.get("ContentType", "application/octet-stream")

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)
