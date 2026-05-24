from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.schemas.audits import EntityAuditCycleRequest, ImageAuditRequest, MetadataAuditRequest, NumericAuditRequest
from gengscope_api.services.audit_log import record_audit_log
from gengscope_api.services.entity_cycle import run_entity_audit_cycle
from gengscope_api.services.image_audit import run_image_audit
from gengscope_api.services.metadata_audit import run_metadata_audit
from gengscope_api.services.numeric_audit import run_numeric_audit

router = APIRouter(prefix="/api/audits", tags=["audits"])


@router.post("/entity-cycle")
def entity_audit_cycle_endpoint(
    request: EntityAuditCycleRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = run_entity_audit_cycle(
            db,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            discover_artifacts=request.discover_artifacts,
            inspect_landing_pages=request.inspect_landing_pages,
            queue_review_tasks=request.queue_review_tasks,
            run_metadata=request.run_metadata_audit,
            min_cluster_size=request.min_cluster_size,
            min_signal_rate_audited_count=request.min_signal_rate_audited_count,
            signal_rate_threshold=request.signal_rate_threshold,
            public_event_rate_threshold=request.public_event_rate_threshold,
            priority=request.priority,
        )
        record_audit_log(
            db,
            action="entity_audit_cycle_run",
            actor=actor,
            target_type="entity",
            target_id=request.entity_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            summary="Ran entity audit cycle.",
            metadata={
                "paper_count": result["paper_count"],
                "discovered_artifact_count": result["discovered_artifact_count"],
                "queued_review_tasks": result["queued_review_tasks"],
                "metadata_signal_count": result["metadata_audit"]["signal_count"] if result["metadata_audit"] else 0,
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/numeric")
def numeric_audit_endpoint(
    request: NumericAuditRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = run_numeric_audit(
            db,
            artifact_id=request.artifact_id,
            min_duplicate_length=request.min_duplicate_length,
            min_last_digit_sample=request.min_last_digit_sample,
            min_fixed_relationship_sample=request.min_fixed_relationship_sample,
            max_fixed_relationship_cv=request.max_fixed_relationship_cv,
            create_review_tasks=request.create_review_tasks,
            priority=request.priority,
        )
        record_audit_log(
            db,
            action="numeric_audit_run",
            actor=actor,
            target_type="artifact",
            target_id=request.artifact_id,
            paper_id=result["paper_id"],
            artifact_id=request.artifact_id,
            summary=f"Numeric audit created {result['signal_count']} signals.",
            metadata={
                "signal_count": result["signal_count"],
                "created_review_tasks": result["created_review_tasks"],
                "analyzed_rows": result["analyzed_rows"],
                "analyzed_numeric_columns": result["analyzed_numeric_columns"],
                "signal_ids": [signal["id"] for signal in result["signals"]],
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/image")
def image_audit_endpoint(
    request: ImageAuditRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = run_image_audit(
            db,
            artifact_id=request.artifact_id,
            compare_artifact_ids=request.compare_artifact_ids,
            max_hamming_distance=request.max_hamming_distance,
            enable_patch_similarity=request.enable_patch_similarity,
            max_patch_hamming_distance=request.max_patch_hamming_distance,
            patch_grid_size=request.patch_grid_size,
            min_patch_stddev=request.min_patch_stddev,
            enable_shift_correlation=request.enable_shift_correlation,
            min_shift_correlation=request.min_shift_correlation,
            max_shift_fraction=request.max_shift_fraction,
            correlation_size=request.correlation_size,
            create_review_tasks=request.create_review_tasks,
            priority=request.priority,
        )
        record_audit_log(
            db,
            action="image_audit_run",
            actor=actor,
            target_type="artifact",
            target_id=request.artifact_id,
            paper_id=result["paper_id"],
            artifact_id=request.artifact_id,
            summary=f"Image audit created {result['signal_count']} signals.",
            metadata={
                "signal_count": result["signal_count"],
                "created_review_tasks": result["created_review_tasks"],
                "compared_artifact_count": result["compared_artifact_count"],
                "signal_ids": [signal["id"] for signal in result["signals"]],
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/metadata")
def metadata_audit_endpoint(
    request: MetadataAuditRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = run_metadata_audit(
            db,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            min_cluster_size=request.min_cluster_size,
            min_signal_rate_audited_count=request.min_signal_rate_audited_count,
            signal_rate_threshold=request.signal_rate_threshold,
            public_event_rate_threshold=request.public_event_rate_threshold,
            create_review_tasks=request.create_review_tasks,
            priority=request.priority,
        )
        record_audit_log(
            db,
            action="metadata_audit_run",
            actor=actor,
            target_type="entity",
            target_id=request.entity_id,
            entity_type=result["entity_type"],
            entity_id=request.entity_id,
            summary=f"Metadata audit created {result['signal_count']} signals.",
            metadata={
                "paper_count": result["paper_count"],
                "finding_count": result["finding_count"],
                "signal_count": result["signal_count"],
                "created_review_tasks": result["created_review_tasks"],
                "signal_ids": [signal["id"] for signal in result["signals"]],
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
