from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from gengscope_api.config import get_settings
from gengscope_api.services.doi import normalize_doi


class CrossrefClient:
    base_url = "https://api.crossref.org"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        settings = get_settings()
        normalized = normalize_doi(doi)
        url = f"{self.base_url}/works/{quote(normalized, safe='')}"
        if self._client is not None:
            response = self._client.get(url, timeout=settings.http_timeout_seconds)
        else:
            response = httpx.get(url, timeout=settings.http_timeout_seconds)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("message")
