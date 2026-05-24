from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gengscope_api.db.models import IntegrityEvent, Paper
from gengscope_api.schemas.admin import ManualEventRequest
from gengscope_api.services.doi import normalize_doi


OFFICIAL_STATUS_LEVELS = {
    "official_retraction",
    "official_correction",
    "official_expression_of_concern",
}
OFFICIAL_SOURCE_TYPES = {"publisher", "institution", "regulator", "court", "official"}
INSTITUTION_STATUS_LEVELS = {"institution_investigation", "institution_conclusion"}
PUBLISHER_STATUS_LEVELS = {"publisher_notice"}
ALLOWED_VERIFICATION_STATUSES = {
    "unverified",
    "source_verified",
    "official_confirmed",
    "disputed",
    "withdrawn",
    "superseded",
}


def create_manual_event(db: Session, request: ManualEventRequest) -> IntegrityEvent:
    doi = normalize_doi(request.doi)
    _validate_event_request(request)
    event_type = request.event_type.strip()
    status_level = request.status_level.strip()
    source_type = request.source_type.strip().lower()
    verification_status = request.verification_status.strip()
    paper = db.scalar(select(Paper).where(func.lower(Paper.doi) == doi))
    if paper is None:
        raise LookupError(f"No paper found for DOI {doi}; import metadata first")

    event = IntegrityEvent(
        paper=paper,
        event_type=event_type,
        status_level=status_level,
        source_type=source_type,
        source_name=request.source_name,
        source_url=str(request.source_url),
        event_date=request.event_date,
        claim_summary=request.claim_summary.strip(),
        verification_status=verification_status,
        created_by=request.created_by,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _validate_event_request(request: ManualEventRequest) -> None:
    source_type = request.source_type.strip().lower()
    status_level = request.status_level.strip()
    summary = request.claim_summary.strip()
    if not summary:
        raise ValueError("claim_summary is required")
    if len(summary) > 800:
        raise ValueError("claim_summary must be 800 characters or fewer")
    verification_status = request.verification_status.strip()
    if verification_status not in ALLOWED_VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported verification_status: {verification_status}")
    if status_level in OFFICIAL_STATUS_LEVELS and source_type not in OFFICIAL_SOURCE_TYPES:
        raise ValueError("Unofficial sources cannot set official status levels")
    if status_level in INSTITUTION_STATUS_LEVELS and source_type != "institution":
        raise ValueError("Institution status levels require source_type='institution'")
    if status_level in PUBLISHER_STATUS_LEVELS and source_type != "publisher":
        raise ValueError("Publisher notices require source_type='publisher'")
