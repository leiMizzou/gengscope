from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.services.signals import list_signals

router = APIRouter(tags=["signals"])


@router.get("/api/signals")
def list_signals_endpoint(
    entity_type: str | None = Query(default=None, pattern="^(author|institution|group)$"),
    entity_id: str | None = None,
    status: str = Query(default="visible"),
    signal_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return list_signals(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            signal_type=signal_type,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/entities/{entity_type}/{entity_id}/signals")
def list_entity_signals_endpoint(
    entity_type: str,
    entity_id: str,
    status: str = Query(default="visible"),
    signal_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return list_signals(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            signal_type=signal_type,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
