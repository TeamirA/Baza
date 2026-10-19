"""Where uploaded media (product photos) is stored.

Vercel's filesystem is read-only and short-lived, so production stores files in
Vercel Blob. Locally (no BLOB_READ_WRITE_TOKEN) files go to MEDIA_ROOT and are
served by Django in DEBUG. Both stores return a public URL from save().
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class MediaStoreError(Exception):
    """Saving or deleting a file failed; the message is safe to show to staff."""


class MediaStore(ABC):
    @abstractmethod
    def save(self, path, data, content_type):
        """Stores bytes under a path like "products/mug/abc-800.webp"; returns its public URL."""

    @abstractmethod
    def delete(self, urls):
        """Best-effort removal of previously saved files, by URL."""


class LocalMediaStore(MediaStore):
    def __init__(self, root=None, base_url=None):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.base_url = base_url or settings.MEDIA_URL

    def save(self, path, data, content_type):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{self.base_url}{path}"

    def delete(self, urls):
        for url in urls:
            if url.startswith(self.base_url):
                (self.root / url[len(self.base_url):]).unlink(missing_ok=True)


class VercelBlobStore(MediaStore):
    """Minimal client for the Vercel Blob HTTP API (public stores), matching the
    official SDKs: PUT /?pathname=... to upload, POST /delete to remove."""

    API_URL = "https://vercel.com/api/blob"
    API_VERSION = "11"
    ONE_YEAR = 60 * 60 * 24 * 365

    def __init__(self, token, session=None):
        import requests  # only needed in production; keeps local startup light

        self.token = token
        self.http = session or requests.Session()
        self.RequestException = requests.RequestException

    def _headers(self, extra=None):
        return {"authorization": f"Bearer {self.token}", "x-api-version": self.API_VERSION, **(extra or {})}

    def save(self, path, data, content_type):
        try:
            response = self.http.put(
                self.API_URL,
                params={"pathname": path},
                data=data,
                headers=self._headers({
                    "x-content-type": content_type,
                    # File names already contain a random id; images never change once
                    # uploaded, so browsers and the CDN can cache them for a year.
                    "x-add-random-suffix": "0",
                    "x-cache-control-max-age": str(self.ONE_YEAR),
                }),
                timeout=30,
            )
        except self.RequestException as e:
            raise MediaStoreError(f"Couldn't reach Vercel Blob: {e}") from e
        if response.status_code >= 400:
            raise MediaStoreError(self._error_message(response))
        return response.json()["url"]

    def delete(self, urls):
        urls = [u for u in urls if u]
        if not urls:
            return
        try:
            response = self.http.post(
                f"{self.API_URL}/delete",
                json={"urls": urls},
                headers=self._headers({"content-type": "application/json"}),
                timeout=15,
            )
            if response.status_code >= 400:
                logger.warning("Blob delete failed: %s", self._error_message(response))
        except self.RequestException:
            logger.exception("Blob delete failed")

    @staticmethod
    def _error_message(response):
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = response.text[:200]
        if response.status_code in (401, 403):
            return f"Vercel Blob refused the upload ({response.status_code}). Check BLOB_READ_WRITE_TOKEN and that the store is public. {detail}".strip()
        return f"Vercel Blob error {response.status_code}: {detail}".strip()


def get_media_store():
    token = settings.BLOB_READ_WRITE_TOKEN
    return VercelBlobStore(token) if token else LocalMediaStore()
