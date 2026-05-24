from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import select

from gengscope_api.db.models import Paper


def test_image_audit_flags_flipped_panel_pair(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    base = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(base)
    draw.rectangle((6, 10, 28, 44), fill="black")
    draw.rectangle((34, 20, 42, 56), fill="gray")
    flipped = ImageOps.mirror(base)

    base_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-1a.png", _png_bytes(base), "image/png")},
    )
    assert base_upload.status_code == 200, base_upload.text
    base_artifact_id = base_upload.json()["artifact"]["id"]

    flipped_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-2b.png", _png_bytes(flipped), "image/png")},
    )
    assert flipped_upload.status_code == 200, flipped_upload.text
    flipped_artifact_id = flipped_upload.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": base_artifact_id,
            "compare_artifact_ids": [flipped_artifact_id],
            "max_hamming_distance": 4,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["compared_artifact_count"] == 1
    assert audit["signal_count"] == 1
    assert audit["created_review_tasks"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "image_panel_similarity"
    assert signal["severity"] == "high"
    assert signal["metrics"]["matched_artifact_id"] == flipped_artifact_id
    assert signal["metrics"]["transform"] == "flip_horizontal"
    assert "不能单独证明" in audit["conclusion_boundary"]


def test_image_audit_flags_cropped_patch_reuse(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    base = Image.new("RGB", (96, 96), "white")
    draw = ImageDraw.Draw(base)
    for y in range(0, 24, 4):
        for x in range(0, 24, 4):
            if (x // 4 + y // 4) % 2 == 0:
                draw.rectangle((x, y, x + 3, y + 3), fill="black")
    draw.rectangle((52, 52, 78, 72), fill="gray")
    cropped = base.crop((0, 0, 24, 24))

    base_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-full.png", _png_bytes(base), "image/png")},
    )
    assert base_upload.status_code == 200, base_upload.text
    base_artifact_id = base_upload.json()["artifact"]["id"]

    cropped_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-crop.png", _png_bytes(cropped), "image/png")},
    )
    assert cropped_upload.status_code == 200, cropped_upload.text
    cropped_artifact_id = cropped_upload.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": base_artifact_id,
            "compare_artifact_ids": [cropped_artifact_id],
            "max_hamming_distance": 2,
            "max_patch_hamming_distance": 0,
            "patch_grid_size": 4,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["signal_count"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "image_patch_similarity"
    assert signal["metrics"]["matched_artifact_id"] == cropped_artifact_id
    assert signal["metrics"]["target_region"]["label"] == "r0c0"
    assert signal["metrics"]["matched_region"]["label"] == "full"
    assert signal["metrics"]["comparison"] == "patch_similarity"


def test_image_audit_flags_internal_patch_reuse(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    figure = Image.new("RGB", (96, 96), "white")
    patch = Image.new("RGB", (24, 24), "white")
    draw = ImageDraw.Draw(patch)
    for y in range(0, 24, 4):
        for x in range(0, 24, 4):
            if (x // 4 + y // 4) % 2 == 0:
                draw.rectangle((x, y, x + 3, y + 3), fill="black")
    figure.paste(patch, (0, 0))
    figure.paste(patch, (48, 48))
    draw = ImageDraw.Draw(figure)
    draw.rectangle((72, 8, 88, 34), fill="gray")

    upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-internal-dup.png", _png_bytes(figure), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    artifact_id = upload.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": artifact_id,
            "max_hamming_distance": 0,
            "max_patch_hamming_distance": 0,
            "patch_grid_size": 4,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["signal_count"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "image_internal_patch_similarity"
    assert signal["metrics"]["matched_artifact_id"] == artifact_id
    assert signal["metrics"]["comparison"] == "internal_patch_similarity"


def test_image_audit_flags_internal_patch_reuse_on_finer_grid(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    figure = Image.new("RGB", (120, 120), "white")
    patch = Image.new("RGB", (24, 24), "white")
    draw = ImageDraw.Draw(patch)
    for index in range(12):
        x = 2 + (index * 7) % 18
        y = 2 + (index * 11) % 18
        draw.rectangle((x, y, x + 3, y + 3), fill=(20 + index * 12, 40, 130))
    figure.paste(patch, (24, 48))
    figure.paste(patch, (72, 48))
    draw = ImageDraw.Draw(figure)
    draw.rectangle((4, 8, 18, 38), fill="gray")

    upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-internal-fine-grid.png", _png_bytes(figure), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    artifact_id = upload.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": artifact_id,
            "max_hamming_distance": 0,
            "max_patch_hamming_distance": 0,
            "patch_grid_size": 4,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["signal_count"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "image_internal_patch_similarity"
    assert signal["metrics"]["comparison"] == "internal_patch_similarity"
    assert signal["metrics"]["target_region"]["label"].startswith("g5:")
    assert signal["metrics"]["matched_region"]["label"].startswith("g5:")


def test_image_audit_empty_peer_list_runs_internal_only(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    figure = Image.new("RGB", (96, 96), "white")
    patch = Image.new("RGB", (24, 24), "white")
    draw = ImageDraw.Draw(patch)
    draw.rectangle((4, 4, 18, 10), fill="black")
    draw.ellipse((8, 12, 22, 22), fill="gray")
    figure.paste(patch, (0, 0))
    figure.paste(patch, (48, 48))

    matching_peer = Image.new("RGB", (96, 96), "white")
    matching_peer.paste(patch, (0, 0))
    matching_peer.paste(patch, (48, 48))

    upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-internal-only.png", _png_bytes(figure), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    artifact_id = upload.json()["artifact"]["id"]

    peer_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-peer-should-not-compare.png", _png_bytes(matching_peer), "image/png")},
    )
    assert peer_upload.status_code == 200, peer_upload.text

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": artifact_id,
            "compare_artifact_ids": [],
            "max_hamming_distance": 0,
            "max_patch_hamming_distance": 0,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["compared_artifact_count"] == 0
    assert audit["signal_count"] == 1
    assert audit["signals"][0]["signal_type"] == "image_internal_patch_similarity"
    assert audit["signals"][0]["metrics"]["matched_artifact_id"] == artifact_id


def test_image_audit_flags_shifted_correlation_panel_pair(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    field = Image.new("RGB", (180, 130), "white")
    draw = ImageDraw.Draw(field)
    for index in range(90):
        x = 8 + (index * 19) % 154
        y = 8 + (index * 29) % 106
        color = (120 + index % 50, 62 + index % 45, 76 + index % 40)
        draw.ellipse((x, y, x + 8 + index % 5, y + 4 + index % 4), fill=color)
    draw.ellipse((96, 52, 126, 82), fill=(228, 204, 205), outline=(180, 126, 139))
    base = field.crop((12, 10, 156, 110))
    shifted = field.crop((12, 13, 156, 113))

    base_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-shift-a.png", _png_bytes(base), "image/png")},
    )
    assert base_upload.status_code == 200, base_upload.text
    base_artifact_id = base_upload.json()["artifact"]["id"]

    shifted_upload = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "manual_upload"},
        files={"file": ("fig-shift-b.png", _png_bytes(shifted), "image/png")},
    )
    assert shifted_upload.status_code == 200, shifted_upload.text
    shifted_artifact_id = shifted_upload.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": base_artifact_id,
            "compare_artifact_ids": [shifted_artifact_id],
            "max_hamming_distance": 0,
            "enable_patch_similarity": False,
            "min_shift_correlation": 0.86,
            "priority": 9,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["signal_count"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "image_shift_correlation"
    assert signal["metrics"]["matched_artifact_id"] == shifted_artifact_id
    assert signal["metrics"]["comparison"] == "shift_tolerant_normalized_correlation"
    assert signal["metrics"]["max_correlation"] >= 0.86


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
