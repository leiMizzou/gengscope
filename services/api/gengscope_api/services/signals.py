from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import false, select
from sqlalchemy.orm import Session, selectinload

from gengscope_api.db.models import AlgorithmicSignal, EvidencePointer
from gengscope_api.services.entities import list_entity_papers


VISIBLE_SIGNAL_STATUSES = {"needs_review", "in_review", "confirmed_signal", "promoted_to_event"}


def list_signals(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    status: str = "visible",
    signal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    statement = (
        select(AlgorithmicSignal)
        .options(
            selectinload(AlgorithmicSignal.paper),
            selectinload(AlgorithmicSignal.artifact),
            selectinload(AlgorithmicSignal.evidence_pointers).selectinload(EvidencePointer.artifact),
        )
        .order_by(AlgorithmicSignal.created_at.desc())
    )
    if entity_type and entity_id:
        normalized_type = _entity_type(entity_type)
        paper_ids = [paper.id for paper in list_entity_papers(db, normalized_type, entity_id)]
        statement = statement.where(AlgorithmicSignal.paper_id.in_(paper_ids) if paper_ids else false())
    if status == "visible":
        statement = statement.where(AlgorithmicSignal.status.in_(VISIBLE_SIGNAL_STATUSES))
    elif status != "all":
        statement = statement.where(AlgorithmicSignal.status == status)
    if signal_type:
        statement = statement.where(AlgorithmicSignal.signal_type == signal_type)

    unique_signals = _unique(db.scalars(statement).all())
    page = unique_signals[offset : offset + limit]
    return {
        "items": [_signal_dict(signal) for signal in page],
        "total": len(unique_signals),
        "limit": limit,
        "offset": offset,
        "status_counts": dict(Counter(signal.status for signal in unique_signals)),
        "severity_counts": dict(Counter(signal.severity for signal in unique_signals)),
        "signal_type_counts": dict(Counter(signal.signal_type for signal in unique_signals)),
        "conclusion_boundary": "信号列表只汇总公开事件与算法初筛结果，不能直接认定论文、作者、实验室或机构造假。",
    }


def signal_dict(signal: AlgorithmicSignal) -> dict[str, Any]:
    return _signal_dict(signal)


def _signal_dict(signal: AlgorithmicSignal) -> dict[str, Any]:
    paper = signal.paper
    artifact = signal.artifact
    return {
        "id": signal.id,
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "confidence": signal.confidence,
        "analyzer_name": signal.analyzer_name,
        "analyzer_version": signal.analyzer_version,
        "status": signal.status,
        "summary": signal.summary,
        "metrics": signal.metrics_json,
        "paper": {
            "id": paper.id,
            "doi": paper.doi,
            "title": paper.title,
            "journal_name": paper.journal_name,
            "publication_year": paper.publication_year,
            "material_status": paper.material_status,
            "audit_status": paper.audit_status,
        }
        if paper
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
        "evidence": [
            {
                "id": pointer.id,
                "artifact_id": pointer.artifact_id,
                "figure_label": pointer.figure_label,
                "table_label": pointer.table_label,
                "panel_label": pointer.panel_label,
                "column_name": pointer.column_name,
                "row_label": pointer.row_label,
                "evidence_url": pointer.evidence_url,
                "summary": pointer.evidence_summary,
            }
            for pointer in signal.evidence_pointers
        ],
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
        "updated_at": signal.updated_at.isoformat() if signal.updated_at else None,
    }


def _unique(signals: list[AlgorithmicSignal]) -> list[AlgorithmicSignal]:
    seen: set[str] = set()
    unique = []
    for signal in signals:
        if signal.id in seen:
            continue
        unique.append(signal)
        seen.add(signal.id)
    return unique


def _entity_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"author", "institution", "group"}:
        raise ValueError("entity_type must be 'author', 'institution' or 'group'")
    return normalized
