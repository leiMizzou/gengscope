from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from gengscope_api.api.deps import get_source_clients
from gengscope_api.db.models import Authorship, SourceRecord
from gengscope_api.db.session import get_db
from gengscope_api.schemas.admin import ImportDoiRequest, ImportDoiResponse, ManualEventRequest, ManualEventResponse
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.events import create_manual_event
from gengscope_api.services.import_paper import SourceClients, import_doi

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/import/doi", response_model=ImportDoiResponse)
def import_doi_endpoint(
    request: ImportDoiRequest,
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> ImportDoiResponse:
    try:
        paper = import_doi(db, request.doi, request.sources, clients)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Metadata import failed: {exc}") from exc

    authorship_count = len(db.scalars(select(Authorship).where(Authorship.paper_id == paper.id)).all())
    source_record_count = len(db.scalars(select(SourceRecord).where(SourceRecord.entity_id == paper.id)).all())
    record_audit_log(
        db,
        action="paper_doi_imported",
        actor=actor,
        target_type="paper",
        target_id=paper.id,
        paper_id=paper.id,
        summary=f"Imported DOI {paper.doi}.",
        metadata={"doi": paper.doi, "sources": request.sources, "authorship_count": authorship_count, "source_record_count": source_record_count},
    )
    return ImportDoiResponse(
        id=paper.id,
        doi=paper.doi or "",
        title=paper.title,
        authorship_count=authorship_count,
        source_record_count=source_record_count,
    )


@router.post("/events", response_model=ManualEventResponse)
def create_event_endpoint(
    request: ManualEventRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> ManualEventResponse:
    try:
        event = create_manual_event(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit_log(
        db,
        action="integrity_event_created",
        actor=actor or request.created_by,
        target_type="integrity_event",
        target_id=event.id,
        paper_id=event.paper_id,
        summary=f"Created {event.status_level} event from {event.source_type}.",
        metadata={
            "event_type": event.event_type,
            "status_level": event.status_level,
            "source_type": event.source_type,
            "source_url": event.source_url,
            "verification_status": event.verification_status,
        },
    )
    return ManualEventResponse(
        id=event.id,
        doi=event.paper.doi if event.paper else request.doi,
        event_type=event.event_type,
        status_level=event.status_level,
        source_type=event.source_type,
        source_url=event.source_url,
        claim_summary=event.claim_summary,
        verification_status=event.verification_status,
    )
