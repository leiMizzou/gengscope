from __future__ import annotations

from pydantic import BaseModel, Field


class EntitySearchResult(BaseModel):
    entity_type: str
    openalex_id: str | None
    display_name: str
    works_count: int | None = None
    country_code: str | None = None
    hint: str | None = None


class EntityCorpusRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution)$")
    query: str | None = None
    openalex_id: str | None = None
    display_name: str | None = None
    limit: int = Field(default=25, ge=1, le=200)
    year_from: int | None = None
    year_to: int | None = None


class EntityBatchCorpusRequest(BaseModel):
    items: list[EntityCorpusRequest] = Field(min_length=1, max_length=100)
    continue_on_error: bool = True


class EntityGroupMemberRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution)$")
    entity_id: str
    label: str | None = Field(default=None, max_length=160)


class EntityGroupCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    members: list[EntityGroupMemberRequest] = Field(min_length=1, max_length=100)


class EntityGroupCorpusRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    members: list[EntityCorpusRequest] = Field(min_length=1, max_length=100)
    continue_on_error: bool = True


class EntityProfileRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution|group)$")
    entity_id: str


class EntityAuditQueueRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution|group)$")
    entity_id: str
    priority: int = Field(default=5, ge=0, le=10)
