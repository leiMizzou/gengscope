from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from gengscope_api.db.models import SourceArtifact
from gengscope_api.db.session import get_db
from gengscope_api.schemas.artifacts import ArtifactDiscoverRequest, ArtifactFetchRequest, ArtifactRegisterRequest, PdfImageExtractRequest
from gengscope_api.services.artifacts import (
    artifact_dict,
    discover_paper_artifacts,
    extract_pdf_images,
    fetch_remote_artifact,
    list_paper_artifacts,
    register_artifact,
    save_uploaded_artifact,
)
from gengscope_api.services.audit_log import record_audit_log

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.post("/register")
def register_artifact_endpoint(
    request: ArtifactRegisterRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        artifact = register_artifact(db, request)
        result = {"artifact": artifact_dict(artifact)}
        record_audit_log(
            db,
            action="artifact_registered",
            actor=actor,
            target_type="artifact",
            target_id=artifact.id,
            paper_id=artifact.paper_id,
            artifact_id=artifact.id,
            summary=f"Registered {artifact.artifact_type} artifact.",
            metadata={"source_url": artifact.source_url, "license_status": artifact.license_status},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/upload")
def upload_artifact_endpoint(
    artifact_type: str = Form(...),
    file: UploadFile = File(...),
    paper_id: str | None = Form(default=None),
    doi: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    license_status: str = Form(default="manual_upload"),
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        content = file.file.read()
        artifact = save_uploaded_artifact(
            db,
            paper_id=paper_id,
            doi=doi,
            artifact_type=artifact_type,
            filename=file.filename or "artifact.bin",
            content_type=file.content_type,
            content=content,
            source_url=source_url,
            license_status=license_status,
        )
        result = {"artifact": artifact_dict(artifact), "material_status": artifact.paper.material_status}
        record_audit_log(
            db,
            action="artifact_uploaded",
            actor=actor,
            target_type="artifact",
            target_id=artifact.id,
            paper_id=artifact.paper_id,
            artifact_id=artifact.id,
            summary=f"Uploaded {artifact.artifact_type} artifact {artifact.filename}.",
            metadata={
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "checksum_sha256": artifact.checksum_sha256,
                "license_status": artifact.license_status,
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/fetch")
def fetch_artifact_endpoint(
    request: ArtifactFetchRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        artifact = fetch_remote_artifact(db, request)
        result = {"artifact": artifact_dict(artifact), "material_status": artifact.paper.material_status}
        record_audit_log(
            db,
            action="artifact_fetched",
            actor=actor,
            target_type="artifact",
            target_id=artifact.id,
            paper_id=artifact.paper_id,
            artifact_id=artifact.id,
            summary=f"Fetched {artifact.artifact_type} artifact {artifact.filename}.",
            metadata={
                "source_url": artifact.source_url,
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "checksum_sha256": artifact.checksum_sha256,
                "license_status": artifact.license_status,
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/extract/pdf-images")
def extract_pdf_images_endpoint(
    request: PdfImageExtractRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = extract_pdf_images(
            db,
            artifact_id=request.artifact_id,
            max_pages=request.max_pages,
            max_images=request.max_images,
            min_width=request.min_width,
            min_height=request.min_height,
        )
        record_audit_log(
            db,
            action="pdf_images_extracted",
            actor=actor,
            target_type="artifact",
            target_id=request.artifact_id,
            paper_id=result["paper_id"],
            artifact_id=request.artifact_id,
            summary=f"Extracted {result['extracted_count']} PDF image artifact(s).",
            metadata={
                "extracted_count": result["extracted_count"],
                "artifact_ids": [item["id"] for item in result["items"]],
                "skipped_count": len(result["skipped"]),
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/discover")
def discover_artifacts_endpoint(
    request: ArtifactDiscoverRequest,
    db: Session = Depends(get_db),
    actor: str | None = Header(default=None, alias="X-GengScope-Actor"),
) -> dict:
    try:
        result = discover_paper_artifacts(
            db,
            paper_id=request.paper_id,
            doi=request.doi,
            inspect_landing_pages=request.inspect_landing_pages,
            max_landing_pages=request.max_landing_pages,
            max_discovered_links=request.max_discovered_links,
        )
        record_audit_log(
            db,
            action="artifacts_discovered",
            actor=actor,
            target_type="paper",
            target_id=result["paper_id"],
            paper_id=result["paper_id"],
            summary=f"Discovered {len(result['items'])} artifacts for paper.",
            metadata={
                "material_status": result["material_status"],
                "artifact_count": len(result["items"]),
                "inspect_landing_pages": request.inspect_landing_pages,
                "inspected_landing_pages": result.get("inspected_landing_pages", []),
                "discovered_link_count": result.get("discovered_link_count", 0),
                "discovery_error_count": len(result.get("discovery_errors", [])),
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/papers/{paper_id}")
def list_paper_artifacts_endpoint(paper_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return list_paper_artifacts(db, paper_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{artifact_id}")
def artifact_detail_endpoint(artifact_id: str, db: Session = Depends(get_db)) -> dict:
    artifact = db.get(SourceArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"No artifact found for id {artifact_id}")
    return artifact_dict(artifact)
