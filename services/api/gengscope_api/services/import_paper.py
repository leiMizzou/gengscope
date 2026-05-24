from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from gengscope_api.clients.crossref import CrossrefClient
from gengscope_api.clients.openalex import OpenAlexClient
from gengscope_api.db.models import Author, Authorship, Institution, Paper, SourceArtifact, SourceRecord
from gengscope_api.services.doi import doi_url, normalize_doi
from gengscope_api.services.provenance import payload_hash


@dataclass
class SourceClients:
    openalex: OpenAlexClient
    crossref: CrossrefClient


def default_source_clients() -> SourceClients:
    return SourceClients(openalex=OpenAlexClient(), crossref=CrossrefClient())


def import_doi(
    db: Session,
    doi: str,
    sources: list[str] | None = None,
    clients: SourceClients | None = None,
) -> Paper:
    normalized = normalize_doi(doi)
    requested_sources = sources or ["openalex", "crossref"]
    clients = clients or default_source_clients()

    openalex_payload = None
    crossref_payload = None
    if "openalex" in requested_sources:
        openalex_payload = clients.openalex.fetch_work_by_doi(normalized)
    if "crossref" in requested_sources:
        crossref_payload = clients.crossref.fetch_work_by_doi(normalized)

    if not openalex_payload and not crossref_payload:
        raise LookupError(f"No metadata found for DOI {normalized}")

    paper = _upsert_paper(db, normalized, openalex_payload, crossref_payload)
    db.flush()

    if openalex_payload:
        _sync_openalex_authorships(db, paper, openalex_payload)
        _sync_openalex_artifacts(db, paper, openalex_payload)
        _save_source_record(db, "openalex", "paper", paper.id, openalex_payload.get("id"), openalex_payload.get("id"), openalex_payload)
    elif crossref_payload:
        _sync_crossref_authorships(db, paper, crossref_payload)

    if crossref_payload:
        _save_source_record(
            db,
            "crossref",
            "paper",
            paper.id,
            crossref_payload.get("DOI"),
            crossref_payload.get("URL"),
            crossref_payload,
        )

    db.commit()
    db.refresh(paper)
    return paper


def import_openalex_work(db: Session, payload: dict[str, Any], commit: bool = True) -> Paper:
    doi = _doi_from_openalex(payload)
    paper = _upsert_paper(db, doi, payload, None)
    db.flush()
    _sync_openalex_authorships(db, paper, payload)
    _sync_openalex_artifacts(db, paper, payload)
    _save_source_record(db, "openalex", "paper", paper.id, payload.get("id"), payload.get("id"), payload)
    if commit:
        db.commit()
        db.refresh(paper)
    return paper


def _upsert_paper(
    db: Session,
    doi: str | None,
    openalex_payload: dict[str, Any] | None,
    crossref_payload: dict[str, Any] | None,
) -> Paper:
    paper = db.scalar(select(Paper).where(func.lower(Paper.doi) == doi)) if doi else None
    if paper is None and openalex_payload and openalex_payload.get("id"):
        paper = db.scalar(select(Paper).where(Paper.openalex_id == openalex_payload.get("id")))
    if paper is None:
        fallback_title = doi or ((openalex_payload or {}).get("id")) or "Untitled paper"
        paper = Paper(doi=doi, title=_title(openalex_payload, crossref_payload) or fallback_title)
        db.add(paper)

    paper.doi = doi
    paper.title = _title(openalex_payload, crossref_payload) or paper.title
    paper.abstract = _abstract(openalex_payload)
    paper.journal_name = _journal(openalex_payload, crossref_payload)
    paper.publisher = _publisher(openalex_payload, crossref_payload)
    paper.publication_year = _publication_year(openalex_payload, crossref_payload)
    paper.publication_date = _publication_date(openalex_payload, crossref_payload)
    paper.type = (openalex_payload or {}).get("type") or (crossref_payload or {}).get("type")
    paper.openalex_id = (openalex_payload or {}).get("id") or paper.openalex_id
    paper.crossref_member_id = str((crossref_payload or {}).get("member")) if (crossref_payload or {}).get("member") else paper.crossref_member_id
    ids = (openalex_payload or {}).get("ids") or {}
    paper.pmid = ids.get("pmid") or (crossref_payload or {}).get("PMID") or paper.pmid
    paper.pmcid = ids.get("pmcid") or paper.pmcid
    paper.landing_page_url = _landing_page(openalex_payload, crossref_payload, doi)
    paper.open_access_url = _open_access_url(openalex_payload) or paper.open_access_url
    paper.is_retracted = bool((openalex_payload or {}).get("is_retracted") or (crossref_payload or {}).get("relation", {}).get("is-retracted-by"))
    paper.is_oa_pdf_available = bool(paper.open_access_url)
    paper.material_status = _material_status(openalex_payload, paper)
    return paper


def _doi_from_openalex(payload: dict[str, Any]) -> str | None:
    value = payload.get("doi")
    if not value:
        ids = payload.get("ids") or {}
        value = ids.get("doi")
    if not value:
        return None
    try:
        return normalize_doi(value)
    except ValueError:
        return None


def _title(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None) -> str | None:
    title = (openalex_payload or {}).get("title")
    if title:
        return title
    titles = (crossref_payload or {}).get("title") or []
    return titles[0] if titles else None


def _journal(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None) -> str | None:
    source = ((openalex_payload or {}).get("primary_location") or {}).get("source") or {}
    return source.get("display_name") or _first((crossref_payload or {}).get("container-title"))


def _publisher(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None) -> str | None:
    source = ((openalex_payload or {}).get("primary_location") or {}).get("source") or {}
    return source.get("host_organization_name") or (crossref_payload or {}).get("publisher")


def _publication_year(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None) -> int | None:
    year = (openalex_payload or {}).get("publication_year")
    if year:
        return int(year)
    parts = (((crossref_payload or {}).get("published-print") or {}).get("date-parts") or []) or (
        ((crossref_payload or {}).get("published-online") or {}).get("date-parts") or []
    )
    return parts[0][0] if parts and parts[0] else None


def _publication_date(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None) -> date | None:
    value = (openalex_payload or {}).get("publication_date")
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    parts = (((crossref_payload or {}).get("published-print") or {}).get("date-parts") or []) or (
        ((crossref_payload or {}).get("published-online") or {}).get("date-parts") or []
    )
    if not parts or not parts[0]:
        return None
    year = parts[0][0]
    month = parts[0][1] if len(parts[0]) > 1 else 1
    day = parts[0][2] if len(parts[0]) > 2 else 1
    return date(year, month, day)


def _landing_page(openalex_payload: dict[str, Any] | None, crossref_payload: dict[str, Any] | None, doi: str | None) -> str | None:
    location = (openalex_payload or {}).get("primary_location") or {}
    if location.get("landing_page_url") or (crossref_payload or {}).get("URL"):
        return location.get("landing_page_url") or (crossref_payload or {}).get("URL")
    return doi_url(doi) if doi else None


def _open_access_url(openalex_payload: dict[str, Any] | None) -> str | None:
    location = (openalex_payload or {}).get("primary_location") or {}
    return location.get("pdf_url") or ((openalex_payload or {}).get("open_access") or {}).get("oa_url")


def _material_status(openalex_payload: dict[str, Any] | None, paper: Paper) -> str:
    if paper.is_source_data_available:
        return "source_data_found"
    if paper.open_access_url or _openalex_pdf_url(openalex_payload):
        return "pdf_found"
    if paper.landing_page_url:
        return "landing_page_found"
    return "metadata_only"


def _abstract(openalex_payload: dict[str, Any] | None) -> str | None:
    inverted = (openalex_payload or {}).get("abstract_inverted_index")
    if not inverted:
        return None
    positions: dict[int, str] = {}
    for word, indexes in inverted.items():
        for index in indexes:
            positions[int(index)] = word
    return " ".join(positions[i] for i in sorted(positions))


def _sync_openalex_authorships(db: Session, paper: Paper, payload: dict[str, Any]) -> None:
    db.execute(delete(Authorship).where(Authorship.paper_id == paper.id))
    for index, item in enumerate(payload.get("authorships") or [], start=1):
        author_payload = item.get("author") or {}
        raw_name = author_payload.get("display_name") or "Unknown author"
        author = _upsert_author(db, raw_name, author_payload.get("id"), author_payload.get("orcid"))
        institutions = item.get("institutions") or []
        affiliation_raw = _affiliation_raw(item)
        author_position = item.get("author_position")
        is_corresponding = bool(item.get("is_corresponding"))
        role = _author_role(index, author_position, is_corresponding)
        if institutions:
            for institution_payload in institutions:
                institution = _upsert_institution(db, institution_payload)
                db.add(
                    Authorship(
                        paper=paper,
                        author=author,
                        author_name_raw=raw_name,
                        author_position=index,
                        author_role=role,
                        is_corresponding=is_corresponding,
                        institution=institution,
                        affiliation_raw=affiliation_raw,
                        affiliation_match_confidence=1.0,
                    )
                )
        else:
            db.add(
                Authorship(
                    paper=paper,
                    author=author,
                    author_name_raw=raw_name,
                    author_position=index,
                    author_role=role,
                    is_corresponding=is_corresponding,
                    affiliation_raw=affiliation_raw,
                )
            )


def _sync_openalex_artifacts(db: Session, paper: Paper, payload: dict[str, Any]) -> None:
    landing_page_url = ((payload.get("primary_location") or {}).get("landing_page_url")) or paper.landing_page_url
    pdf_url = _openalex_pdf_url(payload)
    if landing_page_url:
        _upsert_artifact(db, paper, "publisher_landing_page", landing_page_url, "unknown")
    if pdf_url:
        _upsert_artifact(db, paper, "paper_pdf", pdf_url, "open_or_linked")
        paper.is_oa_pdf_available = True

    for location in payload.get("locations") or []:
        location_pdf = location.get("pdf_url")
        location_page = location.get("landing_page_url")
        if location_page:
            _upsert_artifact(db, paper, "publisher_landing_page", location_page, "unknown")
        if location_pdf:
            _upsert_artifact(db, paper, "paper_pdf", location_pdf, "open_or_linked")
            paper.is_oa_pdf_available = True

    paper.material_status = _material_status(payload, paper)


def _openalex_pdf_url(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    location = payload.get("primary_location") or {}
    return location.get("pdf_url") or ((payload.get("open_access") or {}).get("oa_url"))


def _upsert_artifact(db: Session, paper: Paper, artifact_type: str, source_url: str, license_status: str) -> SourceArtifact:
    artifact = db.scalar(
        select(SourceArtifact).where(
            SourceArtifact.paper_id == paper.id,
            SourceArtifact.artifact_type == artifact_type,
            SourceArtifact.source_url == source_url,
        )
    )
    if artifact is None:
        artifact = SourceArtifact(
            paper=paper,
            artifact_type=artifact_type,
            source_url=source_url,
            license_status=license_status,
        )
        db.add(artifact)
    return artifact


def _sync_crossref_authorships(db: Session, paper: Paper, payload: dict[str, Any]) -> None:
    db.execute(delete(Authorship).where(Authorship.paper_id == paper.id))
    for index, item in enumerate(payload.get("author") or [], start=1):
        raw_name = " ".join(part for part in [item.get("given"), item.get("family")] if part).strip() or item.get("name") or "Unknown author"
        author = _upsert_author(db, raw_name, None, item.get("ORCID"))
        db.add(
            Authorship(
                paper=paper,
                author=author,
                author_name_raw=raw_name,
                author_position=index,
                author_role=_author_role(index, None, False),
                affiliation_raw="; ".join(aff.get("name", "") for aff in item.get("affiliation") or [] if aff.get("name")),
            )
        )


def _upsert_author(db: Session, display_name: str, openalex_id: str | None, orcid: str | None) -> Author:
    query = select(Author)
    if openalex_id:
        author = db.scalar(query.where(Author.openalex_id == openalex_id))
    elif orcid:
        author = db.scalar(query.where(Author.orcid == orcid))
    else:
        author = db.scalar(query.where(Author.display_name == display_name))
    if author is None:
        author = Author(display_name=display_name, openalex_id=openalex_id, orcid=orcid, name_variants=[display_name])
        db.add(author)
    author.display_name = display_name
    author.openalex_id = openalex_id or author.openalex_id
    author.orcid = orcid or author.orcid
    return author


def _upsert_institution(db: Session, payload: dict[str, Any]) -> Institution:
    openalex_id = payload.get("id")
    ror = payload.get("ror")
    institution = None
    if openalex_id:
        institution = db.scalar(select(Institution).where(Institution.openalex_id == openalex_id))
    if institution is None and ror:
        institution = db.scalar(select(Institution).where(Institution.ror_id == ror))
    if institution is None:
        institution = db.scalar(select(Institution).where(Institution.display_name == payload.get("display_name")))
    if institution is None:
        institution = Institution(display_name=payload.get("display_name") or "Unknown institution")
        db.add(institution)
    institution.display_name = payload.get("display_name") or institution.display_name
    institution.openalex_id = openalex_id or institution.openalex_id
    institution.ror_id = ror or institution.ror_id
    institution.country_code = payload.get("country_code") or institution.country_code
    institution.city = payload.get("city") or institution.city
    return institution


def _save_source_record(
    db: Session,
    source_name: str,
    entity_type: str,
    entity_id: str,
    source_record_id: str | None,
    source_url: str | None,
    raw_payload: dict[str, Any],
) -> None:
    digest = payload_hash(raw_payload)
    existing = db.scalar(
        select(SourceRecord).where(
            SourceRecord.source_name == source_name,
            SourceRecord.entity_type == entity_type,
            SourceRecord.entity_id == entity_id,
            SourceRecord.raw_payload_hash == digest,
        )
    )
    if existing is None:
        db.add(
            SourceRecord(
                source_name=source_name,
                source_record_id=source_record_id,
                source_url=source_url,
                entity_type=entity_type,
                entity_id=entity_id,
                raw_payload=raw_payload,
                raw_payload_hash=digest,
            )
        )


def _affiliation_raw(item: dict[str, Any]) -> str | None:
    raw = item.get("raw_affiliation_strings") or []
    if raw:
        return "; ".join(raw)
    return None


def _author_role(index: int, openalex_position: str | None, is_corresponding: bool) -> str:
    if is_corresponding:
        return "corresponding"
    if openalex_position in {"first", "middle", "last"}:
        return openalex_position
    return "first" if index == 1 else "unknown"


def _first(value: list[Any] | None) -> Any | None:
    return value[0] if value else None
