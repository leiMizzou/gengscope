from __future__ import annotations

from pydantic import BaseModel, Field


class EntityReportArchiveRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution|group)$")
    entity_id: str
    formats: list[str] = Field(default_factory=lambda: ["json", "markdown"], min_length=1, max_length=2)


class ReportArchivePruneRequest(BaseModel):
    entity_type: str | None = Field(default=None, pattern="^(author|institution|group)$")
    entity_id: str | None = None
    format: str = Field(default="all", pattern="^(all|json|markdown)$")
    keep_latest: int | None = Field(default=20, ge=0, le=1000)
    older_than_days: int | None = Field(default=180, ge=1, le=36500)
    dry_run: bool = True
