from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from math import sqrt
from io import StringIO
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from gengscope_api.config import get_settings
from gengscope_api.db.models import AlgorithmicSignal, Author, Authorship, EntityGroup, EntityGroupMember, EntitySearchCache, Institution, Paper, ReviewTask
from gengscope_api.schemas.entities import EntityCorpusRequest, EntityGroupMemberRequest
from gengscope_api.services.import_paper import SourceClients, import_openalex_work


OFFICIAL_STATUS_LEVELS = {
    "official_retraction",
    "official_correction",
    "official_expression_of_concern",
}
PUBLIC_STATUS_LEVELS = {"public_discussion", "media_report"}
AUDITABLE_MATERIAL_STATUSES = {"pdf_found", "source_data_found", "full_auditable", "manual_upload_available"}
COUNTED_SIGNAL_STATUSES = {"needs_review", "in_review", "confirmed_signal", "promoted_to_event"}


def search_entities(clients: SourceClients, entity_type: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    normalized_type = _entity_type(entity_type)
    if normalized_type == "author":
        results = clients.openalex.search_authors(query, limit=limit)
        return [_author_candidate(item) for item in results]
    if normalized_type == "group":
        raise ValueError("group entities are local composites; create them from resolved author or institution members")
    results = clients.openalex.search_institutions(query, limit=limit)
    return [_institution_candidate(item) for item in results]


def search_entities_with_cache(
    db: Session,
    clients: SourceClients,
    entity_type: str,
    query: str,
    limit: int = 10,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    normalized_type = _entity_type(entity_type)
    if normalized_type == "group":
        raise ValueError("group entities are local composites; create them from resolved author or institution members")
    query_text = query.strip()
    query_normalized = _search_query_key(query_text)
    if not query_normalized:
        raise ValueError("query is required")
    cache = _load_search_cache(db, normalized_type, query_normalized, limit)
    if cache is not None and not refresh:
        return _cached_search_response(cache)
    try:
        items = search_entities(clients, normalized_type, query_text, limit)
    except Exception as exc:
        if cache is not None:
            return _cached_search_response(cache, fallback_error=str(exc))
        raise
    cache = _upsert_search_cache(db, normalized_type, query_text, query_normalized, limit, items)
    return _remote_search_response(cache)


def build_entity_corpus(db: Session, clients: SourceClients, request: EntityCorpusRequest) -> dict[str, Any]:
    entity_type = _entity_type(request.entity_type)
    if entity_type == "group":
        raise ValueError("group corpora must be created from author or institution members")
    candidate = _resolve_candidate(clients, request)
    if entity_type == "author":
        entity = _upsert_author_candidate(db, candidate)
        works = clients.openalex.fetch_works_by_author(candidate["openalex_id"], request.limit, request.year_from, request.year_to)
    else:
        entity = _upsert_institution_candidate(db, candidate)
        works = clients.openalex.fetch_works_by_institution(candidate["openalex_id"], request.limit, request.year_from, request.year_to)

    imported_papers = []
    for work in works:
        imported_papers.append(import_openalex_work(db, work, commit=False))
    db.commit()
    for paper in imported_papers:
        db.refresh(paper)

    profile = entity_profile(db, entity_type, entity.id)
    return {
        "entity": _entity_dict(entity_type, entity),
        "imported_count": len(imported_papers),
        "profile": profile,
    }


def create_entity_group(
    db: Session,
    *,
    display_name: str,
    description: str | None = None,
    members: list[EntityGroupMemberRequest],
) -> dict[str, Any]:
    cleaned_name = display_name.strip()
    if not cleaned_name:
        raise ValueError("display_name is required")
    group = EntityGroup(display_name=cleaned_name, description=(description or "").strip() or None)
    db.add(group)
    db.flush()
    _replace_group_members(db, group, members)
    db.commit()
    db.refresh(group)
    return {
        "entity": _entity_dict("group", group),
        "profile": entity_profile(db, "group", group.id),
        "conclusion_boundary": "本地 group/lab 只是把多个作者或机构组成一个可审计集合，用于覆盖率和复核优先级排序，不能直接认定实验室造假。",
    }


def build_entity_group_corpus(
    db: Session,
    clients: SourceClients,
    *,
    display_name: str,
    description: str | None = None,
    members: list[EntityCorpusRequest],
    continue_on_error: bool = True,
) -> dict[str, Any]:
    built_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    group_members: list[EntityGroupMemberRequest] = []
    total_imported = 0
    for index, member in enumerate(members):
        try:
            result = build_entity_corpus(db, clients, member)
            entity = result["entity"]
            built_items.append({"index": index, "status": "succeeded", **result})
            group_members.append(
                EntityGroupMemberRequest(
                    entity_type=entity["entity_type"],
                    entity_id=entity["id"],
                    label=member.display_name or member.query or entity["display_name"],
                )
            )
            total_imported += result["imported_count"]
        except Exception as exc:
            db.rollback()
            error = {
                "index": index,
                "status": "failed",
                "entity_type": member.entity_type,
                "query": member.query,
                "openalex_id": member.openalex_id,
                "error": str(exc),
            }
            errors.append(error)
            if not continue_on_error:
                raise ValueError(f"Group corpus member {index} failed: {exc}") from exc
    if not group_members:
        raise ValueError("group corpus must contain at least one successfully built member")
    group_result = create_entity_group(db, display_name=display_name, description=description, members=group_members)
    return {
        **group_result,
        "member_results": built_items,
        "errors": errors,
        "member_count": len(members),
        "succeeded_count": len(built_items),
        "failed_count": len(errors),
        "total_imported_count": total_imported,
    }


def parse_entity_manifest(
    content: bytes,
    *,
    filename: str,
    default_limit: int = 25,
    default_year_from: int | None = None,
    default_year_to: int | None = None,
    max_items: int = 100,
) -> list[EntityCorpusRequest]:
    if not content:
        raise ValueError("entity manifest file is empty")
    text = content.decode("utf-8-sig")
    suffix = Path(filename).suffix.casefold()
    if suffix == ".json":
        raw_items = _json_manifest_items(text)
    elif suffix in {".csv", ".tsv", ".txt", ""}:
        raw_items = _delimited_manifest_items(text, delimiter="\t" if suffix == ".tsv" else ",")
    else:
        raise ValueError("entity manifest must be a CSV, TSV or JSON file")
    if not raw_items:
        raise ValueError("entity manifest contains no items")
    if len(raw_items) > max_items:
        raise ValueError(f"entity manifest contains more than {max_items} items")
    return [
        EntityCorpusRequest(
            entity_type=_required_str(item, "entity_type", index),
            query=_optional_str(item.get("query") or item.get("name")),
            openalex_id=_optional_str(item.get("openalex_id")),
            display_name=_optional_str(item.get("display_name")),
            limit=_optional_int(item.get("limit"), default_limit),
            year_from=_optional_int(item.get("year_from"), default_year_from),
            year_to=_optional_int(item.get("year_to"), default_year_to),
        )
        for index, item in enumerate(raw_items)
    ]


def entity_profile(db: Session, entity_type: str, entity_id: str) -> dict[str, Any]:
    normalized_type = _entity_type(entity_type)
    entity = _load_entity(db, normalized_type, entity_id)
    papers = _entity_papers(db, normalized_type, entity_id)
    paper_ids = {paper.id for paper in papers}
    authorships = _entity_authorships(db, normalized_type, entity_id)
    author_role_by_paper = _role_by_paper(authorships)
    review_queue_count = len(db.scalars(select(ReviewTask).where(ReviewTask.paper_id.in_(paper_ids))).all()) if paper_ids else 0

    total = len(papers)
    material_counts = Counter(paper.material_status for paper in papers)
    auditable_count = sum(1 for paper in papers if paper.material_status in AUDITABLE_MATERIAL_STATUSES)
    audited_count = sum(1 for paper in papers if paper.audit_status != "not_audited" or _counted_signals(paper))
    signal_paper_count = sum(1 for paper in papers if _counted_signals(paper))
    official_event_count = sum(_official_event_count(paper) for paper in papers)
    public_discussion_count = sum(_public_event_count(paper) for paper in papers)
    algorithmic_signal_count = sum(len(_counted_signals(paper)) for paper in papers)

    return {
        "entity": _entity_dict(normalized_type, entity),
        "paper_count": total,
        "year_range": _year_range(papers),
        "first_author_paper_count": sum(1 for paper_id, role in author_role_by_paper.items() if role == "first"),
        "corresponding_author_paper_count": sum(1 for paper_id, role in author_role_by_paper.items() if role == "corresponding"),
        "landing_page_count": sum(1 for paper in papers if paper.landing_page_url),
        "oa_pdf_count": sum(1 for paper in papers if paper.is_oa_pdf_available),
        "source_data_count": sum(1 for paper in papers if paper.is_source_data_available),
        "auditable_paper_count": auditable_count,
        "audited_paper_count": audited_count,
        "review_queue_count": review_queue_count,
        "signal_paper_count": signal_paper_count,
        "official_event_count": official_event_count,
        "public_discussion_count": public_discussion_count,
        "algorithmic_signal_count": algorithmic_signal_count,
        "material_status_counts": dict(material_counts),
        "auditable_coverage": _ratio(auditable_count, total),
        "audit_coverage": _ratio(audited_count, total),
        "signal_rate_among_audited": _ratio(signal_paper_count, audited_count),
        "sample_inference": _sample_inference(total, audited_count, signal_paper_count),
        "priority": _priority(total, auditable_count, audited_count, signal_paper_count, official_event_count, public_discussion_count),
        "summary": _profile_summary(total, auditable_count, audited_count, signal_paper_count, official_event_count, public_discussion_count),
        "top_papers": [_paper_summary(paper) for paper in papers[:20]],
        "conclusion_boundary": "实体画像只表示已索引论文和已获取材料中的公开状态、可审计覆盖率与异常信号，不能直接认定作者、实验室或机构造假。",
    }


def entity_breakdown(db: Session, entity_type: str, entity_id: str, *, limit: int = 25, min_papers: int = 1) -> dict[str, Any]:
    normalized_type = _entity_type(entity_type)
    entity = _load_entity(db, normalized_type, entity_id)
    papers = _entity_papers(db, normalized_type, entity_id)
    paper_by_id = {paper.id: paper for paper in papers}
    authorships = _entity_authorships(db, normalized_type, entity_id)
    affiliation_units: dict[str, dict[str, Any]] = {}
    author_units: dict[str, dict[str, Any]] = {}

    for authorship in authorships:
        paper = paper_by_id.get(authorship.paper_id)
        if paper is None:
            continue
        author_key = authorship.author_id or f"raw:{authorship.author_name_raw.casefold()}"
        author_bucket = author_units.setdefault(
            author_key,
            {
                "author_id": authorship.author_id,
                "display_name": authorship.author.display_name if authorship.author else authorship.author_name_raw,
                "paper_ids": set(),
                "affiliations": [],
                "first_author_paper_count": 0,
                "corresponding_author_paper_count": 0,
                "signal_paper_ids": set(),
            },
        )
        author_bucket["paper_ids"].add(paper.id)
        if authorship.affiliation_raw:
            author_bucket["affiliations"].append(authorship.affiliation_raw)
        if authorship.author_role == "first":
            author_bucket["first_author_paper_count"] += 1
        if authorship.is_corresponding:
            author_bucket["corresponding_author_paper_count"] += 1
        if _counted_signals(paper):
            author_bucket["signal_paper_ids"].add(paper.id)

        for unit in _affiliation_units(authorship.affiliation_raw, entity.display_name):
            key = unit["normalized"]
            bucket = affiliation_units.setdefault(
                key,
                {
                    "unit_name": unit["name"],
                    "unit_type": unit["unit_type"],
                    "paper_ids": set(),
                    "author_keys": set(),
                    "affiliations": [],
                    "signal_paper_ids": set(),
                    "auditable_paper_ids": set(),
                    "official_event_count": 0,
                    "public_discussion_count": 0,
                },
            )
            bucket["paper_ids"].add(paper.id)
            bucket["author_keys"].add(author_key)
            if authorship.affiliation_raw:
                bucket["affiliations"].append(authorship.affiliation_raw)
            if _counted_signals(paper):
                bucket["signal_paper_ids"].add(paper.id)
            if paper.material_status in AUDITABLE_MATERIAL_STATUSES:
                bucket["auditable_paper_ids"].add(paper.id)
            bucket["official_event_count"] += _official_event_count(paper)
            bucket["public_discussion_count"] += _public_event_count(paper)

    unit_items = [
        _breakdown_unit_dict(bucket, author_units)
        for bucket in affiliation_units.values()
        if len(bucket["paper_ids"]) >= min_papers
    ]
    author_items = [
        _breakdown_author_dict(bucket)
        for bucket in author_units.values()
        if len(bucket["paper_ids"]) >= min_papers
    ]
    unit_items.sort(key=lambda item: (-item["paper_count"], item["unit_type"], item["unit_name"]))
    author_items.sort(
        key=lambda item: (
            -item["paper_count"],
            -item["corresponding_author_paper_count"],
            -item["first_author_paper_count"],
            item["display_name"],
        )
    )
    return {
        "entity": _entity_dict(normalized_type, entity),
        "paper_count": len(papers),
        "affiliation_unit_count": len(unit_items),
        "author_count": len(author_items),
        "affiliation_units": unit_items[:limit],
        "top_authors": author_items[:limit],
        "method": {
            "source": "authorship.affiliation_raw",
            "classification": "keyword_heuristic",
            "min_papers": min_papers,
            "limit": limit,
        },
        "conclusion_boundary": "机构内部分组来自公开元数据中的原始 affiliation 启发式拆分，只用于导航、取样和复核优先级排序，不能作为院系归属或科研完整性事实结论。",
    }


def list_entity_papers(db: Session, entity_type: str, entity_id: str) -> list[Paper]:
    _load_entity(db, _entity_type(entity_type), entity_id)
    return _entity_papers(db, entity_type, entity_id)


def queue_entity_review_tasks(db: Session, entity_type: str, entity_id: str, priority: int = 5) -> dict[str, Any]:
    papers = _entity_papers(db, entity_type, entity_id)
    created = 0
    for paper in papers:
        if paper.material_status not in AUDITABLE_MATERIAL_STATUSES:
            continue
        existing = db.scalar(
            select(ReviewTask).where(
                ReviewTask.paper_id == paper.id,
                ReviewTask.task_type == "artifact_audit",
                ReviewTask.status == "open",
            )
        )
        if existing is not None:
            continue
        db.add(ReviewTask(paper_id=paper.id, task_type="artifact_audit", priority=priority))
        paper.audit_status = "queued"
        created += 1
    db.commit()
    return {"created_review_tasks": created, "profile": entity_profile(db, entity_type, entity_id)}


def _resolve_candidate(clients: SourceClients, request: EntityCorpusRequest) -> dict[str, Any]:
    if request.openalex_id:
        return {
            "entity_type": request.entity_type,
            "openalex_id": request.openalex_id,
            "display_name": request.display_name or request.openalex_id.rsplit("/", 1)[-1],
            "works_count": None,
            "country_code": None,
        }
    if not request.query:
        raise ValueError("query or openalex_id is required")
    candidates = search_entities(clients, request.entity_type, request.query, limit=10)
    if not candidates:
        raise LookupError(f"No {request.entity_type} found for query {request.query!r}")
    query_normalized = request.query.strip().casefold()
    for candidate in candidates:
        if candidate["display_name"].strip().casefold() == query_normalized:
            return candidate
    return candidates[0]


def _json_manifest_items(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("items")
    if not isinstance(payload, list):
        raise ValueError("JSON entity manifest must be a list or an object with an items list")
    return [_manifest_row(item, index) for index, item in enumerate(payload)]


def _delimited_manifest_items(text: str, *, delimiter: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("entity manifest must include a header row")
    return [_manifest_row(row, index) for index, row in enumerate(reader) if any((value or "").strip() for value in row.values())]


def _manifest_row(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"entity manifest row {index} must be an object")
    return {str(key).strip(): value for key, value in item.items() if str(key).strip()}


def _required_str(item: dict[str, Any], key: str, index: int) -> str:
    value = _optional_str(item.get(key))
    if not value:
        raise ValueError(f"entity manifest row {index} is missing {key}")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_int(value: Any, default: int | None) -> int | None:
    if value is None or str(value).strip() == "":
        return default
    return int(value)


def _author_candidate(item: dict[str, Any]) -> dict[str, Any]:
    last_institution = item.get("last_known_institution") or {}
    return {
        "entity_type": "author",
        "openalex_id": item.get("id"),
        "display_name": item.get("display_name") or "Unknown author",
        "works_count": item.get("works_count"),
        "country_code": (last_institution.get("country_code") if last_institution else None),
        "hint": last_institution.get("display_name") if last_institution else None,
    }


def _institution_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": "institution",
        "openalex_id": item.get("id"),
        "display_name": item.get("display_name") or "Unknown institution",
        "works_count": item.get("works_count"),
        "country_code": item.get("country_code"),
        "hint": item.get("city"),
    }


def _upsert_author_candidate(db: Session, candidate: dict[str, Any]) -> Author:
    author = db.scalar(select(Author).where(Author.openalex_id == candidate["openalex_id"]))
    if author is None:
        author = Author(
            display_name=candidate["display_name"],
            openalex_id=candidate["openalex_id"],
            name_variants=[candidate["display_name"]],
            disambiguation_status="openalex_resolved",
        )
        db.add(author)
        db.flush()
    else:
        author.display_name = candidate["display_name"]
    return author


def _upsert_institution_candidate(db: Session, candidate: dict[str, Any]) -> Institution:
    institution = db.scalar(select(Institution).where(Institution.openalex_id == candidate["openalex_id"]))
    if institution is None:
        institution = Institution(
            display_name=candidate["display_name"],
            openalex_id=candidate["openalex_id"],
            country_code=candidate.get("country_code"),
            city=candidate.get("hint"),
        )
        db.add(institution)
        db.flush()
    else:
        institution.display_name = candidate["display_name"]
        institution.country_code = candidate.get("country_code") or institution.country_code
    return institution


def _entity_papers(db: Session, entity_type: str, entity_id: str) -> list[Paper]:
    normalized_type = _entity_type(entity_type)
    if normalized_type == "group":
        return _group_papers(db, entity_id)
    statement = (
        select(Paper)
        .join(Authorship)
        .options(selectinload(Paper.events), selectinload(Paper.algorithmic_signals), selectinload(Paper.source_artifacts))
        .order_by(Paper.publication_year.desc().nullslast(), Paper.title)
    )
    if normalized_type == "author":
        statement = statement.where(Authorship.author_id == entity_id)
    else:
        statement = statement.where(Authorship.institution_id == entity_id)
    seen: set[str] = set()
    papers: list[Paper] = []
    for paper in db.scalars(statement).all():
        if paper.id not in seen:
            papers.append(paper)
            seen.add(paper.id)
    return papers


def _entity_authorships(db: Session, entity_type: str, entity_id: str) -> list[Authorship]:
    normalized_type = _entity_type(entity_type)
    if normalized_type == "group":
        return _group_authorships(db, entity_id)
    statement = select(Authorship)
    if normalized_type == "author":
        statement = statement.where(Authorship.author_id == entity_id)
    else:
        statement = statement.where(Authorship.institution_id == entity_id)
    return db.scalars(statement).all()


def _role_by_paper(authorships: list[Authorship]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for authorship in authorships:
        if authorship.is_corresponding:
            roles[authorship.paper_id] = "corresponding"
        elif authorship.author_role == "first" and roles.get(authorship.paper_id) != "corresponding":
            roles[authorship.paper_id] = "first"
        elif authorship.paper_id not in roles:
            roles[authorship.paper_id] = authorship.author_role or "unknown"
    return roles


def _load_entity(db: Session, entity_type: str, entity_id: str) -> Author | Institution | EntityGroup:
    normalized_type = _entity_type(entity_type)
    model = Author if normalized_type == "author" else Institution if normalized_type == "institution" else EntityGroup
    entity = db.get(model, entity_id)
    if entity is None:
        raise LookupError(f"No {entity_type} found for id {entity_id}")
    return entity


def _entity_dict(entity_type: str, entity: Author | Institution | EntityGroup) -> dict[str, Any]:
    if entity_type == "author":
        assert isinstance(entity, Author)
        return {
            "entity_type": "author",
            "id": entity.id,
            "display_name": entity.display_name,
            "openalex_id": entity.openalex_id,
            "orcid": entity.orcid,
        }
    if entity_type == "group":
        assert isinstance(entity, EntityGroup)
        return {
            "entity_type": "group",
            "id": entity.id,
            "display_name": entity.display_name,
            "description": entity.description,
            "members": [_group_member_dict(member) for member in entity.memberships],
        }
    assert isinstance(entity, Institution)
    return {
        "entity_type": "institution",
        "id": entity.id,
        "display_name": entity.display_name,
        "openalex_id": entity.openalex_id,
        "ror_id": entity.ror_id,
        "country_code": entity.country_code,
        "city": entity.city,
    }


def _replace_group_members(db: Session, group: EntityGroup, members: list[EntityGroupMemberRequest]) -> None:
    db.query(EntityGroupMember).filter(EntityGroupMember.group_id == group.id).delete()
    seen: set[tuple[str, str]] = set()
    for member in members:
        member_type = _member_entity_type(member.entity_type)
        _load_entity(db, member_type, member.entity_id)
        key = (member_type, member.entity_id)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            EntityGroupMember(
                group_id=group.id,
                member_entity_type=member_type,
                member_entity_id=member.entity_id,
                label=(member.label or "").strip()[:160] or None,
            )
        )
    if not seen:
        raise ValueError("group must contain at least one distinct member")


def _group_papers(db: Session, group_id: str) -> list[Paper]:
    group = db.get(EntityGroup, group_id)
    if group is None:
        raise LookupError(f"No group found for id {group_id}")
    seen: set[str] = set()
    papers: list[Paper] = []
    for member in group.memberships:
        for paper in _entity_papers(db, member.member_entity_type, member.member_entity_id):
            if paper.id in seen:
                continue
            papers.append(paper)
            seen.add(paper.id)
    return sorted(papers, key=lambda paper: (-(paper.publication_year or 0), paper.title or ""))


def _group_authorships(db: Session, group_id: str) -> list[Authorship]:
    group = db.get(EntityGroup, group_id)
    if group is None:
        raise LookupError(f"No group found for id {group_id}")
    seen: set[str] = set()
    authorships: list[Authorship] = []
    for member in group.memberships:
        for authorship in _entity_authorships(db, member.member_entity_type, member.member_entity_id):
            if authorship.id in seen:
                continue
            authorships.append(authorship)
            seen.add(authorship.id)
    return authorships


def _group_member_dict(member: EntityGroupMember) -> dict[str, Any]:
    return {
        "id": member.id,
        "entity_type": member.member_entity_type,
        "entity_id": member.member_entity_id,
        "label": member.label,
    }


def _paper_summary(paper: Paper) -> dict[str, Any]:
    return {
        "id": paper.id,
        "doi": paper.doi,
        "title": paper.title,
        "journal_name": paper.journal_name,
        "publication_year": paper.publication_year,
        "material_status": paper.material_status,
        "audit_status": paper.audit_status,
        "algorithmic_signal_count": len(_counted_signals(paper)),
        "official_event_count": _official_event_count(paper),
        "landing_page_url": paper.landing_page_url,
        "open_access_url": paper.open_access_url,
    }


_UNIT_KEYWORDS = [
    ("laboratory", re.compile(r"\b(lab|laboratory|key laboratory|state key laboratory)\b|实验室|重点实验室", re.IGNORECASE)),
    ("department", re.compile(r"\b(department|dept\.?|division|section|clinic)\b|系|科|教研室", re.IGNORECASE)),
    ("school", re.compile(r"\b(school|college|faculty)\b|学院|学部", re.IGNORECASE)),
    ("institute", re.compile(r"\b(institute|academy|research center|research centre|center|centre)\b|研究院|研究所|中心|科学院", re.IGNORECASE)),
    ("hospital", re.compile(r"\b(hospital|medical center|medical centre)\b|医院", re.IGNORECASE)),
]


def _affiliation_units(affiliation_raw: str | None, entity_name: str | None) -> list[dict[str, str]]:
    if not affiliation_raw:
        return []
    entity_normalized = _normalize_unit(entity_name or "")
    units: list[dict[str, str]] = []
    for part in re.split(r"[,;，；|]+", affiliation_raw):
        name = re.sub(r"\s+", " ", part).strip(" .")
        if len(name) < 3:
            continue
        normalized = _normalize_unit(name)
        if not normalized or normalized == entity_normalized:
            continue
        unit_type = _unit_type(name)
        if unit_type == "other" and entity_normalized and entity_normalized not in normalized:
            continue
        if any(existing["normalized"] == normalized for existing in units):
            continue
        units.append({"name": name, "normalized": normalized, "unit_type": unit_type})
    return units


def _unit_type(name: str) -> str:
    for unit_type, pattern in _UNIT_KEYWORDS:
        if pattern.search(name):
            return unit_type
    return "other"


def _normalize_unit(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", value.casefold()).strip()


def _breakdown_unit_dict(bucket: dict[str, Any], author_units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paper_count = len(bucket["paper_ids"])
    authors = [
        {
            "author_id": author_units[key]["author_id"],
            "display_name": author_units[key]["display_name"],
            "paper_count": len(author_units[key]["paper_ids"] & bucket["paper_ids"]),
        }
        for key in bucket["author_keys"]
        if key in author_units
    ]
    authors.sort(key=lambda item: (-item["paper_count"], item["display_name"]))
    return {
        "unit_name": bucket["unit_name"],
        "unit_type": bucket["unit_type"],
        "paper_count": paper_count,
        "author_count": len(bucket["author_keys"]),
        "auditable_paper_count": len(bucket["auditable_paper_ids"]),
        "signal_paper_count": len(bucket["signal_paper_ids"]),
        "official_event_count": bucket["official_event_count"],
        "public_discussion_count": bucket["public_discussion_count"],
        "auditable_coverage": _ratio(len(bucket["auditable_paper_ids"]), paper_count),
        "top_authors": authors[:5],
        "sample_affiliations": _sample_strings(bucket["affiliations"], limit=3),
    }


def _breakdown_author_dict(bucket: dict[str, Any]) -> dict[str, Any]:
    paper_count = len(bucket["paper_ids"])
    return {
        "author_id": bucket["author_id"],
        "display_name": bucket["display_name"],
        "paper_count": paper_count,
        "first_author_paper_count": bucket["first_author_paper_count"],
        "corresponding_author_paper_count": bucket["corresponding_author_paper_count"],
        "signal_paper_count": len(bucket["signal_paper_ids"]),
        "sample_affiliations": _sample_strings(bucket["affiliations"], limit=3),
    }


def _sample_strings(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    samples: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned or cleaned in seen:
            continue
        samples.append(cleaned)
        seen.add(cleaned)
        if len(samples) >= limit:
            break
    return samples


def _load_search_cache(db: Session, entity_type: str, query_normalized: str, limit: int) -> EntitySearchCache | None:
    return db.scalar(
        select(EntitySearchCache).where(
            EntitySearchCache.entity_type == entity_type,
            EntitySearchCache.query_normalized == query_normalized,
            EntitySearchCache.requested_limit == limit,
        )
    )


def _upsert_search_cache(
    db: Session,
    entity_type: str,
    query_text: str,
    query_normalized: str,
    limit: int,
    items: list[dict[str, Any]],
) -> EntitySearchCache:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max(60, get_settings().entity_search_cache_ttl_seconds))
    cache = _load_search_cache(db, entity_type, query_normalized, limit)
    if cache is None:
        cache = EntitySearchCache(
            entity_type=entity_type,
            query_text=query_text,
            query_normalized=query_normalized,
            requested_limit=limit,
            results_json=items,
            result_count=len(items),
            source_name="openalex",
            fetched_at=now,
            expires_at=expires_at,
        )
        db.add(cache)
    else:
        cache.query_text = query_text
        cache.results_json = items
        cache.result_count = len(items)
        cache.source_name = "openalex"
        cache.fetched_at = now
        cache.expires_at = expires_at
    db.commit()
    db.refresh(cache)
    return cache


def _cached_search_response(cache: EntitySearchCache, *, fallback_error: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    status = "fresh" if _ensure_aware(cache.expires_at) >= now else "stale"
    if fallback_error:
        status = "stale_fallback"
    response = {
        "items": cache.results_json or [],
        "cached": True,
        "source": "cache",
        "cache_status": status,
        "fetched_at": cache.fetched_at.isoformat() if cache.fetched_at else None,
        "expires_at": cache.expires_at.isoformat() if cache.expires_at else None,
    }
    if fallback_error:
        response["warning"] = f"OpenAlex refresh failed; served cached results: {fallback_error}"
    return response


def _remote_search_response(cache: EntitySearchCache) -> dict[str, Any]:
    return {
        "items": cache.results_json or [],
        "cached": False,
        "source": cache.source_name,
        "cache_status": "refreshed",
        "fetched_at": cache.fetched_at.isoformat() if cache.fetched_at else None,
        "expires_at": cache.expires_at.isoformat() if cache.expires_at else None,
    }


def _counted_signals(paper: Paper) -> list[AlgorithmicSignal]:
    return [signal for signal in paper.algorithmic_signals if signal.status in COUNTED_SIGNAL_STATUSES]


def _official_event_count(paper: Paper) -> int:
    return sum(1 for event in paper.events if event.status_level in OFFICIAL_STATUS_LEVELS)


def _public_event_count(paper: Paper) -> int:
    return sum(1 for event in paper.events if event.status_level in PUBLIC_STATUS_LEVELS or event.source_type in {"pubpeer", "media"})


def _year_range(papers: list[Paper]) -> dict[str, int | None]:
    years = [paper.publication_year for paper in papers if paper.publication_year is not None]
    return {"from": min(years) if years else None, "to": max(years) if years else None}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _sample_inference(total: int, audited_count: int, signal_paper_count: int) -> dict[str, Any]:
    signal_rate = _ratio(signal_paper_count, audited_count)
    interval = _wilson_interval(signal_paper_count, audited_count)
    if audited_count == 0:
        reliability = "not_available"
        interpretation = "尚未形成已审计样本，只能继续获取全文、源数据或人工上传材料。"
    elif audited_count < 3:
        reliability = "very_low"
        interpretation = "已审计样本过小，只能作为材料获取和人工复核的排队线索。"
    elif _ratio(audited_count, total) < 0.5:
        reliability = "limited_coverage"
        interpretation = "已审计样本覆盖率有限，信号率可用于提高复核优先级，但不能代表全库比例。"
    else:
        reliability = "screening_estimate"
        interpretation = "已审计样本已有一定覆盖，可用于审计优先级排序；仍不能替代官方或人工结论。"
    return {
        "paper_count": total,
        "audited_sample_size": audited_count,
        "signal_sample_size": signal_paper_count,
        "audit_coverage": _ratio(audited_count, total),
        "observed_signal_rate": signal_rate,
        "wilson_signal_rate_interval_95": interval,
        "reliability": reliability,
        "interpretation": interpretation,
        "extrapolation_boundary": "该区间只描述已审计样本中算法信号率的不确定性；全文可得性和上传材料可能有偏，不能外推为全库造假比例或事实结论。",
    }


def _wilson_interval(successes: int, sample_size: int, z: float = 1.96) -> dict[str, float]:
    if sample_size <= 0:
        return {"lower": 0.0, "upper": 0.0}
    proportion = successes / sample_size
    denominator = 1 + z * z / sample_size
    center = (proportion + z * z / (2 * sample_size)) / denominator
    margin = z * sqrt((proportion * (1 - proportion) + z * z / (4 * sample_size)) / sample_size) / denominator
    return {"lower": round(max(0.0, center - margin), 4), "upper": round(min(1.0, center + margin), 4)}


def _priority(
    total: int,
    auditable_count: int,
    audited_count: int,
    signal_paper_count: int,
    official_event_count: int,
    public_discussion_count: int,
) -> str:
    signal_rate = _ratio(signal_paper_count, audited_count)
    if official_event_count or (audited_count >= 2 and signal_rate >= 0.5) or signal_paper_count >= 2:
        return "high"
    if public_discussion_count or signal_paper_count or auditable_count:
        return "medium"
    if total:
        return "low"
    return "unknown"


def _profile_summary(
    total: int,
    auditable_count: int,
    audited_count: int,
    signal_paper_count: int,
    official_event_count: int,
    public_discussion_count: int,
) -> str:
    if total == 0:
        return "尚未索引到该实体相关论文。"
    parts = [f"已索引 {total} 篇论文", f"其中 {auditable_count} 篇存在可审计全文或材料"]
    if audited_count:
        parts.append(f"已进入审计或已有信号的论文 {audited_count} 篇")
    if signal_paper_count:
        parts.append(f"{signal_paper_count} 篇存在算法异常信号")
    if official_event_count:
        parts.append(f"{official_event_count} 条官方事件")
    if public_discussion_count:
        parts.append(f"{public_discussion_count} 条公开讨论或媒体记录")
    return "，".join(parts) + "。"


def _entity_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"author", "institution", "group"}:
        raise ValueError("entity_type must be 'author', 'institution' or 'group'")
    return normalized


def _search_query_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _member_entity_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"author", "institution"}:
        raise ValueError("group members must be authors or institutions")
    return normalized
