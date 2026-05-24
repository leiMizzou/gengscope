from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    doi: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    journal_name: Mapped[str | None] = mapped_column(String)
    publisher: Mapped[str | None] = mapped_column(String)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    publication_date: Mapped[str | None] = mapped_column(Date)
    type: Mapped[str | None] = mapped_column(String)
    openalex_id: Mapped[str | None] = mapped_column(String, unique=True)
    crossref_member_id: Mapped[str | None] = mapped_column(String)
    pmid: Mapped[str | None] = mapped_column(String)
    pmcid: Mapped[str | None] = mapped_column(String)
    landing_page_url: Mapped[str | None] = mapped_column(String)
    open_access_url: Mapped[str | None] = mapped_column(String)
    is_retracted: Mapped[bool] = mapped_column(Boolean, default=False)
    material_status: Mapped[str] = mapped_column(String, default="metadata_only")
    is_oa_pdf_available: Mapped[bool] = mapped_column(Boolean, default=False)
    is_source_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    audit_status: Mapped[str] = mapped_column(String, default="not_audited")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    authorships: Mapped[list[Authorship]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    events: Mapped[list[IntegrityEvent]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    source_artifacts: Mapped[list[SourceArtifact]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    algorithmic_signals: Mapped[list[AlgorithmicSignal]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    display_name: Mapped[str] = mapped_column(String)
    openalex_id: Mapped[str | None] = mapped_column(String)
    orcid: Mapped[str | None] = mapped_column(String)
    name_variants: Mapped[list[str] | None] = mapped_column(JSON)
    disambiguation_status: Mapped[str] = mapped_column(String, default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    authorships: Mapped[list[Authorship]] = relationship(back_populates="author")


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    display_name: Mapped[str] = mapped_column(String)
    english_name: Mapped[str | None] = mapped_column(String)
    chinese_name: Mapped[str | None] = mapped_column(String)
    ror_id: Mapped[str | None] = mapped_column(String)
    openalex_id: Mapped[str | None] = mapped_column(String)
    country_code: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    aliases: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    authorships: Mapped[list[Authorship]] = relationship(back_populates="institution")


class EntityGroup(Base):
    __tablename__ = "entity_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    display_name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    memberships: Mapped[list[EntityGroupMember]] = relationship(back_populates="group", cascade="all, delete-orphan")


class EntityGroupMember(Base):
    __tablename__ = "entity_group_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    group_id: Mapped[str] = mapped_column(ForeignKey("entity_groups.id", ondelete="CASCADE"))
    member_entity_type: Mapped[str] = mapped_column(String)
    member_entity_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    group: Mapped[EntityGroup] = relationship(back_populates="memberships")


class EntitySearchCache(Base):
    __tablename__ = "entity_search_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    entity_type: Mapped[str] = mapped_column(String)
    query_text: Mapped[str] = mapped_column(String)
    query_normalized: Mapped[str] = mapped_column(String)
    requested_limit: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[list[dict]] = mapped_column(JSON)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    source_name: Mapped[str] = mapped_column(String, default="openalex")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Authorship(Base):
    __tablename__ = "authorships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    author_id: Mapped[str | None] = mapped_column(ForeignKey("authors.id"))
    author_name_raw: Mapped[str] = mapped_column(String)
    author_position: Mapped[int | None] = mapped_column(Integer)
    author_role: Mapped[str | None] = mapped_column(String)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"))
    affiliation_raw: Mapped[str | None] = mapped_column(Text)
    affiliation_match_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="authorships")
    author: Mapped[Author | None] = relationship(back_populates="authorships")
    institution: Mapped[Institution | None] = relationship(back_populates="authorships")


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    artifact_type: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    storage_uri: Mapped[str | None] = mapped_column(String)
    content_type: Mapped[str | None] = mapped_column(String)
    filename: Mapped[str | None] = mapped_column(String)
    checksum_sha256: Mapped[str | None] = mapped_column(String)
    license_status: Mapped[str] = mapped_column(String, default="unknown")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="source_artifacts")
    evidence_pointers: Mapped[list[EvidencePointer]] = relationship(back_populates="artifact")


class IntegrityEvent(Base):
    __tablename__ = "integrity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String)
    status_level: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    source_name: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    event_date: Mapped[str | None] = mapped_column(Date)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claim_summary: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String, default="unverified")
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    paper: Mapped[Paper | None] = relationship(back_populates="events")
    evidence_pointers: Mapped[list[EvidencePointer]] = relationship(back_populates="event", cascade="all, delete-orphan")


class AlgorithmicSignal(Base):
    __tablename__ = "algorithmic_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("source_artifacts.id", ondelete="SET NULL"))
    signal_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)
    analyzer_name: Mapped[str] = mapped_column(String)
    analyzer_version: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    metrics_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    paper: Mapped[Paper] = relationship(back_populates="algorithmic_signals")
    artifact: Mapped[SourceArtifact | None] = relationship()
    evidence_pointers: Mapped[list[EvidencePointer]] = relationship(back_populates="signal", cascade="all, delete-orphan")


class EvidencePointer(Base):
    __tablename__ = "evidence_pointers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str | None] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("integrity_events.id", ondelete="CASCADE"))
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("algorithmic_signals.id", ondelete="CASCADE"))
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("source_artifacts.id", ondelete="SET NULL"))
    figure_label: Mapped[str | None] = mapped_column(String)
    table_label: Mapped[str | None] = mapped_column(String)
    panel_label: Mapped[str | None] = mapped_column(String)
    column_name: Mapped[str | None] = mapped_column(String)
    row_label: Mapped[str | None] = mapped_column(String)
    page_number: Mapped[int | None] = mapped_column(Integer)
    bbox_json: Mapped[dict | None] = mapped_column(JSON)
    evidence_url: Mapped[str | None] = mapped_column(String)
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    event: Mapped[IntegrityEvent | None] = relationship(back_populates="evidence_pointers")
    signal: Mapped[AlgorithmicSignal | None] = relationship(back_populates="evidence_pointers")
    artifact: Mapped[SourceArtifact | None] = relationship(back_populates="evidence_pointers")


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("algorithmic_signals.id", ondelete="CASCADE"))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("integrity_events.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="open")
    assigned_to: Mapped[str | None] = mapped_column(String)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    paper: Mapped[Paper] = relationship()
    signal: Mapped[AlgorithmicSignal | None] = relationship()
    event: Mapped[IntegrityEvent | None] = relationship()


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_name: Mapped[str] = mapped_column(String)
    source_record_id: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    raw_payload_hash: Mapped[str] = mapped_column(String)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str | None] = mapped_column(String)
    target_type: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String(36))
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    paper_id: Mapped[str | None] = mapped_column(String(36))
    artifact_id: Mapped[str | None] = mapped_column(String(36))
    signal_id: Mapped[str | None] = mapped_column(String(36))
    task_id: Mapped[str | None] = mapped_column(String(36))
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String(36))
    entity_display_name: Mapped[str] = mapped_column(String)
    report_format: Mapped[str] = mapped_column(String)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String)
    actor: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    actor: Mapped[str | None] = mapped_column(String)
    payload_json: Mapped[dict] = mapped_column(JSON)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobSchedule(Base):
    __tablename__ = "job_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String)
    job_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    actor: Mapped[str | None] = mapped_column(String)
    payload_json: Mapped[dict] = mapped_column(JSON)
    interval_seconds: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


Index("idx_papers_doi_lower", Paper.doi)
Index("idx_papers_year", Paper.publication_year)
Index("idx_authorships_paper", Authorship.paper_id)
Index("idx_authorships_author", Authorship.author_id)
Index("idx_authorships_institution", Authorship.institution_id)
Index("idx_entity_group_members_group", EntityGroupMember.group_id)
Index("idx_entity_group_members_member", EntityGroupMember.member_entity_type, EntityGroupMember.member_entity_id)
Index("idx_entity_search_cache_lookup", EntitySearchCache.entity_type, EntitySearchCache.query_normalized, EntitySearchCache.requested_limit, unique=True)
Index("idx_entity_search_cache_expires_at", EntitySearchCache.expires_at)
Index("idx_events_paper", IntegrityEvent.paper_id)
Index("idx_events_status_level", IntegrityEvent.status_level)
Index("idx_signals_paper", AlgorithmicSignal.paper_id)
Index("idx_signals_status", AlgorithmicSignal.status)
Index("idx_audit_logs_action", AuditLog.action)
Index("idx_audit_logs_target", AuditLog.target_type, AuditLog.target_id)
Index("idx_audit_logs_entity", AuditLog.entity_type, AuditLog.entity_id)
Index("idx_audit_logs_created_at", AuditLog.created_at)
Index("idx_report_snapshots_entity", ReportSnapshot.entity_type, ReportSnapshot.entity_id)
Index("idx_report_snapshots_created_at", ReportSnapshot.created_at)
Index("idx_report_snapshots_hash", ReportSnapshot.content_sha256)
Index("idx_job_runs_status", JobRun.status)
Index("idx_job_runs_type_status", JobRun.job_type, JobRun.status)
Index("idx_job_runs_queued_at", JobRun.queued_at)
Index("idx_job_schedules_status_next_run", JobSchedule.status, JobSchedule.next_run_at)
Index("idx_job_schedules_type_status", JobSchedule.job_type, JobSchedule.status)
