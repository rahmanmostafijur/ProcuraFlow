"""An S3-compatible storage backend (AWS S3, MinIO, Cloudflare R2, Backblaze B2) with no SDK dependency.

Requests are signed with AWS Signature Version 4 using only the standard library, and sent over HTTP from a worker
thread so the event loop is never blocked. Path-style addressing (``endpoint/bucket/key``) is used because every
S3-compatible service accepts it. The transport is injectable, which is how the tests run without a network.
"""

import asyncio
import hashlib
import hmac
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

from app.storage.base import StoredObjectNotFoundError, validate_storage_key

SERVICE = "s3"
ALGORITHM = "AWS4-HMAC-SHA256"
REQUEST_TIMEOUT_SECONDS = 30
HTTP_NOT_FOUND = 404
HTTP_ERROR_FLOOR = 300

# (method, url, headers, body) -> (status code, response body)
Transport = Callable[[str, str, Mapping[str, str], bytes], tuple[int, bytes]]


class StorageError(RuntimeError):
    """The bucket refused or failed a request. The message never contains credentials."""


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def sign_request(
    *,
    method: str,
    url: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    payload: bytes,
    now: datetime,
    headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The request headers to send, including ``Authorization``, for a request signed at ``now``."""
    parts = urlsplit(url)
    amz_date = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    day = amz_date[:8]
    payload_hash = hashlib.sha256(payload).hexdigest()
    signed = {name.lower(): value.strip() for name, value in (headers or {}).items()}
    signed |= {"host": parts.netloc, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}

    names = sorted(signed)
    canonical_headers = "".join(f"{name}:{signed[name]}\n" for name in names)
    signed_names = ";".join(names)
    canonical_request = "\n".join(
        [method, parts.path or "/", parts.query, canonical_headers, signed_names, payload_hash]
    )
    scope = f"{day}/{region}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join([ALGORITHM, amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    key = _hmac(f"AWS4{secret_access_key}".encode(), day)
    for part in (region, SERVICE, "aws4_request"):
        key = _hmac(key, part)
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"{ALGORITHM} Credential={access_key_id}/{scope},SignedHeaders={signed_names},Signature={signature}"
    # "host" is set by the HTTP client itself; everything else that was signed must be sent as signed.
    sent = {name: value for name, value in signed.items() if name != "host"}
    return sent | {"Authorization": authorization}


def urllib_transport(method: str, url: str, headers: Mapping[str, str], body: bytes) -> tuple[int, bytes]:
    if not url.startswith(("https://", "http://")):
        raise StorageError("The storage endpoint must be an http(s) URL")
    request = urllib.request.Request(url, data=body or None, headers=dict(headers), method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise StorageError(f"The storage endpoint could not be reached: {exc.reason}") from exc


class S3Storage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        transport: Transport = urllib_transport,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._endpoint = endpoint_url.rstrip("/")
        self._bucket = bucket
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._transport = transport
        self._clock = clock

    def _url(self, key: str) -> str:
        return f"{self._endpoint}/{quote(self._bucket, safe='')}/{quote(validate_storage_key(key), safe='/')}"

    async def _send(
        self, method: str, key: str, body: bytes = b"", headers: Mapping[str, str] | None = None
    ) -> tuple[int, bytes]:
        url = self._url(key)
        signed = sign_request(
            method=method,
            url=url,
            region=self._region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            payload=body,
            now=self._clock(),
            headers=headers,
        )
        return await asyncio.to_thread(self._transport, method, url, signed, body)

    @staticmethod
    def _ensure_ok(status: int, action: str, key: str) -> None:
        if status >= HTTP_ERROR_FLOOR:
            raise StorageError(f"Could not {action} {key}: the bucket answered {status}")

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        status, _ = await self._send("PUT", key, data, {"Content-Type": content_type})
        self._ensure_ok(status, "store", key)

    async def read(self, key: str) -> bytes:
        status, body = await self._send("GET", key)
        if status == HTTP_NOT_FOUND:
            raise StoredObjectNotFoundError(key)
        self._ensure_ok(status, "read", key)
        return body

    async def delete(self, key: str) -> None:
        status, _ = await self._send("DELETE", key)
        if status != HTTP_NOT_FOUND:
            self._ensure_ok(status, "delete", key)
