from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.schemas.reports import EntityReportArchiveRequest, ReportArchivePruneRequest
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.reports import (
    archive_entity_report,
    entity_report,
    get_report_snapshot,
    list_report_snapshots,
    prune_report_snapshots,
    report_snapshot_dict,
    report_snapshot_markdown,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/entity")
def entity_report_endpoint(
    entity_type: str = Query(pattern="^(author|institution|group)$"),
    entity_id: str = Query(),
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
):
    try:
        report = entity_report(db, entity_type=entity_type, entity_id=entity_id, format=format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit_log(
        db,
        action="entity_report_exported",
        actor=actor,
        target_type="entity",
        target_id=entity_id,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=f"Exported {format} entity report.",
        metadata={"format": format},
    )
    if format == "markdown":
        return PlainTextResponse(str(report), media_type="text/markdown; charset=utf-8")
    return report


@router.post("/entity/archive")
def archive_entity_report_endpoint(
    request: EntityReportArchiveRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = archive_entity_report(
            db,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            formats=request.formats,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit_log(
        db,
        action="entity_report_archived",
        actor=actor,
        target_type="entity",
        target_id=request.entity_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        summary=f"Archived {len(result['items'])} entity report snapshot(s).",
        metadata={
            "snapshot_ids": [item["id"] for item in result["items"]],
            "formats": [item["report_format"] for item in result["items"]],
        },
    )
    return result


@router.get("/archive")
def list_report_archive_endpoint(
    entity_type: str | None = Query(default=None, pattern="^(author|institution|group)$"),
    entity_id: str | None = None,
    format: str = Query(default="all", pattern="^(all|json|markdown)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return list_report_snapshots(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            report_format=format,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/archive/prune")
def prune_report_archive_endpoint(
    request: ReportArchivePruneRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = prune_report_snapshots(
            db,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            report_format=request.format,
            keep_latest=request.keep_latest,
            older_than_days=request.older_than_days,
            dry_run=request.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit_log(
        db,
        action="entity_report_archive_prune_planned" if request.dry_run else "entity_report_archive_pruned",
        actor=actor,
        target_type="report_snapshot",
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        summary=f"{'Planned pruning' if request.dry_run else 'Pruned'} {result['pruned_count']} report snapshot(s).",
        metadata={
            "snapshot_ids": [item["id"] for item in result["items"]],
            "pruned_count": result["pruned_count"],
            "dry_run": request.dry_run,
            "keep_latest": request.keep_latest,
            "older_than_days": request.older_than_days,
            "format": request.format,
        },
    )
    return result


@router.get("/archive/{snapshot_id}")
def get_report_archive_endpoint(
    snapshot_id: str,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
):
    try:
        snapshot = get_report_snapshot(db, snapshot_id)
        if format == "markdown":
            content = report_snapshot_markdown(snapshot)
        else:
            content = report_snapshot_dict(snapshot, include_content=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit_log(
        db,
        action="entity_report_archive_read",
        actor=actor,
        target_type="report_snapshot",
        target_id=snapshot_id,
        entity_type=snapshot.entity_type,
        entity_id=snapshot.entity_id,
        summary=f"Read {format} report snapshot.",
        metadata={"format": format, "content_sha256": snapshot.content_sha256},
    )
    if format == "markdown":
        return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")
    return content
