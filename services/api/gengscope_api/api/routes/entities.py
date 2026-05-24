from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from gengscope_api.api.deps import get_source_clients
from gengscope_api.db.session import get_db
from gengscope_api.schemas.entities import EntityAuditQueueRequest, EntityBatchCorpusRequest, EntityCorpusRequest, EntityGroupCorpusRequest, EntityGroupCreateRequest
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.entities import (
    build_entity_corpus,
    build_entity_group_corpus,
    create_entity_group,
    entity_breakdown,
    entity_profile,
    parse_entity_manifest,
    queue_entity_review_tasks,
    search_entities,
    search_entities_with_cache,
)
from gengscope_api.services.import_paper import SourceClients

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.get("/search")
def search_entity_candidates(
    query: str,
    entity_type: str = Query(pattern="^(author|institution)$"),
    limit: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
) -> dict:
    try:
        return search_entities_with_cache(db, clients, entity_type, query, limit, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Entity search failed: {exc}") from exc


@router.post("/corpus")
def build_corpus_endpoint(
    request: EntityCorpusRequest,
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = build_entity_corpus(db, clients, request)
        entity = result["entity"]
        record_audit_log(
            db,
            action="entity_corpus_built",
            actor=actor,
            target_type="entity",
            target_id=entity["id"],
            entity_type=entity["entity_type"],
            entity_id=entity["id"],
            summary=f"Built corpus for {entity['entity_type']} {entity['display_name']}.",
            metadata={
                "query": request.query,
                "openalex_id": entity.get("openalex_id"),
                "limit": request.limit,
                "year_from": request.year_from,
                "year_to": request.year_to,
                "imported_count": result["imported_count"],
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Corpus build failed: {exc}") from exc


@router.post("/corpus/batch")
def build_batch_corpus_endpoint(
    request: EntityBatchCorpusRequest,
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    return _build_batch_corpus(db, clients, request.items, continue_on_error=request.continue_on_error, actor=actor)


@router.post("/groups")
def create_group_endpoint(
    request: EntityGroupCreateRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = create_entity_group(
            db,
            display_name=request.display_name,
            description=request.description,
            members=request.members,
        )
        record_audit_log(
            db,
            action="entity_group_created",
            actor=actor,
            target_type="entity",
            target_id=result["entity"]["id"],
            entity_type="group",
            entity_id=result["entity"]["id"],
            summary=f"Created local group {result['entity']['display_name']}.",
            metadata={"member_count": len(result["entity"]["members"])},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/groups/corpus")
def build_group_corpus_endpoint(
    request: EntityGroupCorpusRequest,
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = build_entity_group_corpus(
            db,
            clients,
            display_name=request.display_name,
            description=request.description,
            members=request.members,
            continue_on_error=request.continue_on_error,
        )
        record_audit_log(
            db,
            action="entity_group_corpus_built",
            actor=actor,
            target_type="entity",
            target_id=result["entity"]["id"],
            entity_type="group",
            entity_id=result["entity"]["id"],
            summary=f"Built local group corpus for {result['entity']['display_name']}.",
            metadata={
                "member_count": result["member_count"],
                "succeeded_count": result["succeeded_count"],
                "failed_count": result["failed_count"],
                "total_imported_count": result["total_imported_count"],
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/corpus/import")
async def import_corpus_manifest_endpoint(
    file: UploadFile = File(),
    continue_on_error: bool = Form(default=True),
    default_limit: int = Form(default=25, ge=1, le=200),
    default_year_from: int | None = Form(default=None),
    default_year_to: int | None = Form(default=None),
    db: Session = Depends(get_db),
    clients: SourceClients = Depends(get_source_clients),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        requests = parse_entity_manifest(
            await file.read(),
            filename=file.filename or "entities.csv",
            default_limit=default_limit,
            default_year_from=default_year_from,
            default_year_to=default_year_to,
        )
        result = _build_batch_corpus(db, clients, requests, continue_on_error=continue_on_error, actor=actor)
        result["source_filename"] = file.filename
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{entity_type}/{entity_id}/profile")
def entity_profile_endpoint(entity_type: str, entity_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return entity_profile(db, entity_type, entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{entity_type}/{entity_id}/breakdown")
def entity_breakdown_endpoint(
    entity_type: str,
    entity_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    min_papers: int = Query(default=1, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return entity_breakdown(db, entity_type, entity_id, limit=limit, min_papers=min_papers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/review-queue")
def queue_review_tasks_endpoint(
    request: EntityAuditQueueRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = queue_entity_review_tasks(db, request.entity_type, request.entity_id, request.priority)
        record_audit_log(
            db,
            action="entity_review_queue_created",
            actor=actor,
            target_type="entity",
            target_id=request.entity_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            summary=f"Queued {result['created_review_tasks']} review tasks for entity.",
            metadata={"priority": request.priority, "created_review_tasks": result["created_review_tasks"]},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _build_batch_corpus(
    db: Session,
    clients: SourceClients,
    requests: list[EntityCorpusRequest],
    *,
    continue_on_error: bool,
    actor: str | None,
) -> dict:
    items = []
    errors = []
    total_imported = 0
    for index, item in enumerate(requests):
        try:
            result = build_entity_corpus(db, clients, item)
            entity = result["entity"]
            total_imported += result["imported_count"]
            record_audit_log(
                db,
                action="entity_corpus_built",
                actor=actor,
                target_type="entity",
                target_id=entity["id"],
                entity_type=entity["entity_type"],
                entity_id=entity["id"],
                summary=f"Built corpus for {entity['entity_type']} {entity['display_name']} from batch.",
                metadata={
                    "batch_index": index,
                    "query": item.query,
                    "openalex_id": entity.get("openalex_id"),
                    "limit": item.limit,
                    "year_from": item.year_from,
                    "year_to": item.year_to,
                    "imported_count": result["imported_count"],
                },
            )
            items.append({"index": index, "status": "succeeded", **result})
        except Exception as exc:
            db.rollback()
            error = {
                "index": index,
                "status": "failed",
                "entity_type": item.entity_type,
                "query": item.query,
                "openalex_id": item.openalex_id,
                "error": str(exc),
            }
            errors.append(error)
            if not continue_on_error:
                raise HTTPException(status_code=422, detail={"message": "Batch corpus build failed.", "error": error}) from exc
    return {
        "items": items,
        "errors": errors,
        "item_count": len(requests),
        "succeeded_count": len(items),
        "failed_count": len(errors),
        "total_imported_count": total_imported,
        "conclusion_boundary": "批量建库只建立本地论文集合和覆盖率基础，不能直接认定论文、作者、实验室或机构造假。",
    }
