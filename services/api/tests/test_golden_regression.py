from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy import select

from gengscope_api.db.models import Paper


GOLDEN_CASES = json.loads(
    (Path(__file__).resolve().parents[3] / "data" / "seeds" / "golden_algorithm_cases.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[case["id"] for case in GOLDEN_CASES])
def test_golden_algorithm_case(case: dict[str, Any], api_client, db_session) -> None:
    _assert_review_label_contract(case)
    corpus_response = api_client.post("/api/entities/corpus", json=case["entity"])
    assert corpus_response.status_code == 200, corpus_response.text
    entity_id = corpus_response.json()["entity"]["id"]

    if case["analyzer"] == "numeric":
        _assert_numeric_golden_case(api_client, case)
    elif case["analyzer"] == "image":
        _assert_image_golden_case(api_client, db_session, case)
    elif case["analyzer"] == "metadata":
        _assert_metadata_golden_case(api_client, case, entity_id)
    else:
        raise AssertionError(f"Unsupported analyzer in golden case: {case['analyzer']}")


def _assert_numeric_golden_case(api_client, case: dict[str, Any]) -> None:
    artifact = case["artifact"]
    upload_response = api_client.post(
        "/api/artifacts/upload",
        data={"doi": artifact["doi"], "artifact_type": artifact["artifact_type"], "license_status": "golden_fixture"},
        files={
            "file": (
                artifact["filename"],
                "\n".join(artifact["csv_lines"]).encode("utf-8"),
                artifact["content_type"],
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    artifact_id = upload_response.json()["artifact"]["id"]

    audit_response = api_client.post("/api/audits/numeric", json={"artifact_id": artifact_id, **case["request"]})
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    expected = case["expected"]
    if "signal_count" in expected:
        assert audit["signal_count"] == expected["signal_count"]
    else:
        assert audit["signal_count"] >= expected["min_signal_count"]
    assert {signal["signal_type"] for signal in audit["signals"]} >= set(expected["signal_types"])
    assert audit["created_review_tasks"] == audit["signal_count"]
    assert "不能单独证明" in audit["conclusion_boundary"]


def _assert_review_label_contract(case: dict[str, Any]) -> None:
    expected = case["expected"]
    assert expected["human_review_label"] in {"review_required", "expected_negative", "expected_low_priority"}
    assert expected["expected_review_decision"] in {
        "confirmed_signal",
        "false_positive",
        "not_actionable",
        "needs_more_evidence",
    }
    assert expected["misconduct_conclusion"] is False


def _assert_image_golden_case(api_client, db_session, case: dict[str, Any]) -> None:
    paper = db_session.scalars(select(Paper).where(Paper.doi == case["artifact"]["doi"])).one()
    base, transformed = _image_fixture(case["artifact"]["fixture"])
    base_response = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "golden_fixture"},
        files={"file": ("golden-base.png", _png_bytes(base), "image/png")},
    )
    assert base_response.status_code == 200, base_response.text
    transformed_response = api_client.post(
        "/api/artifacts/upload",
        data={"paper_id": paper.id, "artifact_type": "figure_image", "license_status": "golden_fixture"},
        files={"file": ("golden-transformed.png", _png_bytes(transformed), "image/png")},
    )
    assert transformed_response.status_code == 200, transformed_response.text

    audit_response = api_client.post(
        "/api/audits/image",
        json={
            "artifact_id": base_response.json()["artifact"]["id"],
            "compare_artifact_ids": [transformed_response.json()["artifact"]["id"]],
            **case["request"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    expected = case["expected"]
    assert audit["signal_count"] == expected["signal_count"]
    if expected["signal_count"] == 0:
        assert audit["created_review_tasks"] == 0
        assert "不能单独证明" in audit["conclusion_boundary"]
        return
    signal = audit["signals"][0]
    assert signal["signal_type"] == expected["signal_type"]
    if "transform" in expected:
        assert signal["metrics"]["transform"] == expected["transform"]
    if "comparison" in expected:
        assert signal["metrics"]["comparison"] == expected["comparison"]
    assert "不能单独证明" in audit["conclusion_boundary"]


def _assert_metadata_golden_case(api_client, case: dict[str, Any], entity_id: str) -> None:
    audit_response = api_client.post(
        "/api/audits/metadata",
        json={"entity_type": case["entity"]["entity_type"], "entity_id": entity_id, **case["request"]},
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    expected = case["expected"]
    assert audit["signal_count"] == expected["signal_count"]
    assert audit["created_review_tasks"] == expected["created_review_tasks"]
    assert {signal["signal_type"] for signal in audit["signals"]} == set(expected["signal_types"])
    assert "不能单独证明" in audit["conclusion_boundary"]


def _image_fixture(name: str) -> tuple[Image.Image, Image.Image]:
    if name == "flip_pair_64":
        base = Image.new("RGB", (64, 64), "white")
        draw = ImageDraw.Draw(base)
        draw.rectangle((6, 10, 28, 44), fill="black")
        draw.rectangle((34, 20, 42, 56), fill="gray")
        return base, ImageOps.mirror(base)
    if name == "patch_pair_128":
        base = Image.new("RGB", (128, 128), "white")
        patch = Image.new("RGB", (32, 32), "white")
        patch_draw = ImageDraw.Draw(patch)
        patch_draw.rectangle((4, 4, 26, 12), fill="black")
        patch_draw.ellipse((8, 16, 28, 28), fill="gray")
        base.paste(patch, (0, 0))
        peer = Image.new("RGB", (128, 128), "white")
        peer_draw = ImageDraw.Draw(peer)
        peer_draw.rectangle((8, 72, 54, 110), fill="lightgray")
        peer.paste(patch, (96, 96))
        return base, peer
    if name == "distinct_pair_64":
        base = Image.new("RGB", (64, 64), "white")
        base_draw = ImageDraw.Draw(base)
        base_draw.rectangle((4, 6, 20, 24), fill="black")
        base_draw.line((2, 58, 58, 2), fill="gray", width=3)
        peer = Image.new("RGB", (64, 64), "white")
        peer_draw = ImageDraw.Draw(peer)
        peer_draw.ellipse((34, 8, 58, 32), fill="black")
        peer_draw.rectangle((8, 42, 48, 54), fill="gray")
        return base, peer
    raise AssertionError(f"Unsupported image fixture: {name}")


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
