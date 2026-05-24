from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gengscope_api.db.models import AuditLog


def record_audit_log(
    db: Session,
    *,
    action: str,
    actor: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    paper_id: str | None = None,
    artifact_id: str | None = None,
    signal_id: str | None = None,
    task_id: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        action=action,
        actor=_clean_actor(actor),
        target_type=target_type,
        target_id=target_id,
        entity_type=entity_type,
        entity_id=entity_id,
        paper_id=paper_id,
        artifact_id=artifact_id,
        signal_id=signal_id,
        task_id=task_id,
        summary=summary,
        metadata_json=metadata,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def list_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    actor: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    paper_id: str | None = None,
    artifact_id: str | None = None,
    signal_id: str | None = None,
    task_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc())
    filters = {
        AuditLog.action: action,
        AuditLog.actor: actor,
        AuditLog.target_type: target_type,
        AuditLog.target_id: target_id,
        AuditLog.entity_type: entity_type,
        AuditLog.entity_id: entity_id,
        AuditLog.paper_id: paper_id,
        AuditLog.artifact_id: artifact_id,
        AuditLog.signal_id: signal_id,
        AuditLog.task_id: task_id,
    }
    for column, value in filters.items():
        if value:
            statement = statement.where(column == value)

    logs = db.scalars(statement).all()
    page = logs[offset : offset + limit]
    return {
        "items": [audit_log_dict(log) for log in page],
        "total": len(logs),
        "limit": limit,
        "offset": offset,
        "conclusion_boundary": "操作日志只记录系统动作和人工复核轨迹，不能作为论文、作者、实验室或机构的事实认定。",
    }


def audit_log_dict(log: AuditLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "action": log.action,
        "actor": log.actor,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "paper_id": log.paper_id,
        "artifact_id": log.artifact_id,
        "signal_id": log.signal_id,
        "task_id": log.task_id,
        "summary": log.summary,
        "metadata": log.metadata_json,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def _clean_actor(actor: str | None) -> str | None:
    if actor is None:
        return None
    cleaned = actor.strip()
    return cleaned[:120] if cleaned else None
