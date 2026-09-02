"""Private Supabase Storage client used only by the backend."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from threading import Lock
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings


_shared_client: httpx.Client | None = None
_shared_client_lock = Lock()


def _get_shared_client() -> httpx.Client:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        with _shared_client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = httpx.Client(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    limits=httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=30.0),
                )
    return _shared_client


def close_shared_storage_client() -> None:
    global _shared_client
    with _shared_client_lock:
        if _shared_client is not None and not _shared_client.is_closed:
            _shared_client.close()
        _shared_client = None


class StorageError(RuntimeError):
    pass


class StorageNotFound(StorageError):
    pass


@dataclass(frozen=True)
class StoredPdf:
    object_key: str
    bucket: str
    size_bytes: int
    sha256: str
    etag: str | None
    provider: str = "supabase"


class SupabaseStorage:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self._settings = settings
        self._client = client or _get_shared_client()
        self._bucket: str | None = None

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def bucket(self) -> str:
        if self._bucket is None:
            self._bucket = self.settings.supabase_storage_bucket
        return self._bucket

    @property
    def headers(self) -> dict[str, str]:
        key = self.settings.supabase_service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, f"{self.settings.supabase_url}{path}", headers=self.headers, **kwargs)
        except httpx.HTTPError as exc:
            raise StorageError("Supabase Storage could not be reached.") from exc
        return response

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Unexpected provider response."
        return str(payload.get("message") or payload.get("error") or "Unexpected provider response.")[:240]

    @classmethod
    def _not_found(cls, response: httpx.Response) -> bool:
        if response.status_code == 404:
            return True
        try:
            payload = response.json()
        except ValueError:
            return False
        return str(payload.get("statusCode")) == "404" or "not found" in str(payload.get("message", "")).lower()

    ASSET_MIME_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/svg+xml"]

    def _bucket_file_size_limit(self) -> int:
        """Return the largest configured object limit, capped at Supabase's max 50MB."""

        legacy = int(getattr(self.settings, "max_upload_bytes", 0) or 0)
        limit = max(
            int(getattr(self.settings, "max_source_pdf_bytes", legacy) or legacy),
            int(getattr(self.settings, "max_generated_pdf_bytes", legacy) or legacy),
            int(getattr(self.settings, "max_asset_bytes", legacy) or legacy),
        )
        return min(limit, 52428800) if limit > 0 else 52428800

    def ensure_bucket(self) -> None:
        bucket_id = quote(self.bucket, safe="")
        response = self._request("GET", f"/storage/v1/bucket/{bucket_id}")
        if response.status_code == 200:
            payload = response.json()
            if payload.get("public") is True:
                raise StorageError("The Supabase PDF bucket must be private.")
            allowed = payload.get("allowed_mime_types") or []
            if not all(mime in allowed for mime in self.ASSET_MIME_TYPES):
                updated = self._request(
                    "PUT",
                    f"/storage/v1/bucket/{bucket_id}",
                    json={
                        "file_size_limit": self._bucket_file_size_limit(),
                        "allowed_mime_types": self.ASSET_MIME_TYPES,
                    },
                )
                if updated.status_code not in {200, 201}:
                    raise StorageError(
                        f"Supabase bucket mime-type update failed ({updated.status_code}): {self._error_message(updated)}"
                    )
            return
        if not self._not_found(response):
            raise StorageError(f"Supabase bucket check failed ({response.status_code}): {self._error_message(response)}")
        created = self._request(
            "POST",
            "/storage/v1/bucket",
            json={
                "id": self.bucket,
                "name": self.bucket,
                "public": False,
                "file_size_limit": self._bucket_file_size_limit(),
                "allowed_mime_types": self.ASSET_MIME_TYPES,
            },
        )
        if created.status_code not in {200, 201}:
            raise StorageError(f"Supabase private bucket creation failed ({created.status_code}): {self._error_message(created)}")

    def _upload_pdf_with_limit(self, object_key: str, data: bytes, maximum: int) -> StoredPdf:
        key = self._validate_object_key(object_key)
        if len(data) > maximum:
            raise StorageError("PDF exceeds the configured upload limit.")
        encoded_key = quote(key, safe="/")
        response = self._request(
            "POST",
            f"/storage/v1/object/{quote(self.bucket, safe='')}/{encoded_key}",
            files={"file": (PurePosixPath(key).name, data, "application/pdf")},
        )
        if response.status_code not in {200, 201}:
            if response.status_code == 409:
                raise StorageError("A PDF already exists at the generated object key.")
            raise StorageError(f"Supabase PDF upload failed ({response.status_code}): {self._error_message(response)}")
        return StoredPdf(
            object_key=key,
            bucket=self.bucket,
            size_bytes=len(data),
            sha256=sha256(data).hexdigest(),
            etag=response.headers.get("etag"),
        )

    def upload_pdf(self, object_key: str, data: bytes) -> StoredPdf:
        """Compatibility/source upload; new callers should use the typed method."""

        source_limit = int(getattr(self.settings, "max_source_pdf_bytes", self.settings.max_upload_bytes))
        return self._upload_pdf_with_limit(object_key, data, source_limit)

    def upload_generated_pdf(self, object_key: str, data: bytes) -> StoredPdf:
        maximum = int(getattr(self.settings, "max_generated_pdf_bytes", self.settings.max_upload_bytes))
        return self._upload_pdf_with_limit(object_key, data, maximum)

    def upload_asset(self, object_key: str, data: bytes, content_type: str) -> StoredPdf:
        key = self._validate_object_key(object_key)
        if content_type not in self.ASSET_MIME_TYPES or content_type == "application/pdf":
            raise StorageError("Asset content type is not allowed.")
        if len(data) > self.settings.max_asset_bytes:
            raise StorageError("Asset exceeds the configured upload limit.")
        encoded_key = quote(key, safe="/")
        response = self._request(
            "POST",
            f"/storage/v1/object/{quote(self.bucket, safe='')}/{encoded_key}",
            files={"file": (PurePosixPath(key).name, data, content_type)},
        )
        if response.status_code not in {200, 201}:
            if response.status_code == 409:
                raise StorageError("An asset already exists at the generated object key.")
            raise StorageError(f"Supabase asset upload failed ({response.status_code}): {self._error_message(response)}")
        return StoredPdf(
            object_key=key,
            bucket=self.bucket,
            size_bytes=len(data),
            sha256=sha256(data).hexdigest(),
            etag=response.headers.get("etag"),
        )

    def download_bytes(self, object_key: str) -> bytes:
        key = self._validate_object_key(object_key)
        response = self._request(
            "GET",
            f"/storage/v1/object/{quote(self.bucket, safe='')}/{quote(key, safe='/')}",
        )
        if self._not_found(response):
            raise StorageNotFound("Object not found.")
        if response.status_code != 200:
            raise StorageError(f"Supabase download failed ({response.status_code}): {self._error_message(response)}")
        return response.content

    def delete_pdf(self, object_key: str) -> None:
        key = self._validate_object_key(object_key)
        response = self._request(
            "DELETE",
            f"/storage/v1/object/{quote(self.bucket, safe='')}",
            json={"prefixes": [key]},
        )
        if response.status_code not in {200, 204, 404}:
            raise StorageError(f"Supabase PDF deletion failed ({response.status_code}): {self._error_message(response)}")

    def check(self) -> tuple[bool, str]:
        try:
            self.ensure_bucket()
            return True, f"Private bucket '{self.bucket}' is ready."
        except StorageError as exc:
            return False, str(exc)

    @staticmethod
    def _validate_object_key(object_key: str) -> str:
        normalized = str(PurePosixPath(object_key.replace("\\", "/")))
        if normalized in {"", "."} or normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
            raise StorageError("Invalid object key.")
        if any(part in {"", "."} for part in PurePosixPath(normalized).parts):
            raise StorageError("Invalid object key.")
        return normalized
