from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.schemas.audits import EntityAuditCycleBatchRequest, EntityAuditCycleRequest
from gengscope_api.schemas.entities import EntityCorpusRequest
from gengscope_api.schemas.jobs import EntityAuditScheduleRequest, JobScheduleStatusRequest
from gengscope_api.services.jobs import (
    create_entity_audit_schedule,
    enqueue_due_scheduled_jobs,
    enqueue_entity_corpus_job,
    enqueue_entity_audit_cycle_job,
    get_job,
    get_job_schedule,
    list_job_schedules,
    list_jobs,
    process_job,
    retry_job,
    update_job_schedule_status,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs_endpoint(
    status: str = Query(default="all", pattern="^(all|queued|running|succeeded|failed|cancelled)$"),
    job_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    return list_jobs(db, status=status, job_type=job_type, limit=limit, offset=offset)


@router.get("/schedules")
def list_job_schedules_endpoint(
    status: str = Query(default="all", pattern="^(all|active|paused|cancelled)$"),
    job_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    return list_job_schedules(db, status=status, job_type=job_type, limit=limit, offset=offset)


@router.post("/schedules/entity-cycle")
def create_entity_cycle_schedule_endpoint(
    request: EntityAuditScheduleRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        return create_entity_audit_schedule(
            db,
            name=request.name,
            payload=request.job.model_dump(),
            interval_seconds=request.interval_seconds,
            start_at=request.start_at,
            run_immediately=request.run_immediately,
            max_attempts=request.max_attempts,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/schedules/run-due")
def run_due_schedules_endpoint(db: Session = Depends(get_db)) -> dict:
    return enqueue_due_scheduled_jobs(db)


@router.get("/schedules/{schedule_id}")
def get_job_schedule_endpoint(schedule_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return get_job_schedule(db, schedule_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/schedules/{schedule_id}/status")
def update_job_schedule_status_endpoint(
    schedule_id: str,
    request: JobScheduleStatusRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        return update_job_schedule_status(db, schedule_id, status=request.status, actor=actor)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{job_id}")
def get_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return get_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/entity-cycle")
def enqueue_entity_cycle_job_endpoint(
    request: EntityAuditCycleRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    return enqueue_entity_audit_cycle_job(
        db,
        payload=request.model_dump(),
        actor=actor,
    )


@router.post("/entity-corpus")
def enqueue_entity_corpus_job_endpoint(
    request: EntityCorpusRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    return enqueue_entity_corpus_job(
        db,
        payload=request.model_dump(),
        actor=actor,
    )


@router.post("/entity-cycle/batch")
def enqueue_entity_cycle_batch_job_endpoint(
    request: EntityAuditCycleBatchRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    jobs = [
        enqueue_entity_audit_cycle_job(
            db,
            payload=item.model_dump(),
            actor=actor,
        )
        for item in request.items
    ]
    return {
        "items": jobs,
        "job_count": len(jobs),
        "conclusion_boundary": "批量任务只是把实体审计 workflow 放入后台执行队列，任务成功不代表任何科研完整性事实结论。",
    }


@router.post("/{job_id}/run")
def run_job_now_endpoint(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return process_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{job_id}/retry")
def retry_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return retry_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
