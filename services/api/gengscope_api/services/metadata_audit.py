from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gengscope_api.db.models import AlgorithmicSignal, EvidencePointer, Paper, ReviewTask
from gengscope_api.services.entities import COUNTED_SIGNAL_STATUSES, list_entity_papers
from gengscope_api.services.signals import signal_dict


ANALYZER_NAME = "gengscope.metadata"
ANALYZER_VERSION = "0.1.0"
PUBLIC_STATUS_LEVELS = {"public_discussion", "media_report"}
OFFICIAL_STATUS_LEVELS = {
    "official_retraction",
    "official_correction",
    "official_expression_of_concern",
    "institution_conclusion",
    "institution_investigation",
}
TERMINAL_SIGNAL_STATUSES = {"confirmed_signal", "false_positive", "not_actionable", "promoted_to_event"}
TITLE_TEMPLATE_SIMILARITY_THRESHOLD = 0.6
TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "through",
    "to",
    "via",
    "with",
    "using",
    "study",
    "effect",
    "effects",
    "analysis",
}


def run_metadata_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    min_cluster_size: int = 5,
    min_signal_rate_audited_count: int = 2,
    signal_rate_threshold: float = 0.5,
    public_event_rate_threshold: float = 0.2,
    create_review_tasks: bool = True,
    priority: int = 6,
) -> dict[str, Any]:
    normalized_type = _entity_type(entity_type)
    papers = _entity_papers(db, normalized_type, entity_id)
    if not papers:
        raise LookupError(f"No papers found for {normalized_type} {entity_id}")

    findings = []
    findings.extend(_publication_year_clusters(papers, min_cluster_size))
    findings.extend(_journal_clusters(papers, min_cluster_size))
    findings.extend(_title_template_clusters(papers, min_cluster_size))
    findings.extend(
        _event_density_findings(
            papers,
            public_event_rate_threshold=public_event_rate_threshold,
            min_signal_rate_audited_count=min_signal_rate_audited_count,
            signal_rate_threshold=signal_rate_threshold,
        )
    )

    signals: list[AlgorithmicSignal] = []
    created_review_tasks = 0
    for finding in findings[:100]:
        signal, created_task = _upsert_signal(db, finding, normalized_type, entity_id, create_review_tasks, priority)
        signals.append(signal)
        created_review_tasks += int(created_task)

    db.commit()
    for signal in signals:
        db.refresh(signal)

    return {
        "entity_type": normalized_type,
        "entity_id": entity_id,
        "paper_count": len(papers),
        "finding_count": len(findings),
        "signal_count": len(signals),
        "created_review_tasks": created_review_tasks,
        "signals": [signal_dict(signal) for signal in signals],
        "conclusion_boundary": "元数据审计只发现实体层面的聚集模式和公开状态密度，用于排序和人工复核，不能单独证明论文或作者造假。",
    }


def _entity_papers(db: Session, entity_type: str, entity_id: str) -> list[Paper]:
    return list_entity_papers(db, entity_type, entity_id)


def _publication_year_clusters(papers: list[Paper], min_cluster_size: int) -> list[dict[str, Any]]:
    by_year: dict[int, list[Paper]] = defaultdict(list)
    for paper in papers:
        if paper.publication_year is not None:
            by_year[paper.publication_year].append(paper)

    findings = []
    for year, year_papers in by_year.items():
        if len(year_papers) < min_cluster_size:
            continue
        severity = "medium" if len(year_papers) >= min_cluster_size * 2 else "low"
        for paper in year_papers[:25]:
            findings.append(
                {
                    "paper": paper,
                    "signal_type": "metadata_publication_year_cluster",
                    "severity": severity,
                    "confidence": 0.6,
                    "summary": f"实体在 {year} 年存在集中发表模式：当前索引到 {len(year_papers)} 篇相关论文。",
                    "metrics": {
                        "cluster_kind": "publication_year",
                        "publication_year": year,
                        "cluster_paper_count": len(year_papers),
                        "cluster_paper_ids": [item.id for item in year_papers],
                    },
                }
            )
    return findings


def _journal_clusters(papers: list[Paper], min_cluster_size: int) -> list[dict[str, Any]]:
    by_journal: dict[str, list[Paper]] = defaultdict(list)
    for paper in papers:
        if paper.journal_name:
            by_journal[paper.journal_name].append(paper)

    findings = []
    for journal, journal_papers in by_journal.items():
        if len(journal_papers) < min_cluster_size:
            continue
        severity = "medium" if len(journal_papers) >= min_cluster_size * 2 else "low"
        for paper in journal_papers[:25]:
            findings.append(
                {
                    "paper": paper,
                    "signal_type": "metadata_journal_cluster",
                    "severity": severity,
                    "confidence": 0.58,
                    "summary": f"实体在期刊 {journal} 存在集中发表模式：当前索引到 {len(journal_papers)} 篇相关论文。",
                    "metrics": {
                        "cluster_kind": "journal",
                        "journal_name": journal,
                        "cluster_paper_count": len(journal_papers),
                        "cluster_paper_ids": [item.id for item in journal_papers],
                    },
                }
            )
    return findings


def _title_template_clusters(papers: list[Paper], min_cluster_size: int) -> list[dict[str, Any]]:
    tokenized = {paper.id: _title_tokens(paper.title) for paper in papers}
    neighbors: dict[str, set[str]] = {paper.id: set() for paper in papers}
    paper_by_id = {paper.id: paper for paper in papers}
    for index, left in enumerate(papers):
        left_tokens = tokenized[left.id]
        if len(left_tokens) < 4:
            continue
        for right in papers[index + 1 :]:
            right_tokens = tokenized[right.id]
            if len(right_tokens) < 4:
                continue
            common_tokens = left_tokens & right_tokens
            if len(common_tokens) < 4:
                continue
            similarity = len(common_tokens) / len(left_tokens | right_tokens)
            if similarity >= TITLE_TEMPLATE_SIMILARITY_THRESHOLD:
                neighbors[left.id].add(right.id)
                neighbors[right.id].add(left.id)

    findings = []
    for component_ids in _connected_components(neighbors):
        if len(component_ids) < min_cluster_size:
            continue
        component = sorted((paper_by_id[paper_id] for paper_id in component_ids), key=lambda paper: (paper.publication_year or 0, paper.title), reverse=True)
        shared_terms = _shared_title_terms([tokenized[paper.id] for paper in component])
        severity = "medium" if len(component) >= min_cluster_size * 2 else "low"
        summary_terms = ", ".join(shared_terms[:8]) or "shared title tokens"
        for paper in component[:25]:
            findings.append(
                {
                    "paper": paper,
                    "signal_type": "metadata_title_template_similarity",
                    "severity": severity,
                    "confidence": 0.62,
                    "summary": f"实体存在标题高度相似的论文聚集，当前聚类 {len(component)} 篇，共享关键词：{summary_terms}。",
                    "metrics": {
                        "cluster_kind": "title_template",
                        "cluster_paper_count": len(component),
                        "cluster_paper_ids": [item.id for item in component],
                        "shared_title_terms": shared_terms,
                        "similarity_threshold": TITLE_TEMPLATE_SIMILARITY_THRESHOLD,
                    },
                }
            )
    return findings


def _event_density_findings(
    papers: list[Paper],
    *,
    public_event_rate_threshold: float,
    min_signal_rate_audited_count: int,
    signal_rate_threshold: float,
) -> list[dict[str, Any]]:
    total = len(papers)
    if not total:
        return []
    public_papers = [paper for paper in papers if _public_event_count(paper)]
    official_papers = [paper for paper in papers if _official_event_count(paper)]
    audited_papers = [paper for paper in papers if paper.audit_status == "reviewed" or _counted_non_metadata_signals(paper)]
    signal_papers = [paper for paper in papers if _counted_non_metadata_signals(paper)]
    findings = []

    public_rate = len(public_papers) / total
    if public_papers and public_rate >= public_event_rate_threshold:
        for paper in public_papers[:25]:
            findings.append(
                {
                    "paper": paper,
                    "signal_type": "metadata_public_event_density",
                    "severity": "medium",
                    "confidence": round(min(0.95, 0.5 + public_rate), 3),
                    "summary": f"实体相关论文的公开讨论/媒体记录比例为 {public_rate:.0%}，需要结合来源逐条复核。",
                    "metrics": {
                        "public_event_paper_count": len(public_papers),
                        "paper_count": total,
                        "public_event_rate": round(public_rate, 4),
                    },
                }
            )

    if official_papers:
        official_rate = len(official_papers) / total
        for paper in official_papers[:25]:
            findings.append(
                {
                    "paper": paper,
                    "signal_type": "metadata_official_event_density",
                    "severity": "high",
                    "confidence": round(min(0.98, 0.7 + official_rate / 2), 3),
                    "summary": f"实体相关论文中存在官方或机构事件记录，当前覆盖 {len(official_papers)} / {total} 篇。",
                    "metrics": {
                        "official_event_paper_count": len(official_papers),
                        "paper_count": total,
                        "official_event_rate": round(official_rate, 4),
                    },
                }
            )

    if len(audited_papers) >= min_signal_rate_audited_count:
        signal_rate = len(signal_papers) / len(audited_papers)
        if signal_papers and signal_rate >= signal_rate_threshold:
            for paper in signal_papers[:25]:
                findings.append(
                    {
                        "paper": paper,
                        "signal_type": "metadata_signal_density",
                        "severity": "high" if signal_rate >= 0.75 else "medium",
                        "confidence": round(min(0.99, 0.55 + signal_rate / 2), 3),
                        "summary": f"已审计样本中的算法信号论文比例为 {signal_rate:.0%}，建议扩大材料获取和人工复核。",
                        "metrics": {
                            "audited_paper_count": len(audited_papers),
                            "signal_paper_count": len(signal_papers),
                            "signal_rate_among_audited": round(signal_rate, 4),
                        },
                    }
                )
    return findings


def _upsert_signal(
    db: Session,
    finding: dict[str, Any],
    entity_type: str,
    entity_id: str,
    create_review_task: bool,
    priority: int,
) -> tuple[AlgorithmicSignal, bool]:
    paper = finding["paper"]
    metrics = {
        **finding["metrics"],
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
    signal = db.scalar(
        select(AlgorithmicSignal).where(
            AlgorithmicSignal.paper_id == paper.id,
            AlgorithmicSignal.signal_type == finding["signal_type"],
            AlgorithmicSignal.analyzer_name == ANALYZER_NAME,
            AlgorithmicSignal.summary == finding["summary"],
        )
    )
    if signal is None:
        signal = AlgorithmicSignal(
            paper=paper,
            signal_type=finding["signal_type"],
            severity=finding["severity"],
            confidence=finding["confidence"],
            analyzer_name=ANALYZER_NAME,
            analyzer_version=ANALYZER_VERSION,
            summary=finding["summary"],
            metrics_json=metrics,
            status="needs_review",
        )
        db.add(signal)
        db.flush()
    else:
        signal.severity = finding["severity"]
        signal.confidence = finding["confidence"]
        signal.analyzer_version = ANALYZER_VERSION
        signal.metrics_json = metrics
        if signal.status not in TERMINAL_SIGNAL_STATUSES:
            signal.status = "needs_review"
        db.execute(delete(EvidencePointer).where(EvidencePointer.signal_id == signal.id))

    db.add(
        EvidencePointer(
            paper_id=paper.id,
            signal=signal,
            evidence_summary=finding["summary"],
        )
    )

    created_task = False
    if create_review_task and signal.status not in TERMINAL_SIGNAL_STATUSES:
        existing_task = db.scalar(select(ReviewTask).where(ReviewTask.signal_id == signal.id, ReviewTask.status == "open"))
        if existing_task is None:
            db.add(ReviewTask(paper=paper, signal=signal, task_type="signal_review", priority=priority))
            paper.audit_status = "in_review"
            created_task = True
    return signal, created_task


def _counted_non_metadata_signals(paper: Paper) -> list[AlgorithmicSignal]:
    return [
        signal
        for signal in paper.algorithmic_signals
        if signal.status in COUNTED_SIGNAL_STATUSES and signal.analyzer_name != ANALYZER_NAME
    ]


def _public_event_count(paper: Paper) -> int:
    return sum(1 for event in paper.events if event.status_level in PUBLIC_STATUS_LEVELS or event.source_type in {"pubpeer", "media"})


def _official_event_count(paper: Paper) -> int:
    return sum(1 for event in paper.events if event.status_level in OFFICIAL_STATUS_LEVELS)


def _entity_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"author", "institution", "group"}:
        raise ValueError("entity_type must be 'author', 'institution' or 'group'")
    return normalized


def _title_tokens(title: str | None) -> set[str]:
    if not title:
        return set()
    tokens = {token for token in re.findall(r"[a-z0-9]+", title.casefold()) if len(token) > 2}
    return {token for token in tokens if token not in TITLE_STOPWORDS}


def _connected_components(neighbors: dict[str, set[str]]) -> list[set[str]]:
    seen: set[str] = set()
    components: list[set[str]] = []
    for node, linked in neighbors.items():
        if node in seen or not linked:
            continue
        stack = [node]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.add(current)
            stack.extend(neighbors[current] - seen)
        components.append(component)
    return components


def _shared_title_terms(token_sets: list[set[str]]) -> list[str]:
    if not token_sets:
        return []
    counter: Counter[str] = Counter()
    for tokens in token_sets:
        counter.update(tokens)
    minimum_count = max(2, len(token_sets) // 2)
    return sorted([token for token, count in counter.items() if count >= minimum_count])
