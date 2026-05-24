from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from gengscope_api.config import get_settings
from gengscope_api.db.models import Base
from gengscope_api.db.session import get_db

router = APIRouter()

REQUIRED_TABLES = frozenset(Base.metadata.tables.keys())


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str | list[str]]:
    try:
        db.execute(text("select 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}") from exc
    try:
        missing_tables = _missing_required_tables(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database schema not ready: {exc}") from exc
    if missing_tables:
        raise HTTPException(status_code=503, detail=f"database schema missing tables: {', '.join(missing_tables)}")
    try:
        _check_artifact_storage_writable(get_settings().artifact_storage_dir)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"artifact storage not writable: {exc}") from exc
    return {
        "status": "ready",
        "database": "ok",
        "required_tables": "ok",
        "artifact_storage": "ok",
    }


def _missing_required_tables(db: Session) -> list[str]:
    table_names = set(inspect(db.bind).get_table_names()) if db.bind is not None else set()
    return sorted(REQUIRED_TABLES - table_names)


def _check_artifact_storage_writable(storage_dir: str) -> None:
    root = Path(storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f".gengscope-ready-{uuid4().hex}"
    target.write_text("ok", encoding="utf-8")
    target.unlink()
