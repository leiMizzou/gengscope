from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from gengscope_api.db.models import IntegrityEvent, Paper
from gengscope_api.db.session import get_db
from gengscope_api.services.doi import normalize_doi
from gengscope_api.services.risk_card import risk_card_for_doi, risk_card_for_paper

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("")
def search_papers(
    query: str | None = None,
    doi: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(Paper).options(selectinload(Paper.events), selectinload(Paper.algorithmic_signals))
    if doi:
        normalized = normalize_doi(doi)
        statement = statement.where(func.lower(Paper.doi) == normalized)
    elif query:
        like = f"%{query.lower()}%"
        statement = statement.where(or_(func.lower(Paper.title).like(like), func.lower(Paper.doi).like(like)))
    total = len(db.scalars(statement).all())
    papers = db.scalars(statement.offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "id": paper.id,
                "doi": paper.doi,
                "title": paper.title,
                "journal_name": paper.journal_name,
                "publication_year": paper.publication_year,
                "risk_status": risk_card_for_paper(paper),
            }
            for paper in papers
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{doi:path}/risk-card")
def paper_risk_card(doi: str, db: Session = Depends(get_db)) -> dict:
    try:
        return risk_card_for_doi(db, doi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{doi:path}")
def paper_detail(doi: str, db: Session = Depends(get_db)) -> dict:
    try:
        normalized = normalize_doi(doi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    paper = db.scalar(
        select(Paper)
        .where(func.lower(Paper.doi) == normalized)
        .options(
            selectinload(Paper.authorships),
            selectinload(Paper.events).selectinload(IntegrityEvent.evidence_pointers),
            selectinload(Paper.algorithmic_signals),
            selectinload(Paper.source_artifacts),
        )
    )
    if paper is None:
        raise HTTPException(status_code=404, detail=f"No paper found for DOI {normalized}")
    return {
        "paper": {
            "id": paper.id,
            "doi": paper.doi,
            "title": paper.title,
            "abstract": paper.abstract,
            "journal_name": paper.journal_name,
            "publisher": paper.publisher,
            "publication_year": paper.publication_year,
            "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
            "landing_page_url": paper.landing_page_url,
            "open_access_url": paper.open_access_url,
            "material_status": paper.material_status,
            "is_oa_pdf_available": paper.is_oa_pdf_available,
            "is_source_data_available": paper.is_source_data_available,
            "audit_status": paper.audit_status,
        },
        "authorships": [
            {
                "id": authorship.id,
                "author_id": authorship.author_id,
                "institution_id": authorship.institution_id,
                "author_name_raw": authorship.author_name_raw,
                "author_position": authorship.author_position,
                "author_role": authorship.author_role,
                "is_corresponding": authorship.is_corresponding,
                "affiliation_raw": authorship.affiliation_raw,
                "institution_display_name": authorship.institution.display_name if authorship.institution else None,
            }
            for authorship in paper.authorships
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "status_level": event.status_level,
                "source_type": event.source_type,
                "source_name": event.source_name,
                "source_url": event.source_url,
                "event_date": event.event_date.isoformat() if event.event_date else None,
                "claim_summary": event.claim_summary,
                "verification_status": event.verification_status,
            }
            for event in paper.events
        ],
        "algorithmic_signals": [
            {
                "id": signal.id,
                "signal_type": signal.signal_type,
                "severity": signal.severity,
                "status": signal.status,
                "summary": signal.summary,
                "metrics": signal.metrics_json,
            }
            for signal in paper.algorithmic_signals
        ],
        "artifacts": [
            {
                "id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "source_url": artifact.source_url,
                "checksum_sha256": artifact.checksum_sha256,
                "storage_uri": artifact.storage_uri,
                "content_type": artifact.content_type,
                "filename": artifact.filename,
                "license_status": artifact.license_status,
            }
            for artifact in paper.source_artifacts
        ],
        "risk_status": risk_card_for_paper(paper),
    }
