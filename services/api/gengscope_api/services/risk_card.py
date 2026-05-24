from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from gengscope_api.db.models import AlgorithmicSignal, EvidencePointer, IntegrityEvent, Paper
from gengscope_api.services.doi import normalize_doi


OFFICIAL_PRECEDENCE = [
    ("official_retraction", "retracted"),
    ("official_correction", "corrected"),
    ("official_expression_of_concern", "expression_of_concern"),
]
PUBLISHER_PRECEDENCE = [
    ("official_retraction", "retraction"),
    ("official_correction", "correction"),
    ("official_expression_of_concern", "expression_of_concern"),
    ("publisher_notice", "editor_note"),
]
VISIBLE_SIGNAL_STATUSES = {"needs_review", "in_review", "confirmed_signal", "promoted_to_event"}


def risk_card_for_doi(db: Session, doi: str) -> dict[str, Any]:
    paper = _paper_by_doi(db, doi)
    if paper is None:
        raise LookupError(f"No paper found for DOI {normalize_doi(doi)}")
    return risk_card_for_paper(paper)


def risk_card_for_paper(paper: Paper) -> dict[str, Any]:
    events = list(paper.events)
    signals = [signal for signal in paper.algorithmic_signals if signal.status in VISIBLE_SIGNAL_STATUSES]
    official_status = _official_status(events)
    publisher_status = _publisher_status(events)
    institution_status = _institution_status(events)
    public_discussion_count = _count_events(events, {"public_discussion"}, {"pubpeer", "public_discussion"})
    media_report_count = _count_events(events, {"media_report"}, {"media", "news"})
    algorithmic_signal_count = len(signals)
    highest_signal_level = _highest_signal_level(
        official_status=official_status,
        institution_status=institution_status,
        public_discussion_count=public_discussion_count,
        media_report_count=media_report_count,
        algorithmic_signal_count=algorithmic_signal_count,
    )

    return {
        "doi": paper.doi,
        "title": paper.title,
        "official_status": official_status,
        "institution_status": institution_status,
        "publisher_status": publisher_status,
        "public_discussion_count": public_discussion_count,
        "media_report_count": media_report_count,
        "algorithmic_signal_count": algorithmic_signal_count,
        "highest_signal_level": highest_signal_level,
        "summary": _summary(official_status, institution_status, public_discussion_count, media_report_count, algorithmic_signal_count),
        "evidence": _evidence(events, signals),
    }


def agent_summary_for_doi(db: Session, doi: str) -> dict[str, Any]:
    paper = _paper_by_doi(db, doi)
    if paper is None:
        raise LookupError(f"No paper found for DOI {normalize_doi(doi)}")
    card = risk_card_for_paper(paper)
    return {
        "paper": {
            "id": paper.id,
            "doi": paper.doi,
            "title": paper.title,
            "journal_name": paper.journal_name,
            "publication_year": paper.publication_year,
            "landing_page_url": paper.landing_page_url,
        },
        "risk_card": card,
        "events": [_event_dict(event) for event in paper.events],
        "evidence": card["evidence"],
        "conclusion_boundary": "以上为已索引的公开状态、公开讨论和算法信号，不能据此直接认定论文造假。",
    }


def _paper_by_doi(db: Session, doi: str) -> Paper | None:
    normalized = normalize_doi(doi)
    return db.scalar(
        select(Paper)
        .where(func.lower(Paper.doi) == normalized)
        .options(
            selectinload(Paper.events).selectinload(IntegrityEvent.evidence_pointers),
            selectinload(Paper.algorithmic_signals).selectinload(AlgorithmicSignal.evidence_pointers).selectinload(EvidencePointer.artifact),
        )
    )


def _official_status(events: list[IntegrityEvent]) -> str:
    levels = {event.status_level for event in events}
    for status_level, status in OFFICIAL_PRECEDENCE:
        if status_level in levels:
            return status
    return "none"


def _publisher_status(events: list[IntegrityEvent]) -> str:
    levels = {event.status_level for event in events}
    for status_level, status in PUBLISHER_PRECEDENCE:
        if status_level in levels:
            return status
    return "none"


def _institution_status(events: list[IntegrityEvent]) -> str:
    levels = {event.status_level for event in events}
    if "institution_conclusion" in levels:
        return "conclusion"
    if "institution_investigation" in levels:
        return "investigation"
    return "none"


def _count_events(events: list[IntegrityEvent], event_types: set[str], source_types: set[str]) -> int:
    return sum(
        1
        for event in events
        if event.event_type in event_types or event.status_level in event_types or event.source_type in source_types
    )


def _highest_signal_level(
    official_status: str,
    institution_status: str,
    public_discussion_count: int,
    media_report_count: int,
    algorithmic_signal_count: int,
) -> str:
    if official_status != "none":
        return "official"
    if institution_status != "none":
        return "investigation"
    if public_discussion_count or media_report_count:
        return "public_discussion"
    if algorithmic_signal_count:
        return "algorithmic"
    return "none"


def _summary(
    official_status: str,
    institution_status: str,
    public_discussion_count: int,
    media_report_count: int,
    algorithmic_signal_count: int,
) -> str:
    if official_status == "retracted":
        return "期刊或出版方已发布撤稿记录。"
    if official_status == "corrected":
        return "期刊或出版方已发布更正记录。"
    if official_status == "expression_of_concern":
        return "期刊或出版方已发布关注表达。"
    parts: list[str] = []
    if institution_status == "conclusion":
        parts.append("存在机构结论记录")
    elif institution_status == "investigation":
        parts.append("存在机构调查记录")
    if public_discussion_count:
        parts.append("存在公开讨论")
    if media_report_count:
        parts.append("存在媒体报道")
    if algorithmic_signal_count:
        parts.append("存在算法异常信号")
    if not parts:
        return "未索引到公开完整性事件或已审核算法信号。"
    return "，".join(parts) + "，尚未发现期刊撤稿、更正或关注表达记录。"


def _evidence(events: list[IntegrityEvent], signals: list[AlgorithmicSignal]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for event in events:
        if event.evidence_pointers:
            for pointer in event.evidence_pointers:
                items.append(_pointer_dict(pointer, event.source_url, event.claim_summary))
        else:
            items.append(
                {
                    "event_id": event.id,
                    "source_url": event.source_url,
                    "summary": event.claim_summary,
                    "status_level": event.status_level,
                }
            )
    for signal in signals:
        if signal.evidence_pointers:
            for pointer in signal.evidence_pointers:
                items.append(_pointer_dict(pointer, None, signal.summary))
        else:
            items.append(
                {
                    "signal_id": signal.id,
                    "summary": signal.summary,
                    "signal_type": signal.signal_type,
                    "severity": signal.severity,
                }
            )
    return items


def _pointer_dict(pointer: EvidencePointer, fallback_url: str | None, fallback_summary: str) -> dict[str, Any]:
    return {
        "id": pointer.id,
        "figure_label": pointer.figure_label,
        "table_label": pointer.table_label,
        "panel_label": pointer.panel_label,
        "column_name": pointer.column_name,
        "artifact_url": pointer.artifact.source_url if pointer.artifact else None,
        "evidence_url": pointer.evidence_url or fallback_url,
        "summary": pointer.evidence_summary or fallback_summary,
    }


def _event_dict(event: IntegrityEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status_level": event.status_level,
        "source_type": event.source_type,
        "source_name": event.source_name,
        "source_url": event.source_url,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "claim_summary": event.claim_summary,
        "verification_status": event.verification_status,
    }
