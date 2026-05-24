from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.services.audit_log import list_audit_logs

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])


@router.get("")
def list_audit_log_endpoint(
    action: str | None = None,
    actor: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    entity_type: str | None = Query(default=None, pattern="^(author|institution|group)$"),
    entity_id: str | None = None,
    paper_id: str | None = None,
    artifact_id: str | None = None,
    signal_id: str | None = None,
    task_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    return list_audit_logs(
        db,
        action=action,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        entity_type=entity_type,
        entity_id=entity_id,
        paper_id=paper_id,
        artifact_id=artifact_id,
        signal_id=signal_id,
        task_id=task_id,
        limit=limit,
        offset=offset,
    )
