from __future__ import annotations

from pydantic import BaseModel, Field


class NumericAuditRequest(BaseModel):
    artifact_id: str
    min_duplicate_length: int = Field(default=3, ge=2, le=20)
    min_last_digit_sample: int = Field(default=10, ge=5, le=500)
    min_fixed_relationship_sample: int = Field(default=6, ge=4, le=500)
    max_fixed_relationship_cv: float = Field(default=0.001, ge=0.0, le=0.05)
    create_review_tasks: bool = True
    priority: int = Field(default=7, ge=0, le=10)


class NumericAuditResponse(BaseModel):
    artifact_id: str
    paper_id: str
    analyzed_rows: int
    analyzed_numeric_columns: int
    signal_count: int
    created_review_tasks: int
    signals: list[dict]
    conclusion_boundary: str


class ImageAuditRequest(BaseModel):
    artifact_id: str
    compare_artifact_ids: list[str] | None = None
    max_hamming_distance: int = Field(default=10, ge=0, le=64)
    enable_patch_similarity: bool = True
    max_patch_hamming_distance: int = Field(default=6, ge=0, le=64)
    patch_grid_size: int = Field(default=4, ge=2, le=8)
    min_patch_stddev: float = Field(default=8.0, ge=0.0, le=128.0)
    enable_shift_correlation: bool = True
    min_shift_correlation: float = Field(default=0.86, ge=0.5, le=0.99)
    max_shift_fraction: float = Field(default=0.18, ge=0.0, le=0.4)
    correlation_size: int = Field(default=64, ge=32, le=160)
    create_review_tasks: bool = True
    priority: int = Field(default=8, ge=0, le=10)


class MetadataAuditRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution|group)$")
    entity_id: str
    min_cluster_size: int = Field(default=5, ge=2, le=100)
    min_signal_rate_audited_count: int = Field(default=2, ge=1, le=100)
    signal_rate_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    public_event_rate_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    create_review_tasks: bool = True
    priority: int = Field(default=6, ge=0, le=10)


class EntityAuditCycleRequest(BaseModel):
    entity_type: str = Field(pattern="^(author|institution|group)$")
    entity_id: str
    discover_artifacts: bool = True
    inspect_landing_pages: bool = False
    queue_review_tasks: bool = True
    run_metadata_audit: bool = True
    min_cluster_size: int = Field(default=5, ge=2, le=100)
    min_signal_rate_audited_count: int = Field(default=2, ge=1, le=100)
    signal_rate_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    public_event_rate_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    priority: int = Field(default=6, ge=0, le=10)


class EntityAuditCycleBatchRequest(BaseModel):
    items: list[EntityAuditCycleRequest] = Field(min_length=1, max_length=100)
