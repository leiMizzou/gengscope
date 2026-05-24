from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from gengscope_api.db.models import AlgorithmicSignal, ReportSnapshot, ReviewTask
from gengscope_api.services.entities import entity_profile, list_entity_papers
from gengscope_api.services.signals import list_signals

REPORT_CONCLUSION_BOUNDARY = (
    "本报告汇总已索引元数据、材料审计信号、公开状态和人工复核任务，不能据此直接认定论文、作者、实验室或机构造假。"
)
REPORT_ARCHIVE_CONCLUSION_BOUNDARY = (
    "报告归档是本地系统在某一时间点的可复核快照，用于追踪审计过程，不能作为论文、作者、实验室或机构的事实认定。"
)
REPORT_FORMATS = {"json", "markdown"}


def build_entity_report(db: Session, *, entity_type: str, entity_id: str) -> dict[str, Any]:
    profile = entity_profile(db, entity_type, entity_id)
    signals = list_signals(db, entity_type=entity_type, entity_id=entity_id, status="visible", limit=200)
    entity_task_items = _open_review_tasks(db, entity_type, entity_id)
    return {
        "entity": profile["entity"],
        "profile": profile,
        "signals": signals,
        "open_review_tasks": {
            "items": entity_task_items,
            "total": len(entity_task_items),
        },
        "conclusion_boundary": REPORT_CONCLUSION_BOUNDARY,
    }


def entity_report(db: Session, *, entity_type: str, entity_id: str, format: str = "json") -> dict[str, Any] | str:
    report = build_entity_report(db, entity_type=entity_type, entity_id=entity_id)
    if format == "markdown":
        return _markdown_report(report)
    if format != "json":
        raise ValueError("format must be 'json' or 'markdown'")
    return report


def archive_entity_report(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    formats: list[str] | tuple[str, ...] | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    selected_formats = _normalize_formats(formats)
    report = build_entity_report(db, entity_type=entity_type, entity_id=entity_id)
    snapshots: list[ReportSnapshot] = []
    for report_format in selected_formats:
        content_text = _markdown_report(report) if report_format == "markdown" else None
        snapshot = ReportSnapshot(
            entity_type=report["entity"]["entity_type"],
            entity_id=report["entity"]["id"],
            entity_display_name=report["entity"]["display_name"],
            report_format=report_format,
            content_json=report,
            content_text=content_text,
            content_sha256=_content_sha256(report_format, report, content_text),
            actor=_clean_actor(actor),
        )
        db.add(snapshot)
        snapshots.append(snapshot)
    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)
    return {
        "items": [report_snapshot_dict(snapshot) for snapshot in snapshots],
        "total": len(snapshots),
        "entity": report["entity"],
        "conclusion_boundary": REPORT_ARCHIVE_CONCLUSION_BOUNDARY,
    }


def list_report_snapshots(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    report_format: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    statement = select(ReportSnapshot).order_by(ReportSnapshot.created_at.desc())
    if entity_type:
        statement = statement.where(ReportSnapshot.entity_type == entity_type)
    if entity_id:
        statement = statement.where(ReportSnapshot.entity_id == entity_id)
    if report_format and report_format != "all":
        if report_format not in REPORT_FORMATS:
            raise ValueError("format must be 'json', 'markdown' or 'all'")
        statement = statement.where(ReportSnapshot.report_format == report_format)
    snapshots = db.scalars(statement).all()
    page = snapshots[offset : offset + limit]
    return {
        "items": [report_snapshot_dict(snapshot) for snapshot in page],
        "total": len(snapshots),
        "limit": limit,
        "offset": offset,
        "conclusion_boundary": REPORT_ARCHIVE_CONCLUSION_BOUNDARY,
    }


def prune_report_snapshots(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    report_format: str | None = None,
    keep_latest: int | None = 20,
    older_than_days: int | None = 180,
    dry_run: bool = True,
) -> dict[str, Any]:
    if keep_latest is not None and keep_latest < 0:
        raise ValueError("keep_latest must be greater than or equal to 0")
    if older_than_days is not None and older_than_days < 1:
        raise ValueError("older_than_days must be greater than or equal to 1")
    if keep_latest is None and older_than_days is None:
        raise ValueError("keep_latest or older_than_days is required")
    if report_format and report_format != "all" and report_format not in REPORT_FORMATS:
        raise ValueError("format must be 'json', 'markdown' or 'all'")

    statement = select(ReportSnapshot)
    if entity_type:
        statement = statement.where(ReportSnapshot.entity_type == entity_type)
    if entity_id:
        statement = statement.where(ReportSnapshot.entity_id == entity_id)
    if report_format and report_format != "all":
        statement = statement.where(ReportSnapshot.report_format == report_format)
    snapshots = db.scalars(statement).all()
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days) if older_than_days is not None else None

    prunable: list[ReportSnapshot] = []
    for group in _group_snapshots(snapshots).values():
        ordered = sorted(group, key=lambda snapshot: _created_at(snapshot), reverse=True)
        for index, snapshot in enumerate(ordered):
            keep_by_latest = keep_latest is not None and index < keep_latest
            old_enough = cutoff is None or _created_at(snapshot) < cutoff
            beyond_latest = keep_latest is None or not keep_by_latest
            if beyond_latest and old_enough:
                prunable.append(snapshot)

    items = [report_snapshot_dict(snapshot) for snapshot in sorted(prunable, key=lambda snapshot: _created_at(snapshot), reverse=True)]
    if not dry_run:
        for snapshot in prunable:
            db.delete(snapshot)
        db.commit()
    return {
        "items": items,
        "matched_count": len(snapshots),
        "pruned_count": len(prunable),
        "dry_run": dry_run,
        "keep_latest": keep_latest,
        "older_than_days": older_than_days,
        "conclusion_boundary": REPORT_ARCHIVE_CONCLUSION_BOUNDARY,
    }


def get_report_snapshot(db: Session, snapshot_id: str) -> ReportSnapshot:
    snapshot = db.get(ReportSnapshot, snapshot_id)
    if snapshot is None:
        raise LookupError(f"No report snapshot found for id {snapshot_id}")
    return snapshot


def report_snapshot_dict(snapshot: ReportSnapshot, *, include_content: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": snapshot.id,
        "entity_type": snapshot.entity_type,
        "entity_id": snapshot.entity_id,
        "entity_display_name": snapshot.entity_display_name,
        "report_format": snapshot.report_format,
        "content_sha256": snapshot.content_sha256,
        "actor": snapshot.actor,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
    if include_content:
        data["content_json"] = snapshot.content_json
        data["content_text"] = snapshot.content_text
        data["content"] = snapshot.content_text if snapshot.report_format == "markdown" else snapshot.content_json
        data["conclusion_boundary"] = REPORT_ARCHIVE_CONCLUSION_BOUNDARY
    return data


def report_snapshot_markdown(snapshot: ReportSnapshot) -> str:
    if snapshot.content_text:
        return snapshot.content_text
    if snapshot.content_json:
        return _markdown_report(snapshot.content_json)
    raise ValueError("snapshot does not contain markdown-compatible content")


def _markdown_report(report: dict[str, Any]) -> str:
    entity = report["entity"]
    profile = report["profile"]
    signals = report["signals"]
    tasks = report["open_review_tasks"]
    lines = [
        f"# GengScope Entity Report: {entity['display_name']}",
        "",
        "## Profile",
        "",
        f"- Entity type: {entity['entity_type']}",
        f"- Paper count: {profile['paper_count']}",
        f"- Auditable papers: {profile['auditable_paper_count']}",
        f"- Audited papers: {profile['audited_paper_count']}",
        f"- Signal papers: {profile['signal_paper_count']}",
        f"- Priority: {profile['priority']}",
        f"- Summary: {profile['summary']}",
        "",
        "## Signal Counts",
        "",
    ]
    if signals["signal_type_counts"]:
        for signal_type, count in sorted(signals["signal_type_counts"].items()):
            lines.append(f"- {signal_type}: {count}")
    else:
        lines.append("- No visible algorithmic signals indexed.")
    lines.extend(["", "## Open Review Tasks", ""])
    if tasks["items"]:
        for task in tasks["items"][:25]:
            paper = task["paper"] or {}
            signal = task["signal"] or {}
            lines.append(f"- P{task['priority']} {paper.get('title', 'Untitled paper')}: {signal.get('summary', task['task_type'])}")
    else:
        lines.append("- No open review tasks for this entity.")
    lines.extend(["", "## Conclusion Boundary", "", report["conclusion_boundary"]])
    return "\n".join(lines) + "\n"


def _normalize_formats(formats: list[str] | tuple[str, ...] | None) -> list[str]:
    values = list(formats or ["json", "markdown"])
    normalized: list[str] = []
    for value in values:
        report_format = value.strip().lower()
        if report_format not in REPORT_FORMATS:
            raise ValueError("formats must contain only 'json' or 'markdown'")
        if report_format not in normalized:
            normalized.append(report_format)
    if not normalized:
        raise ValueError("formats must contain at least one item")
    return normalized


def _content_sha256(report_format: str, report: dict[str, Any], content_text: str | None) -> str:
    if report_format == "markdown":
        payload = (content_text or "").encode("utf-8")
    else:
        payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _group_snapshots(snapshots: list[ReportSnapshot]) -> dict[tuple[str, str, str], list[ReportSnapshot]]:
    groups: dict[tuple[str, str, str], list[ReportSnapshot]] = {}
    for snapshot in snapshots:
        key = (snapshot.entity_type, snapshot.entity_id, snapshot.report_format)
        groups.setdefault(key, []).append(snapshot)
    return groups


def _created_at(snapshot: ReportSnapshot) -> datetime:
    created_at = snapshot.created_at or datetime.min
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=timezone.utc)
    return created_at


def _clean_actor(actor: str | None) -> str | None:
    if actor is None:
        return None
    cleaned = actor.strip()
    return cleaned[:120] if cleaned else None


def _open_review_tasks(db: Session, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    paper_ids = _entity_paper_ids(db, entity_type, entity_id)
    if not paper_ids:
        return []
    tasks = db.scalars(
        select(ReviewTask)
        .where(ReviewTask.paper_id.in_(paper_ids), ReviewTask.status == "open")
        .options(selectinload(ReviewTask.paper), selectinload(ReviewTask.signal).selectinload(AlgorithmicSignal.artifact))
        .order_by(ReviewTask.priority.desc(), ReviewTask.created_at)
    ).all()
    return [_task_item(task) for task in tasks]


def _entity_paper_ids(db: Session, entity_type: str, entity_id: str) -> set[str]:
    return {paper.id for paper in list_entity_papers(db, entity_type, entity_id)}


def _task_item(task: ReviewTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "paper": {
            "id": task.paper.id,
            "doi": task.paper.doi,
            "title": task.paper.title,
            "journal_name": task.paper.journal_name,
            "publication_year": task.paper.publication_year,
        }
        if task.paper
        else None,
        "signal": {
            "id": task.signal.id,
            "signal_type": task.signal.signal_type,
            "severity": task.signal.severity,
            "status": task.signal.status,
            "summary": task.signal.summary,
        }
        if task.signal
        else None,
    }
