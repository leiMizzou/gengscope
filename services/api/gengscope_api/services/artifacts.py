from __future__ import annotations

import hashlib
import html as html_lib
import ipaddress
import re
import socket
import threading
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urldefrag, urljoin, urlparse

import httpx
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gengscope_api.config import get_settings
from gengscope_api.db.models import Paper, SourceArtifact
from gengscope_api.schemas.artifacts import ArtifactFetchRequest, ArtifactRegisterRequest
from gengscope_api.services.doi import normalize_doi


PDF_ARTIFACT_TYPES = {"paper_pdf"}
SOURCE_DATA_ARTIFACT_TYPES = {"source_data", "source_data_table", "supplementary_data", "supplementary_table"}
LANDING_ARTIFACT_TYPES = {"publisher_landing_page"}
IMAGE_ARTIFACT_TYPES = {"figure_image", "image_panel", "supplementary_image"}
AUDITABLE_ARTIFACT_TYPES = PDF_ARTIFACT_TYPES | SOURCE_DATA_ARTIFACT_TYPES | IMAGE_ARTIFACT_TYPES | {"manual_upload"}
FETCHABLE_LICENSE_STATUSES = {
    "open_or_linked",
    "manual_authorized",
    "manual_upload",
    "author_provided",
    "repository_open",
    "public_domain",
    "cc0",
    "cc_by",
    "cc_by_nc",
    "fair_use_review",
}
HTML_FETCH_MAX_BYTES = 2 * 1024 * 1024
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_FETCH_THROTTLE_LOCK = threading.Lock()
_LAST_FETCH_BY_HOST: dict[str, float] = {}


def resolve_paper(db: Session, paper_id: str | None = None, doi: str | None = None) -> Paper:
    if paper_id:
        paper = db.get(Paper, paper_id)
    elif doi:
        normalized = normalize_doi(doi)
        paper = db.scalar(select(Paper).where(func.lower(Paper.doi) == normalized))
    else:
        raise ValueError("paper_id or doi is required")
    if paper is None:
        raise LookupError("No paper found for artifact operation")
    return paper


def artifact_dict(artifact: SourceArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "paper_id": artifact.paper_id,
        "artifact_type": artifact.artifact_type,
        "source_url": artifact.source_url,
        "storage_uri": artifact.storage_uri,
        "content_type": artifact.content_type,
        "filename": artifact.filename,
        "checksum_sha256": artifact.checksum_sha256,
        "license_status": artifact.license_status,
    }


def list_paper_artifacts(db: Session, paper_id: str) -> dict[str, Any]:
    paper = resolve_paper(db, paper_id=paper_id)
    sync_paper_material_state(db, paper)
    artifacts = db.scalars(select(SourceArtifact).where(SourceArtifact.paper_id == paper.id).order_by(SourceArtifact.created_at)).all()
    return {
        "paper_id": paper.id,
        "material_status": paper.material_status,
        "is_oa_pdf_available": paper.is_oa_pdf_available,
        "is_source_data_available": paper.is_source_data_available,
        "items": [artifact_dict(artifact) for artifact in artifacts],
    }


def register_artifact(db: Session, request: ArtifactRegisterRequest) -> SourceArtifact:
    paper = resolve_paper(db, paper_id=request.paper_id, doi=request.doi)
    checksum = request.checksum_sha256 or _checksum_for_path(request.storage_uri)
    artifact = _upsert_artifact(
        db,
        paper=paper,
        artifact_type=request.artifact_type,
        source_url=str(request.source_url),
        storage_uri=request.storage_uri,
        content_type=request.content_type,
        filename=request.filename,
        checksum_sha256=checksum,
        license_status=request.license_status,
    )
    sync_paper_material_state(db, paper)
    db.commit()
    db.refresh(artifact)
    return artifact


def save_uploaded_artifact(
    db: Session,
    *,
    paper_id: str | None,
    doi: str | None,
    artifact_type: str,
    filename: str,
    content_type: str | None,
    content: bytes,
    source_url: str | None,
    license_status: str,
    storage_root: str | None = None,
) -> SourceArtifact:
    if not content:
        raise ValueError("uploaded file is empty")
    paper = resolve_paper(db, paper_id=paper_id, doi=doi)
    digest = hashlib.sha256(content).hexdigest()
    safe_name = _safe_filename(filename)
    artifact_id = str(uuid.uuid4())
    root = Path(storage_root or get_settings().artifact_storage_dir)
    target_dir = root / paper.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{artifact_id}_{safe_name}"
    target_path.write_bytes(content)
    artifact = _upsert_artifact(
        db,
        paper=paper,
        artifact_type=artifact_type,
        source_url=source_url or f"local-upload://{safe_name}",
        storage_uri=str(target_path),
        content_type=content_type,
        filename=safe_name,
        checksum_sha256=digest,
        license_status=license_status,
    )
    sync_paper_material_state(db, paper)
    db.commit()
    db.refresh(artifact)
    return artifact


def discover_paper_artifacts(
    db: Session,
    paper_id: str | None = None,
    doi: str | None = None,
    *,
    inspect_landing_pages: bool = False,
    max_landing_pages: int = 3,
    max_discovered_links: int = 30,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    paper = resolve_paper(db, paper_id=paper_id, doi=doi)
    if paper.landing_page_url:
        _upsert_artifact(
            db,
            paper=paper,
            artifact_type="publisher_landing_page",
            source_url=paper.landing_page_url,
            license_status="reference_only",
        )
    if paper.open_access_url:
        _upsert_artifact(
            db,
            paper=paper,
            artifact_type="paper_pdf",
            source_url=paper.open_access_url,
            license_status="open_or_linked",
        )
    pmc_url = _pmc_article_url(paper.pmcid)
    if pmc_url:
        _upsert_artifact(
            db,
            paper=paper,
            artifact_type="publisher_landing_page",
            source_url=pmc_url,
            license_status="reference_only",
        )
        _upsert_artifact(
            db,
            paper=paper,
            artifact_type="paper_pdf",
            source_url=f"{pmc_url}pdf/",
            license_status="open_or_linked",
        )
    discovery_errors: list[dict[str, str]] = []
    inspected_pages: list[str] = []
    discovered_links = 0
    if inspect_landing_pages and max_landing_pages > 0 and max_discovered_links > 0:
        db.flush()
        pages = _discovery_pages(db, paper)[:max_landing_pages]
        for page_url in pages:
            inspected_pages.append(page_url)
            try:
                for candidate in _discover_links_from_page(page_url, http_client=http_client):
                    if discovered_links >= max_discovered_links:
                        break
                    _upsert_artifact(
                        db,
                        paper=paper,
                        artifact_type=candidate["artifact_type"],
                        source_url=candidate["source_url"],
                        content_type=candidate["content_type"],
                        filename=candidate["filename"],
                        license_status="discovered_link",
                    )
                    discovered_links += 1
            except ValueError as exc:
                discovery_errors.append({"source_url": page_url, "error": str(exc)})
            if discovered_links >= max_discovered_links:
                break

    sync_paper_material_state(db, paper)
    db.commit()
    result = list_paper_artifacts(db, paper.id)
    result.update(
        {
            "inspected_landing_pages": inspected_pages,
            "discovered_link_count": discovered_links,
            "discovery_errors": discovery_errors,
        }
    )
    return result


def fetch_remote_artifact(
    db: Session,
    request: ArtifactFetchRequest,
    *,
    http_client: httpx.Client | None = None,
    storage_root: str | None = None,
) -> SourceArtifact:
    artifact: SourceArtifact | None = None
    if request.artifact_id:
        artifact = db.get(SourceArtifact, request.artifact_id)
        if artifact is None:
            raise LookupError(f"No artifact found for id {request.artifact_id}")
        paper = resolve_paper(db, paper_id=artifact.paper_id)
        source_url = str(request.source_url or artifact.source_url)
        artifact_type = request.artifact_type or artifact.artifact_type
    else:
        if not request.source_url:
            raise ValueError("source_url is required when artifact_id is not provided")
        if not request.artifact_type:
            raise ValueError("artifact_type is required when artifact_id is not provided")
        paper = resolve_paper(db, paper_id=request.paper_id, doi=request.doi)
        source_url = str(request.source_url)
        artifact_type = request.artifact_type

    settings = get_settings()
    max_bytes = request.max_bytes or settings.artifact_fetch_max_bytes
    _validate_fetch_license(request.license_status)
    downloaded = _download_bytes(source_url, max_bytes=max_bytes, http_client=http_client)
    filename = _safe_filename(request.filename or downloaded["filename"] or _filename_from_url(source_url) or "artifact.bin")
    _validate_downloaded_artifact_payload(
        artifact_type=artifact_type,
        source_url=source_url,
        filename=filename,
        content_type=downloaded["content_type"],
    )
    digest = hashlib.sha256(downloaded["content"]).hexdigest()

    if artifact is None:
        artifact = _upsert_artifact(
            db,
            paper=paper,
            artifact_type=artifact_type,
            source_url=downloaded["final_url"] or source_url,
            content_type=downloaded["content_type"],
            filename=filename,
            checksum_sha256=digest,
            license_status=request.license_status,
        )
    else:
        artifact.artifact_type = artifact_type
        artifact.source_url = downloaded["final_url"] or source_url
        artifact.content_type = downloaded["content_type"] or artifact.content_type
        artifact.filename = filename
        artifact.checksum_sha256 = digest
        artifact.license_status = request.license_status or artifact.license_status

    db.flush()
    root = Path(storage_root or settings.artifact_storage_dir)
    target_dir = root / paper.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{artifact.id}_{filename}"
    target_path.write_bytes(downloaded["content"])
    artifact.storage_uri = str(target_path)
    sync_paper_material_state(db, paper)
    db.commit()
    db.refresh(artifact)
    return artifact


def extract_pdf_images(
    db: Session,
    *,
    artifact_id: str,
    max_pages: int = 8,
    max_images: int = 30,
    min_width: int = 80,
    min_height: int = 80,
    storage_root: str | None = None,
) -> dict[str, Any]:
    pdf_artifact = db.get(SourceArtifact, artifact_id)
    if pdf_artifact is None:
        raise LookupError(f"No artifact found for id {artifact_id}")
    if pdf_artifact.artifact_type not in PDF_ARTIFACT_TYPES:
        raise ValueError("PDF image extraction requires a paper_pdf artifact")
    if not pdf_artifact.storage_uri:
        raise ValueError("PDF image extraction requires a locally fetched PDF artifact")
    paper = resolve_paper(db, paper_id=pdf_artifact.paper_id)
    pdf_path = Path(pdf_artifact.storage_uri)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise ValueError(f"PDF artifact file does not exist: {pdf_artifact.storage_uri}")

    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency guard for unusual local installs.
        raise RuntimeError("PDF image extraction requires the pymupdf package") from exc

    extracted: list[SourceArtifact] = []
    skipped: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()
    root = Path(storage_root or get_settings().artifact_storage_dir)
    target_dir = root / paper.id
    target_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(str(pdf_path)) as document:
        page_count = len(document)
        for page_index in range(min(max_pages, page_count)):
            page = document[page_index]
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                if len(extracted) >= max_images:
                    break
                xref = int(image_info[0])
                width = int(image_info[2])
                height = int(image_info[3])
                if xref in seen_xrefs:
                    skipped.append({"page": page_index + 1, "xref": xref, "reason": "duplicate_xref"})
                    continue
                seen_xrefs.add(xref)
                if width < min_width or height < min_height:
                    skipped.append({"page": page_index + 1, "xref": xref, "reason": "below_min_size", "width": width, "height": height})
                    continue
                payload = document.extract_image(xref)
                content = payload.get("image")
                extension = _safe_image_extension(payload.get("ext"))
                if not content:
                    skipped.append({"page": page_index + 1, "xref": xref, "reason": "empty_image_payload"})
                    continue
                if not _is_readable_image(content):
                    skipped.append({"page": page_index + 1, "xref": xref, "reason": "unreadable_image"})
                    continue
                digest = hashlib.sha256(content).hexdigest()
                filename = _safe_filename(
                    f"{Path(pdf_artifact.filename or 'paper').stem}_p{page_index + 1}_img{image_index}_xref{xref}.{extension}"
                )
                source_url = f"{pdf_artifact.source_url}#page={page_index + 1}&xref={xref}"
                artifact = _upsert_artifact(
                    db,
                    paper=paper,
                    artifact_type="figure_image",
                    source_url=source_url,
                    content_type=f"image/{'jpeg' if extension == 'jpg' else extension}",
                    filename=filename,
                    checksum_sha256=digest,
                    license_status=pdf_artifact.license_status,
                )
                db.flush()
                target_path = target_dir / f"{artifact.id}_{filename}"
                target_path.write_bytes(content)
                artifact.storage_uri = str(target_path)
                extracted.append(artifact)
            if len(extracted) >= max_images:
                break

    sync_paper_material_state(db, paper)
    db.commit()
    for artifact in extracted:
        db.refresh(artifact)
    return {
        "source_artifact": artifact_dict(pdf_artifact),
        "paper_id": paper.id,
        "extracted_count": len(extracted),
        "items": [artifact_dict(artifact) for artifact in extracted],
        "skipped": skipped[:50],
        "conclusion_boundary": "PDF 图像抽取只把可审计材料转为 figure_image artifact；后续图像相似信号仍需人工复核，不能单独证明造假。",
    }


def sync_paper_material_state(db: Session, paper: Paper) -> None:
    artifacts = db.scalars(select(SourceArtifact).where(SourceArtifact.paper_id == paper.id)).all()
    has_pdf = bool(paper.open_access_url) or any(artifact.artifact_type in PDF_ARTIFACT_TYPES for artifact in artifacts)
    has_source_data = any(artifact.artifact_type in SOURCE_DATA_ARTIFACT_TYPES for artifact in artifacts)
    has_manual_upload = any(artifact.artifact_type == "manual_upload" or artifact.artifact_type in IMAGE_ARTIFACT_TYPES for artifact in artifacts)
    has_landing = bool(paper.landing_page_url) or any(artifact.artifact_type in LANDING_ARTIFACT_TYPES for artifact in artifacts)

    paper.is_oa_pdf_available = has_pdf
    paper.is_source_data_available = has_source_data
    if has_pdf and has_source_data:
        paper.material_status = "full_auditable"
    elif has_source_data:
        paper.material_status = "source_data_found"
    elif has_pdf:
        paper.material_status = "pdf_found"
    elif has_manual_upload:
        paper.material_status = "manual_upload_available"
    elif has_landing:
        paper.material_status = "landing_page_found"
    else:
        paper.material_status = "metadata_only"


def _upsert_artifact(
    db: Session,
    *,
    paper: Paper,
    artifact_type: str,
    source_url: str,
    storage_uri: str | None = None,
    content_type: str | None = None,
    filename: str | None = None,
    checksum_sha256: str | None = None,
    license_status: str = "unknown",
) -> SourceArtifact:
    artifact = db.scalar(
        select(SourceArtifact).where(
            SourceArtifact.paper_id == paper.id,
            SourceArtifact.artifact_type == artifact_type,
            SourceArtifact.source_url == source_url,
        )
    )
    if artifact is None:
        artifact = SourceArtifact(paper=paper, artifact_type=artifact_type, source_url=source_url)
        db.add(artifact)
        db.flush()
    artifact.storage_uri = storage_uri or artifact.storage_uri
    artifact.content_type = content_type or artifact.content_type
    artifact.filename = filename or artifact.filename
    artifact.checksum_sha256 = checksum_sha256 or artifact.checksum_sha256
    artifact.license_status = license_status or artifact.license_status
    return artifact


def _checksum_for_path(storage_uri: str | None) -> str | None:
    if not storage_uri:
        return None
    path = Path(storage_uri)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_image_extension(value: str | None) -> str:
    extension = (value or "png").lower().strip().lstrip(".")
    if extension == "jpeg":
        return "jpg"
    if extension in {"png", "jpg", "webp", "tif", "tiff", "bmp"}:
        return extension
    return "png"


def _is_readable_image(content: bytes) -> bool:
    try:
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            image.verify()
        return True
    except Exception:
        return False


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "artifact.bin"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:180] or "artifact.bin"


def _pmc_article_url(value: str | None) -> str | None:
    pmcid = _clean_pmcid(value)
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else None


def _pubmed_url(value: str | None) -> str | None:
    pmid = _clean_pmid(value)
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None


def _clean_pmcid(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"PMC\d+", value, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    cleaned = value.strip()
    if cleaned.isdigit():
        return f"PMC{cleaned}"
    if "/pmc/articles/" not in cleaned.casefold():
        return None
    numeric_match = re.search(r"/pmc/articles/(\d{5,12})(?:[/#?]|$)", cleaned, flags=re.IGNORECASE)
    return f"PMC{numeric_match.group(1)}" if numeric_match else None


def _clean_pmid(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d{5,12}", value)
    return match.group(0) if match else None


def _discovery_pages(db: Session, paper: Paper) -> list[str]:
    urls = []
    if paper.landing_page_url:
        urls.append(paper.landing_page_url)
    pmc_url = _pmc_article_url(paper.pmcid)
    if pmc_url:
        urls.append(pmc_url)
    pubmed_url = _pubmed_url(paper.pmid)
    if pubmed_url:
        urls.append(pubmed_url)
    artifacts = db.scalars(
        select(SourceArtifact).where(
            SourceArtifact.paper_id == paper.id,
            SourceArtifact.artifact_type.in_(LANDING_ARTIFACT_TYPES),
        )
    ).all()
    urls.extend(artifact.source_url for artifact in artifacts)
    normalized_urls = []
    for url in urls:
        normalized_urls.append(url)
        normalized_pmc_url = _pmc_article_url(url)
        if normalized_pmc_url:
            normalized_urls.append(normalized_pmc_url)
    deduped_urls = _dedupe_urls(normalized_urls)
    return [
        url
        for _index, url in sorted(
            enumerate(deduped_urls),
            key=lambda item: (_discovery_page_priority(item[1], paper.landing_page_url), item[0]),
        )
    ]


def _discovery_page_priority(url: str, primary_landing_page_url: str | None = None) -> int:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    path = parsed.path.casefold()
    if "ncbi.nlm.nih.gov" in host and "/pmc/articles/" in path:
        if re.search(r"/pmc/articles/\d+/?$", path):
            return 4
        return 0
    if primary_landing_page_url and url == primary_landing_page_url:
        return 1
    if "pubmed.ncbi.nlm.nih.gov" in host:
        return 3
    if host == "doi.org":
        return 5
    return 2


def _discover_links_from_page(page_url: str, *, http_client: httpx.Client | None = None) -> list[dict[str, Any]]:
    html = _fetch_html(page_url, http_client=http_client)
    candidates = []
    seen: set[tuple[str, str]] = set()
    for link in _candidate_links_from_html(html):
        source_url = _absolute_url(page_url, link["href"])
        if not source_url:
            continue
        artifact_type = _classify_link(source_url, link["text"])
        if not artifact_type:
            continue
        key = (artifact_type, source_url)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "artifact_type": artifact_type,
                "source_url": source_url,
                "content_type": _content_type_from_url(source_url),
                "filename": _filename_from_url(source_url),
            }
        )
    return candidates


def _fetch_html(page_url: str, *, http_client: httpx.Client | None = None) -> str:
    _validate_fetch_url(page_url)
    close_client = http_client is None
    client = http_client or httpx.Client(timeout=get_settings().http_timeout_seconds, follow_redirects=True)
    try:
        response = client.get(page_url, follow_redirects=True)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > HTML_FETCH_MAX_BYTES:
            raise ValueError(f"landing page exceeds max html bytes ({HTML_FETCH_MAX_BYTES})")
        content = response.content
        if len(content) > HTML_FETCH_MAX_BYTES:
            raise ValueError(f"landing page exceeds max html bytes ({HTML_FETCH_MAX_BYTES})")
        content_type = _content_type(response.headers.get("content-type")) or ""
        if content_type and not (
            content_type.startswith("text/")
            or content_type in {"application/xhtml+xml", "application/xml"}
            or content_type.endswith("+xml")
        ):
            raise ValueError(f"landing page is not html/text content: {content_type}")
        return response.text
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"landing page fetch failed with HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"landing page fetch failed: {exc}") from exc
    finally:
        if close_client:
            client.close()


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name.casefold(): value for name, value in attrs}
        href = attr.get("href") or attr.get("data-href")
        if tag.casefold() in {"a", "link"}:
            if not href:
                return
            text = " ".join(
                value
                for key, value in attr.items()
                if key in {"title", "aria-label", "download", "rel", "type"} and value
            )
            self.links.append({"href": href, "text": text})
            if tag.casefold() == "a":
                self._current_index = len(self.links) - 1
        elif tag.casefold() == "meta":
            content = attr.get("content")
            name = attr.get("name") or attr.get("property") or ""
            if content and _looks_like_asset_ref(content):
                self.links.append({"href": content, "text": name})
        elif tag.casefold() in {"img", "source"}:
            src = attr.get("src") or attr.get("data-src")
            if not src or not _looks_like_asset_ref(src):
                return
            text = " ".join(
                value
                for key, value in attr.items()
                if key in {"alt", "title", "aria-label", "data-caption"} and value
            )
            self.links.append({"href": src, "text": text})

    def handle_data(self, data: str) -> None:
        if self._current_index is not None and data.strip():
            self.links[self._current_index]["text"] = f"{self.links[self._current_index]['text']} {data.strip()}".strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a":
            self._current_index = None


def _extract_links(html: str) -> list[dict[str, str]]:
    parser = _LinkExtractor()
    parser.feed(html)
    return parser.links


def _candidate_links_from_html(html: str) -> list[dict[str, str]]:
    links = _extract_links(html)
    links.extend(_extract_embedded_asset_refs(html))
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for link in links:
        href = link["href"].strip()
        if not href or href in seen:
            continue
        seen.add(href)
        deduped.append({"href": href, "text": link.get("text", "")})
    return deduped


def _extract_embedded_asset_refs(html: str) -> list[dict[str, str]]:
    normalized = html_lib.unescape(html).replace("\\/", "/").replace("\\u002F", "/")
    refs: list[dict[str, str]] = []
    pattern = re.compile(r"""(?P<url>https?://[^"' <>()]+|//[^"' <>()]+|/[A-Za-z0-9][^"' <>()]+)""")
    for match in pattern.finditer(normalized):
        href = match.group("url").rstrip(".,;]}")
        if not _looks_like_asset_ref(href):
            continue
        start = max(0, match.start() - 80)
        end = min(len(normalized), match.end() + 80)
        refs.append({"href": href, "text": _strip_markup(normalized[start:end])})
    return refs


def _looks_like_asset_ref(value: str) -> bool:
    text = value.casefold()
    return bool(
        re.search(r"\.(?:pdf|csv|tsv|xls|xlsx|xlsm|zip|doc|docx|ppt|pptx|png|jpe?g|webp|tiff?|gif)(?:[?#]|$)", text)
        or any(
            term in text
            for term in (
                "source-data",
                "source_data",
                "sourcedata",
                "data_sheet",
                "data-sheet",
                "supplement",
                "supplementary",
                "supplementary-material",
                "supplemental",
                "supporting-information",
                "supporting_information",
                "suppinfo",
                "suppl_file",
                "suppl-file",
                "mediaobjects",
                "moesm",
                "/mmc",
                "downloadsupplement",
                "/doi/suppl/",
                "/cms/attachment/",
                "type=supplementary",
                "article_deployments",
                "/content/suppl/",
            )
        )
    )


def _strip_markup(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).replace("\n", " ").strip()


def _absolute_url(page_url: str, href: str) -> str | None:
    cleaned = href.strip()
    if cleaned.startswith("//"):
        cleaned = f"{urlparse(page_url).scheme or 'https'}:{cleaned}"
    absolute = urljoin(page_url, cleaned)
    absolute, _fragment = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return absolute


def _classify_link(source_url: str, text: str | None) -> str | None:
    parsed = urlparse(source_url)
    host = parsed.netloc.casefold()
    path = unquote(parsed.path).casefold()
    query = unquote(parsed.query).casefold()
    label = (text or "").casefold()
    haystack = f"{path} {query} {label}"
    suffix = _suffix_from_url(source_url)
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif"}
    table_exts = {".csv", ".tsv", ".xls", ".xlsx", ".xlsm"}
    supp_exts = table_exts | {".zip", ".doc", ".docx", ".ppt", ".pptx", ".pdf"}

    has_source = any(
        term in haystack
        for term in ("source-data", "source_data", "sourcedata", "source data", "raw data", "underlying data", "data sheet", "data_sheet")
    )
    has_supp = any(term in haystack for term in ("supplement", "supplementary", "supplemental", "additional file", "extended data", "supporting information", "esm", "moesm"))
    has_figure = any(term in haystack for term in ("figure", "fig.", "fig_", "fig-", "panel"))
    has_pdf = "pdf" in haystack or suffix == ".pdf"
    has_publisher_supplement = _is_publisher_supplement(host, path, query)

    if has_publisher_supplement:
        if has_source:
            return "source_data"
        if suffix in table_exts:
            return "supplementary_table"
        if suffix in image_exts:
            return "supplementary_image"
        return "supplementary_data"
    if suffix in table_exts and has_source:
        return "source_data"
    if has_source and suffix not in image_exts:
        return "source_data"
    if suffix in image_exts and has_supp:
        return "supplementary_image"
    if suffix in image_exts and "ncbi.nlm.nih.gov" in host and "/pmc/blobs/" in path:
        return "figure_image"
    if suffix in image_exts and has_figure:
        return "figure_image"
    if has_supp and suffix in supp_exts:
        return "supplementary_data"
    if suffix in table_exts:
        return "supplementary_table"
    if suffix == ".pdf" and has_pdf and not has_supp:
        return "paper_pdf"
    return None


def _is_publisher_supplement(host: str, path: str, query: str) -> bool:
    haystack = f"{host} {path} {query}"
    if "static-content.springer.com" in host and ("/esm/" in path or "mediaobjects" in path or "moesm" in path):
        return True
    if "nature.com" in host and ("moesm" in path or "supplementary" in haystack):
        return True
    if ("sciencedirect.com" in host or "elsevier" in host or "els-cdn.com" in host) and re.search(r"/mmc\d+(?:$|[/?#])", path):
        return True
    if "onlinelibrary.wiley.com" in host and ("/doi/suppl/" in path or "downloadsupplement" in path or "supinfo" in haystack):
        return True
    if "cell.com" in host and "/cms/attachment/" in path:
        return True
    if "journals.plos.org" in host and ("/article/file" in path or "type=supplementary" in query):
        return True
    if "mdpi.com" in host and ("article_deployments" in path or "supplementary" in haystack):
        return True
    if "frontiersin.org" in host and ("supplementary-material" in haystack or "data_sheet" in haystack or "data-sheet" in haystack):
        return True
    if "tandfonline.com" in host and ("/doi/suppl/" in path or "suppl_file" in haystack or "download" in path):
        return True
    if host.endswith("bmj.com") and "/content/suppl/" in path:
        return True
    return False


def _content_type_from_url(source_url: str) -> str | None:
    suffix = _suffix_from_url(source_url)
    return {
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".zip": "application/zip",
    }.get(suffix)


def _dedupe_urls(urls: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result = []
    for url in urls:
        if not url:
            continue
        normalized, _fragment = urldefrag(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _download_bytes(
    source_url: str,
    *,
    max_bytes: int,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    _validate_fetch_url(source_url)
    _respect_host_throttle(source_url)
    close_client = http_client is None
    client = http_client or httpx.Client(timeout=get_settings().http_timeout_seconds, follow_redirects=True)
    try:
        response = client.get(source_url, follow_redirects=True)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"remote artifact exceeds max_bytes ({max_bytes})")
        content = response.content
        if len(content) > max_bytes:
            raise ValueError(f"remote artifact exceeds max_bytes ({max_bytes})")
        if not content:
            raise ValueError("remote artifact is empty")
        return {
            "content": content,
            "content_type": _content_type(response.headers.get("content-type")),
            "filename": _filename_from_content_disposition(response.headers.get("content-disposition")),
            "final_url": str(response.url),
        }
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"remote artifact fetch failed with HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"remote artifact fetch failed: {exc}") from exc
    finally:
        if close_client:
            client.close()


def _validate_fetch_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("artifact fetch only supports http and https source_url values")
    settings = get_settings()
    if settings.artifact_fetch_allow_private_networks:
        return
    host = parsed.hostname
    if not host:
        raise ValueError("artifact fetch source_url must include a hostname")
    for address in _resolved_host_addresses(host):
        if _is_private_fetch_address(address):
            raise ValueError("artifact fetch refuses private, loopback, link-local, multicast or reserved network addresses")


def _content_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _validate_fetch_license(license_status: str) -> None:
    normalized = (license_status or "").strip().lower()
    if normalized not in FETCHABLE_LICENSE_STATUSES:
        allowed = ", ".join(sorted(FETCHABLE_LICENSE_STATUSES))
        raise ValueError(f"artifact fetch requires an explicit fetchable license_status ({allowed})")


def _validate_downloaded_artifact_payload(
    *,
    artifact_type: str,
    source_url: str,
    filename: str | None,
    content_type: str | None,
) -> None:
    normalized_type = artifact_type.strip().lower()
    normalized_content_type = _content_type(content_type)
    suffix = Path(filename or _filename_from_url(source_url) or "").suffix.casefold() or _suffix_from_url(source_url)
    if normalized_content_type in HTML_CONTENT_TYPES and normalized_type not in LANDING_ARTIFACT_TYPES:
        raise ValueError("remote artifact fetch returned an HTML page instead of an auditable file")
    if normalized_type in PDF_ARTIFACT_TYPES and normalized_content_type and normalized_content_type != "application/pdf":
        if suffix != ".pdf" and normalized_content_type != "application/octet-stream":
            raise ValueError(f"paper_pdf fetch returned incompatible content type: {normalized_content_type}")
    if normalized_type in IMAGE_ARTIFACT_TYPES and normalized_content_type and not normalized_content_type.startswith("image/"):
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif"} and normalized_content_type != "application/octet-stream":
            raise ValueError(f"image artifact fetch returned incompatible content type: {normalized_content_type}")


def _respect_host_throttle(source_url: str) -> None:
    min_interval = get_settings().artifact_fetch_min_interval_seconds
    if min_interval <= 0:
        return
    host = (urlparse(source_url).hostname or "").casefold()
    if not host:
        return
    with _FETCH_THROTTLE_LOCK:
        now = time.monotonic()
        wait_seconds = min_interval - (now - _LAST_FETCH_BY_HOST.get(host, 0.0))
        if wait_seconds > 0:
            time.sleep(wait_seconds)
            now = time.monotonic()
        _LAST_FETCH_BY_HOST[host] = now


def _resolved_host_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        records = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for record in records:
        sockaddr = record[4]
        if not sockaddr:
            continue
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    return addresses


def _is_private_fetch_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', value, flags=re.IGNORECASE)
    if not match:
        return None
    return unquote(match.group(1)).strip() or None


def _filename_from_url(source_url: str) -> str | None:
    path = unquote(urlparse(source_url).path)
    name = Path(path).name.strip()
    if name:
        return name
    for key, value in parse_qsl(urlparse(source_url).query):
        if key.casefold() in {"file", "filename", "download", "name"} and Path(value).name.strip():
            return Path(value).name.strip()
    return None


def _suffix_from_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    suffix = Path(unquote(parsed.path)).suffix.casefold()
    if suffix:
        return suffix
    for key, value in parse_qsl(parsed.query):
        if key.casefold() in {"file", "filename", "download", "name"}:
            suffix = Path(unquote(value)).suffix.casefold()
            if suffix:
                return suffix
    return ""
