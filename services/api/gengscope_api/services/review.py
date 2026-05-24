from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gengscope_api.db.models import AlgorithmicSignal, Paper, ReviewTask


FINAL_DECISIONS = {"confirmed_signal", "false_positive", "not_actionable"}


def list_review_tasks(db: Session, status: str = "open", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    statement = (
        select(ReviewTask)
        .options(selectinload(ReviewTask.paper), selectinload(ReviewTask.signal).selectinload(AlgorithmicSignal.artifact))
        .order_by(ReviewTask.priority.desc(), ReviewTask.created_at)
    )
    if status != "all":
        statement = statement.where(ReviewTask.status == status)
    total = len(db.scalars(statement).all())
    tasks = db.scalars(statement.offset(offset).limit(limit)).all()
    return {"items": [_task_dict(task) for task in tasks], "total": total, "limit": limit, "offset": offset}


def decide_review_task(
    db: Session,
    *,
    task_id: str,
    decision: str,
    reviewer_note: str | None = None,
    assigned_to: str | None = None,
) -> dict[str, Any]:
    task = db.get(
        ReviewTask,
        task_id,
        options=[selectinload(ReviewTask.paper), selectinload(ReviewTask.signal).selectinload(AlgorithmicSignal.artifact)],
    )
    if task is None:
        raise LookupError(f"No review task found for id {task_id}")
    task.decision = decision
    task.reviewer_note = reviewer_note
    task.assigned_to = assigned_to or task.assigned_to
    if decision in FINAL_DECISIONS:
        task.status = "closed"
        task.decided_at = datetime.now(timezone.utc)
    else:
        task.status = "open"

    if task.signal:
        task.signal.status = "in_review" if decision == "needs_more_evidence" else decision

    paper = task.paper or db.get(Paper, task.paper_id)
    if paper is not None:
        other_open_task = db.scalar(
            select(ReviewTask).where(
                ReviewTask.paper_id == paper.id,
                ReviewTask.id != task.id,
                ReviewTask.status == "open",
            )
        )
        paper.audit_status = "in_review" if decision == "needs_more_evidence" or other_open_task is not None else "reviewed"

    db.commit()
    db.refresh(task)
    return _task_dict(task)


def _task_dict(task: ReviewTask) -> dict[str, Any]:
    paper = task.paper
    signal = task.signal
    artifact = signal.artifact if signal else None
    return {
        "id": task.id,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "decision": task.decision,
        "reviewer_note": task.reviewer_note,
        "assigned_to": task.assigned_to,
        "paper": {
            "id": paper.id,
            "doi": paper.doi,
            "title": paper.title,
            "journal_name": paper.journal_name,
            "publication_year": paper.publication_year,
            "audit_status": paper.audit_status,
        }
        if paper
        else None,
        "signal": {
            "id": signal.id,
            "signal_type": signal.signal_type,
            "severity": signal.severity,
            "status": signal.status,
            "summary": signal.summary,
            "metrics": signal.metrics_json,
        }
        if signal
        else None,
        "artifact": {
            "id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "source_url": artifact.source_url,
            "filename": artifact.filename,
            "storage_uri": artifact.storage_uri,
        }
        if artifact
        else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "decided_at": task.decided_at.isoformat() if task.decided_at else None,
    }
