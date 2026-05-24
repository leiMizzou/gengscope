from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ArtifactRegisterRequest(BaseModel):
    paper_id: str | None = None
    doi: str | None = None
    artifact_type: str
    source_url: str | HttpUrl
    storage_uri: str | None = None
    content_type: str | None = None
    filename: str | None = None
    checksum_sha256: str | None = None
    license_status: str = "unknown"


class ArtifactDiscoverRequest(BaseModel):
    paper_id: str | None = None
    doi: str | None = None
    inspect_landing_pages: bool = False
    max_landing_pages: int = Field(default=3, ge=0, le=20)
    max_discovered_links: int = Field(default=30, ge=0, le=200)


class ArtifactFetchRequest(BaseModel):
    artifact_id: str | None = None
    paper_id: str | None = None
    doi: str | None = None
    artifact_type: str | None = None
    source_url: str | HttpUrl | None = None
    filename: str | None = None
    license_status: str = "open_or_linked"
    max_bytes: int | None = Field(default=None, ge=1, le=500 * 1024 * 1024)


class PdfImageExtractRequest(BaseModel):
    artifact_id: str
    max_pages: int = Field(default=8, ge=1, le=200)
    max_images: int = Field(default=30, ge=1, le=500)
    min_width: int = Field(default=80, ge=1, le=4000)
    min_height: int = Field(default=80, ge=1, le=4000)


class ArtifactResponse(BaseModel):
    id: str
    paper_id: str
    artifact_type: str
    source_url: str
    storage_uri: str | None
    content_type: str | None
    filename: str | None
    checksum_sha256: str | None
    license_status: str


class ArtifactListResponse(BaseModel):
    paper_id: str
    material_status: str
    is_oa_pdf_available: bool
    is_source_data_available: bool
    items: list[ArtifactResponse]


class ArtifactUploadResponse(BaseModel):
    artifact: ArtifactResponse
    material_status: str
