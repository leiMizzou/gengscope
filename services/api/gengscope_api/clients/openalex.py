from __future__ import annotations

from typing import Any

import httpx

from gengscope_api.config import get_settings
from gengscope_api.services.doi import doi_url, normalize_doi


class OpenAlexClient:
    base_url = "https://api.openalex.org"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        settings = get_settings()
        normalized = normalize_doi(doi)
        params: dict[str, str] = {}
        if settings.openalex_email:
            params["mailto"] = settings.openalex_email
        url = f"{self.base_url}/works/{doi_url(normalized)}"
        if self._client is not None:
            response = self._client.get(url, params=params, timeout=settings.http_timeout_seconds)
        else:
            response = httpx.get(url, params=params, timeout=settings.http_timeout_seconds)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def search_authors(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._get_list("/authors", {"search": query, "per-page": str(limit)})

    def search_institutions(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._get_list("/institutions", {"search": query, "per-page": str(limit)})

    def fetch_works_by_author(
        self,
        author_openalex_id: str,
        limit: int = 25,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = [f"authorships.author.id:{author_openalex_id}"]
        filters.extend(_year_filters(year_from, year_to))
        return self._get_list(
            "/works",
            {
                "filter": ",".join(filters),
                "sort": "publication_date:desc",
                "per-page": str(limit),
            },
        )

    def fetch_works_by_institution(
        self,
        institution_openalex_id: str,
        limit: int = 25,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = [f"authorships.institutions.id:{institution_openalex_id}"]
        filters.extend(_year_filters(year_from, year_to))
        return self._get_list(
            "/works",
            {
                "filter": ",".join(filters),
                "sort": "publication_date:desc",
                "per-page": str(limit),
            },
        )

    def _get_list(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        settings = get_settings()
        request_params = dict(params)
        if settings.openalex_email:
            request_params["mailto"] = settings.openalex_email
        url = f"{self.base_url}{path}"
        if self._client is not None:
            response = self._client.get(url, params=request_params, timeout=settings.http_timeout_seconds)
        else:
            response = httpx.get(url, params=request_params, timeout=settings.http_timeout_seconds)
        response.raise_for_status()
        return response.json().get("results", [])


def _year_filters(year_from: int | None, year_to: int | None) -> list[str]:
    filters: list[str] = []
    if year_from is not None:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to is not None:
        filters.append(f"to_publication_date:{year_to}-12-31")
    return filters
