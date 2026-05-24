from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from gengscope_api.schemas.audits import EntityAuditCycleRequest


class EntityAuditScheduleRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    interval_seconds: int = Field(ge=60, le=366 * 24 * 60 * 60)
    start_at: datetime | None = None
    run_immediately: bool = False
    max_attempts: int = Field(default=1, ge=1, le=10)
    job: EntityAuditCycleRequest


class JobScheduleStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|paused|cancelled)$")
