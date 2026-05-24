from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from gengscope_api.services.artifacts import discover_paper_artifacts
from gengscope_api.services.entities import entity_profile, list_entity_papers, queue_entity_review_tasks
from gengscope_api.services.metadata_audit import run_metadata_audit


def run_entity_audit_cycle(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    discover_artifacts: bool = True,
    inspect_landing_pages: bool = False,
    queue_review_tasks: bool = True,
    run_metadata: bool = True,
    min_cluster_size: int = 5,
    min_signal_rate_audited_count: int = 2,
    signal_rate_threshold: float = 0.5,
    public_event_rate_threshold: float = 0.2,
    priority: int = 6,
) -> dict[str, Any]:
    papers = list_entity_papers(db, entity_type, entity_id)
    if not papers:
        raise LookupError(f"No papers found for {entity_type} {entity_id}")

    artifact_results = []
    if discover_artifacts:
        for paper in papers:
            artifact_results.append(discover_paper_artifacts(db, paper_id=paper.id, inspect_landing_pages=inspect_landing_pages))

    queue_result = None
    if queue_review_tasks:
        queue_result = queue_entity_review_tasks(db, entity_type, entity_id, priority)

    metadata_result = None
    if run_metadata:
        metadata_result = run_metadata_audit(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            min_cluster_size=min_cluster_size,
            min_signal_rate_audited_count=min_signal_rate_audited_count,
            signal_rate_threshold=signal_rate_threshold,
            public_event_rate_threshold=public_event_rate_threshold,
            create_review_tasks=True,
            priority=priority,
        )

    profile = entity_profile(db, entity_type, entity_id)
    artifact_count = sum(len(result["items"]) for result in artifact_results)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "paper_count": len(papers),
        "discovered_artifact_papers": len(artifact_results),
        "discovered_artifact_count": artifact_count,
        "queued_review_tasks": queue_result["created_review_tasks"] if queue_result else 0,
        "metadata_audit": metadata_result,
        "profile": profile,
        "conclusion_boundary": "实体审计 cycle 只是把材料发现、审计排队和元数据审计串联执行，不能直接认定论文、作者、实验室或机构造假。",
    }
