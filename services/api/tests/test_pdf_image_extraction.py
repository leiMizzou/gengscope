from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from gengscope_api.db.models import Paper


fitz = pytest.importorskip("fitz")


def test_extract_pdf_images_creates_figure_artifacts(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    upload_response = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "paper_pdf", "license_status": "manual_upload"},
        files={"file": ("paper-with-images.pdf", _pdf_with_images(), "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    pdf_artifact_id = upload_response.json()["artifact"]["id"]

    extract_response = api_client.post(
        "/api/artifacts/extract/pdf-images",
        json={"artifact_id": pdf_artifact_id, "max_pages": 2, "max_images": 10, "min_width": 40, "min_height": 40},
    )
    assert extract_response.status_code == 200, extract_response.text
    extracted = extract_response.json()
    assert extracted["extracted_count"] >= 2
    assert all(item["artifact_type"] == "figure_image" for item in extracted["items"])
    assert all(item["storage_uri"] for item in extracted["items"])
    assert "不能单独证明" in extracted["conclusion_boundary"]

    list_response = api_client.get(f"/api/artifacts/papers/{paper.id}")
    assert list_response.status_code == 200, list_response.text
    figure_items = [item for item in list_response.json()["items"] if item["artifact_type"] == "figure_image"]
    assert len(figure_items) >= 2


def _pdf_with_images() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320, height=220)
    page.insert_image(fitz.Rect(28, 28, 138, 138), stream=_png_bytes("black", "gray"))
    page.insert_image(fitz.Rect(166, 34, 286, 154), stream=_png_bytes("navy", "white"))
    return doc.tobytes()


def _png_bytes(primary: str, secondary: str) -> bytes:
    image = Image.new("RGB", (96, 96), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 12, 58, 76), fill=primary)
    draw.ellipse((32, 28, 86, 84), outline=secondary, width=5)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
