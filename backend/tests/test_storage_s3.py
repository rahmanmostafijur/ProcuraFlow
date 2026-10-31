"""The S3-compatible backend, run against a fake transport: no network and no bucket."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app import storage as storage_module
from app.core.config import Settings
from app.storage.base import InvalidStorageKeyError, StoredObjectNotFoundError
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage, StorageError, sign_request

KEY = "attachments/0123456789abcdef.pdf"
FIXED_NOW = datetime(2026, 11, 1, 12, 30, 0, tzinfo=UTC)
SECRET = "super-secret-access-key"


class FakeBucket:
    """Records every request and answers like a bucket that holds whatever was last PUT."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        self.objects: dict[str, bytes] = {}
        self.forced_status: int | None = None

    def __call__(self, method: str, url: str, headers: Mapping[str, str], body: bytes) -> tuple[int, bytes]:
        self.requests.append((method, url, dict(headers), body))
        if self.forced_status is not None:
            return self.forced_status, b"<Error/>"
        if method == "PUT":
            self.objects[url] = body
            return 200, b""
        if method == "GET":
            return (200, self.objects[url]) if url in self.objects else (404, b"<Error>NoSuchKey</Error>")
        self.objects.pop(url, None)
        return 204, b""


def _storage(bucket: FakeBucket) -> S3Storage:
    return S3Storage(
        endpoint_url="https://s3.example.test/",
        bucket="files",
        region="eu-central-1",
        access_key_id="AKIDEXAMPLE",
        secret_access_key=SECRET,
        transport=bucket,
        clock=lambda: FIXED_NOW,
    )


def test_signature_matches_the_published_aws_example() -> None:
    # The "GET Object" example from the AWS Signature Version 4 documentation.
    headers = sign_request(
        method="GET",
        url="https://examplebucket.s3.amazonaws.com/test.txt",
        region="us-east-1",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        payload=b"",
        now=datetime(2013, 5, 24, tzinfo=UTC),
        headers={"Range": "bytes=0-9"},
    )

    assert headers["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


async def test_save_puts_the_bytes_at_a_path_style_url_with_a_signed_request() -> None:
    bucket = FakeBucket()

    await _storage(bucket).save(KEY, b"file bytes", "application/pdf")

    method, url, headers, body = bucket.requests[0]
    assert (method, url, body) == ("PUT", f"https://s3.example.test/files/{KEY}", b"file bytes")
    assert headers["content-type"] == "application/pdf"
    assert headers["x-amz-date"] == "20261101T123000Z"
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261101/eu-central-1/s3/")
    assert SECRET not in str(headers)


async def test_read_returns_what_was_saved_and_delete_removes_it() -> None:
    bucket = FakeBucket()
    storage = _storage(bucket)
    await storage.save(KEY, b"hello", "application/pdf")

    assert await storage.read(KEY) == b"hello"

    await storage.delete(KEY)
    with pytest.raises(StoredObjectNotFoundError):
        await storage.read(KEY)


async def test_deleting_a_missing_object_is_not_an_error() -> None:
    bucket = FakeBucket()
    bucket.forced_status = 404

    await _storage(bucket).delete(KEY)


async def test_a_failing_bucket_raises_without_leaking_credentials() -> None:
    bucket = FakeBucket()
    bucket.forced_status = 500
    storage = _storage(bucket)

    with pytest.raises(StorageError) as saving:
        await storage.save(KEY, b"x", "application/pdf")
    with pytest.raises(StorageError) as reading:
        await storage.read(KEY)

    assert "500" in str(saving.value)
    assert SECRET not in str(saving.value) + str(reading.value)


async def test_keys_that_are_not_server_generated_never_reach_the_bucket() -> None:
    bucket = FakeBucket()

    with pytest.raises(InvalidStorageKeyError):
        await _storage(bucket).read("../secret.txt")

    assert bucket.requests == []


S3_SETTINGS: dict[str, Any] = {
    "storage_backend": "s3",
    "s3_endpoint_url": "https://s3.example.test",
    "s3_bucket": "files",
    "s3_region": "eu-central-1",
    "s3_access_key_id": "AKIDEXAMPLE",
    "s3_secret_access_key": SECRET,
}


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, environment="test", jwt_secret_key="x" * 40, **(S3_SETTINGS | overrides))


def test_the_local_backend_is_the_default_and_needs_no_s3_settings() -> None:
    settings = Settings(_env_file=None, environment="test", jwt_secret_key="x" * 40)

    assert settings.storage_backend == "local"


def test_s3_settings_are_accepted_when_complete() -> None:
    assert _settings().storage_backend == "s3"


@pytest.mark.parametrize(
    "missing", ["s3_endpoint_url", "s3_bucket", "s3_region", "s3_access_key_id", "s3_secret_access_key"]
)
def test_s3_needs_every_setting_and_names_the_missing_one(missing: str) -> None:
    with pytest.raises(ValidationError, match=missing.upper()):
        _settings(**{missing: None})


def test_a_blank_s3_setting_counts_as_missing() -> None:
    with pytest.raises(ValidationError, match="S3_BUCKET"):
        _settings(s3_bucket="  ")


def test_the_s3_endpoint_must_be_an_http_url() -> None:
    with pytest.raises(ValidationError, match="S3_ENDPOINT_URL must start with"):
        _settings(s3_endpoint_url="ftp://s3.example.test")


def test_get_storage_builds_the_backend_the_environment_selects(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings)
    storage_module.get_storage.cache_clear()
    try:
        assert isinstance(storage_module.get_storage(), S3Storage)
        local = Settings(_env_file=None, environment="test", jwt_secret_key="x" * 40)
        monkeypatch.setattr(storage_module, "get_settings", lambda: local)
        storage_module.get_storage.cache_clear()
        assert isinstance(storage_module.get_storage(), LocalStorage)
    finally:
        storage_module.get_storage.cache_clear()
