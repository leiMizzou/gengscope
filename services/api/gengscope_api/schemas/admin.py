from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class ImportDoiRequest(BaseModel):
    doi: str
    sources: list[str] = Field(default_factory=lambda: ["openalex", "crossref"])


class ManualEventRequest(BaseModel):
    doi: str
    event_type: str
    status_level: str
    source_type: str
    source_name: str | None = None
    source_url: HttpUrl
    event_date: date | None = None
    claim_summary: str = Field(min_length=1, max_length=800)
    verification_status: str = "unverified"
    created_by: str | None = None


class ImportDoiResponse(BaseModel):
    id: str
    doi: str
    title: str
    authorship_count: int
    source_record_count: int


class ManualEventResponse(BaseModel):
    id: str
    doi: str
    event_type: str
    status_level: str
    source_type: str
    source_url: str
    claim_summary: str
    verification_status: str
