from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.schemas.review import ReviewDecisionRequest
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.review import decide_review_task, list_review_tasks

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/tasks")
def list_review_tasks_endpoint(
    status: str = Query(default="open", pattern="^(open|closed|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    return list_review_tasks(db, status=status, limit=limit, offset=offset)


@router.post("/tasks/{task_id}/decision")
def decide_review_task_endpoint(
    task_id: str,
    request: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = decide_review_task(
            db,
            task_id=task_id,
            decision=request.decision,
            reviewer_note=request.reviewer_note,
            assigned_to=request.assigned_to,
        )
        record_audit_log(
            db,
            action="review_task_decided",
            actor=actor or request.assigned_to,
            target_type="review_task",
            target_id=task_id,
            paper_id=result["paper"]["id"] if result.get("paper") else None,
            signal_id=result["signal"]["id"] if result.get("signal") else None,
            task_id=task_id,
            summary=f"Review task decided as {request.decision}.",
            metadata={"decision": request.decision, "reviewer_note": request.reviewer_note, "assigned_to": request.assigned_to},
        )
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
