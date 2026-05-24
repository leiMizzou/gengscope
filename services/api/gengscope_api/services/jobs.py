from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gengscope_api.db.models import JobRun, JobSchedule
from gengscope_api.schemas.entities import EntityCorpusRequest
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.entities import build_entity_corpus
from gengscope_api.services.entity_cycle import run_entity_audit_cycle
from gengscope_api.services.import_paper import default_source_clients


JOB_ENTITY_AUDIT_CYCLE = "entity_audit_cycle"
JOB_ENTITY_CORPUS_BUILD = "entity_corpus_build"
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
SCHEDULE_TERMINAL_STATUSES = {"cancelled"}


def enqueue_entity_audit_cycle_job(
    db: Session,
    *,
    payload: dict[str, Any],
    actor: str | None = None,
    max_attempts: int = 1,
) -> dict[str, Any]:
    job = _enqueue_job_run(db, job_type=JOB_ENTITY_AUDIT_CYCLE, payload=payload, actor=actor, max_attempts=max_attempts)
    db.commit()
    db.refresh(job)
    return job_dict(job)


def enqueue_entity_corpus_job(
    db: Session,
    *,
    payload: dict[str, Any],
    actor: str | None = None,
    max_attempts: int = 1,
) -> dict[str, Any]:
    job = _enqueue_job_run(db, job_type=JOB_ENTITY_CORPUS_BUILD, payload=payload, actor=actor, max_attempts=max_attempts)
    db.commit()
    db.refresh(job)
    return job_dict(job)


def get_job(db: Session, job_id: str) -> dict[str, Any]:
    job = db.get(JobRun, job_id)
    if job is None:
        raise LookupError(f"No job found for id {job_id}")
    return job_dict(job)


def list_jobs(
    db: Session,
    *,
    status: str = "all",
    job_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    statement = select(JobRun).order_by(JobRun.queued_at.desc())
    if status != "all":
        statement = statement.where(JobRun.status == status)
    if job_type:
        statement = statement.where(JobRun.job_type == job_type)
    jobs = db.scalars(statement).all()
    page = jobs[offset : offset + limit]
    return {
        "items": [job_dict(job) for job in page],
        "total": len(jobs),
        "limit": limit,
        "offset": offset,
    }


def create_entity_audit_schedule(
    db: Session,
    *,
    name: str | None,
    payload: dict[str, Any],
    interval_seconds: int,
    start_at: datetime | None = None,
    run_immediately: bool = False,
    max_attempts: int = 1,
    actor: str | None = None,
) -> dict[str, Any]:
    if interval_seconds < 60:
        raise ValueError("interval_seconds must be at least 60")
    now = datetime.now(timezone.utc)
    next_run_at = now if run_immediately else _ensure_aware(start_at) if start_at else now + timedelta(seconds=interval_seconds)
    schedule = JobSchedule(
        name=(name or _schedule_name(payload))[:160],
        job_type=JOB_ENTITY_AUDIT_CYCLE,
        status="active",
        actor=_clean_actor(actor),
        payload_json=payload,
        interval_seconds=interval_seconds,
        max_attempts=max(1, max_attempts),
        next_run_at=next_run_at,
    )
    db.add(schedule)
    db.flush()
    record_audit_log(
        db,
        action="job_schedule_created",
        actor=actor,
        target_type="job_schedule",
        target_id=schedule.id,
        entity_type=payload.get("entity_type"),
        entity_id=payload.get("entity_id"),
        summary=f"Created {JOB_ENTITY_AUDIT_CYCLE} schedule.",
        metadata={"interval_seconds": interval_seconds, "next_run_at": next_run_at.isoformat(), "max_attempts": max_attempts},
        commit=False,
    )
    if run_immediately:
        job = _enqueue_job_run(db, job_type=JOB_ENTITY_AUDIT_CYCLE, payload=payload, actor=actor, max_attempts=schedule.max_attempts)
        schedule.last_run_at = now
        schedule.last_job_id = job.id
        schedule.next_run_at = now + timedelta(seconds=interval_seconds)
        record_audit_log(
            db,
            action="job_schedule_due_enqueued",
            actor=actor,
            target_type="job_schedule",
            target_id=schedule.id,
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            summary=f"Schedule enqueued {JOB_ENTITY_AUDIT_CYCLE} job.",
            metadata={"job_id": job.id, "next_run_at": schedule.next_run_at.isoformat()},
            commit=False,
        )
    db.commit()
    db.refresh(schedule)
    return schedule_dict(schedule)


def list_job_schedules(
    db: Session,
    *,
    status: str = "all",
    job_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    statement = select(JobSchedule).order_by(JobSchedule.next_run_at)
    if status != "all":
        statement = statement.where(JobSchedule.status == status)
    if job_type:
        statement = statement.where(JobSchedule.job_type == job_type)
    schedules = db.scalars(statement).all()
    page = schedules[offset : offset + limit]
    return {
        "items": [schedule_dict(schedule) for schedule in page],
        "total": len(schedules),
        "limit": limit,
        "offset": offset,
        "conclusion_boundary": "周期调度只会按配置把本地审计任务加入队列，任务产生的信号仍需人工复核，不能作为事实结论。",
    }


def get_job_schedule(db: Session, schedule_id: str) -> dict[str, Any]:
    schedule = db.get(JobSchedule, schedule_id)
    if schedule is None:
        raise LookupError(f"No job schedule found for id {schedule_id}")
    return schedule_dict(schedule)


def update_job_schedule_status(db: Session, schedule_id: str, *, status: str, actor: str | None = None) -> dict[str, Any]:
    if status not in {"active", "paused", "cancelled"}:
        raise ValueError("status must be active, paused or cancelled")
    schedule = db.get(JobSchedule, schedule_id)
    if schedule is None:
        raise LookupError(f"No job schedule found for id {schedule_id}")
    if schedule.status in SCHEDULE_TERMINAL_STATUSES and status != schedule.status:
        raise ValueError(f"Schedule {schedule.id} cannot move from {schedule.status} to {status}")
    schedule.status = status
    if status == "active" and _ensure_aware(schedule.next_run_at) < datetime.now(timezone.utc):
        schedule.next_run_at = datetime.now(timezone.utc)
    record_audit_log(
        db,
        action="job_schedule_status_updated",
        actor=actor,
        target_type="job_schedule",
        target_id=schedule.id,
        entity_type=schedule.payload_json.get("entity_type"),
        entity_id=schedule.payload_json.get("entity_id"),
        summary=f"Updated schedule status to {status}.",
        metadata={"status": status},
        commit=False,
    )
    db.commit()
    db.refresh(schedule)
    return schedule_dict(schedule)


def enqueue_due_scheduled_jobs(db: Session, *, now: datetime | None = None, limit: int = 25) -> dict[str, Any]:
    current_time = _ensure_aware(now) if now else datetime.now(timezone.utc)
    schedules = db.scalars(
        select(JobSchedule)
        .where(JobSchedule.status == "active", JobSchedule.next_run_at <= current_time)
        .order_by(JobSchedule.next_run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    enqueued: list[dict[str, Any]] = []
    for schedule in schedules:
        job = _enqueue_job_run(db, job_type=schedule.job_type, payload=schedule.payload_json, actor=schedule.actor, max_attempts=schedule.max_attempts)
        schedule.last_run_at = current_time
        schedule.last_job_id = job.id
        schedule.next_run_at = _next_run_after(current_time, schedule.interval_seconds)
        record_audit_log(
            db,
            action="job_schedule_due_enqueued",
            actor=schedule.actor,
            target_type="job_schedule",
            target_id=schedule.id,
            entity_type=schedule.payload_json.get("entity_type"),
            entity_id=schedule.payload_json.get("entity_id"),
            summary=f"Schedule enqueued {schedule.job_type} job.",
            metadata={"job_id": job.id, "next_run_at": schedule.next_run_at.isoformat()},
            commit=False,
        )
        enqueued.append({"schedule": schedule_dict(schedule), "job": job_dict(job)})
    if schedules:
        db.commit()
    return {
        "items": enqueued,
        "enqueued_count": len(enqueued),
        "checked_at": current_time.isoformat(),
        "conclusion_boundary": "周期调度只是把到期 workflow 加入后台任务队列，不代表任何科研完整性事实结论。",
    }


def process_next_job(db: Session) -> dict[str, Any] | None:
    job = db.scalar(
        select(JobRun)
        .where(JobRun.status == "queued", JobRun.attempts < JobRun.max_attempts)
        .order_by(JobRun.queued_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    return process_job(db, job.id)


def process_job(db: Session, job_id: str) -> dict[str, Any]:
    job = db.scalar(select(JobRun).where(JobRun.id == job_id).with_for_update())
    if job is None:
        raise LookupError(f"No job found for id {job_id}")
    if job.status in TERMINAL_STATUSES:
        return job_dict(job)
    if job.status not in {"queued", "failed"}:
        raise ValueError(f"Job {job.id} is not runnable from status {job.status}")
    if job.attempts >= job.max_attempts:
        raise ValueError(f"Job {job.id} has no attempts remaining")

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.finished_at = None
    job.error_message = None
    job.attempts += 1
    db.commit()

    try:
        result = _run_job(db, job)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        record_audit_log(
            db,
            action="job_failed",
            actor=job.actor,
            target_type="job",
            target_id=job.id,
            entity_type=job.payload_json.get("entity_type"),
            entity_id=job.payload_json.get("entity_id"),
            summary=f"Job {job.job_type} failed.",
            metadata={"error": job.error_message, "attempts": job.attempts},
            commit=False,
        )
        db.commit()
        db.refresh(job)
        return job_dict(job)

    job.status = "succeeded"
    job.result_json = result
    job.finished_at = datetime.now(timezone.utc)
    record_audit_log(
        db,
        action="job_succeeded",
        actor=job.actor,
        target_type="job",
        target_id=job.id,
        entity_type=job.payload_json.get("entity_type"),
        entity_id=job.payload_json.get("entity_id"),
        summary=f"Job {job.job_type} succeeded.",
        metadata={"attempts": job.attempts},
        commit=False,
    )
    db.commit()
    db.refresh(job)
    return job_dict(job)


def requeue_stale_jobs(db: Session, *, stale_after_seconds: float) -> dict[str, int]:
    if stale_after_seconds <= 0:
        return {"requeued": 0, "failed": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    jobs = db.scalars(
        select(JobRun)
        .where(JobRun.status == "running", JobRun.started_at.is_not(None), JobRun.started_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    requeued = 0
    failed = 0
    for job in jobs:
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.error_message = "Job marked failed after stale running state."
            job.finished_at = datetime.now(timezone.utc)
            failed += 1
            record_audit_log(
                db,
                action="job_failed",
                actor=job.actor,
                target_type="job",
                target_id=job.id,
                entity_type=job.payload_json.get("entity_type"),
                entity_id=job.payload_json.get("entity_id"),
                summary=f"Job {job.job_type} failed after becoming stale.",
                metadata={"attempts": job.attempts, "stale_after_seconds": stale_after_seconds},
                commit=False,
            )
            continue
        job.status = "queued"
        job.started_at = None
        job.finished_at = None
        job.error_message = "Previous run became stale and was requeued."
        requeued += 1
        record_audit_log(
            db,
            action="job_requeued",
            actor=job.actor,
            target_type="job",
            target_id=job.id,
            entity_type=job.payload_json.get("entity_type"),
            entity_id=job.payload_json.get("entity_id"),
            summary=f"Job {job.job_type} was requeued after becoming stale.",
            metadata={"attempts": job.attempts, "stale_after_seconds": stale_after_seconds},
            commit=False,
        )
    if jobs:
        db.commit()
    return {"requeued": requeued, "failed": failed}


def retry_job(db: Session, job_id: str) -> dict[str, Any]:
    job = db.get(JobRun, job_id)
    if job is None:
        raise LookupError(f"No job found for id {job_id}")
    if job.status != "failed":
        raise ValueError(f"Only failed jobs can be retried; current status is {job.status}")
    job.status = "queued"
    if job.attempts >= job.max_attempts:
        job.max_attempts = job.attempts + 1
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return job_dict(job)


def schedule_dict(schedule: JobSchedule) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "name": schedule.name,
        "job_type": schedule.job_type,
        "status": schedule.status,
        "actor": schedule.actor,
        "payload": schedule.payload_json,
        "interval_seconds": schedule.interval_seconds,
        "max_attempts": schedule.max_attempts,
        "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        "last_job_id": schedule.last_job_id,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
    }


def job_dict(job: JobRun) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "actor": job.actor,
        "payload": job.payload_json,
        "result": job.result_json,
        "error_message": job.error_message,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _run_job(db: Session, job: JobRun) -> dict[str, Any]:
    if job.job_type == JOB_ENTITY_AUDIT_CYCLE:
        payload = job.payload_json
        return run_entity_audit_cycle(
            db,
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            discover_artifacts=payload.get("discover_artifacts", True),
            inspect_landing_pages=payload.get("inspect_landing_pages", False),
            queue_review_tasks=payload.get("queue_review_tasks", True),
            run_metadata=payload.get("run_metadata_audit", True),
            min_cluster_size=payload.get("min_cluster_size", 5),
            min_signal_rate_audited_count=payload.get("min_signal_rate_audited_count", 2),
            signal_rate_threshold=payload.get("signal_rate_threshold", 0.5),
            public_event_rate_threshold=payload.get("public_event_rate_threshold", 0.2),
            priority=payload.get("priority", 6),
        )
    if job.job_type == JOB_ENTITY_CORPUS_BUILD:
        payload = job.payload_json
        request = EntityCorpusRequest(**payload)
        return build_entity_corpus(db, default_source_clients(), request)
    raise ValueError(f"Unsupported job_type: {job.job_type}")


def _clean_actor(actor: str | None) -> str | None:
    if actor is None:
        return None
    cleaned = actor.strip()
    return cleaned[:120] if cleaned else None


def _enqueue_job_run(
    db: Session,
    *,
    job_type: str,
    payload: dict[str, Any],
    actor: str | None = None,
    max_attempts: int = 1,
) -> JobRun:
    job = JobRun(
        job_type=job_type,
        status="queued",
        actor=_clean_actor(actor),
        payload_json=payload,
        max_attempts=max(1, max_attempts),
    )
    db.add(job)
    db.flush()
    record_audit_log(
        db,
        action="job_enqueued",
        actor=actor,
        target_type="job",
        target_id=job.id,
        entity_type=payload.get("entity_type"),
        entity_id=payload.get("entity_id"),
        summary=f"Enqueued {job_type} job.",
        metadata={"job_type": job.job_type},
        commit=False,
    )
    return job


def _schedule_name(payload: dict[str, Any]) -> str:
    return f"{payload.get('entity_type', 'entity')}:{payload.get('entity_id', 'unknown')} audit cycle"


def _ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _next_run_after(now: datetime, interval_seconds: int) -> datetime:
    return now + timedelta(seconds=max(60, interval_seconds))
