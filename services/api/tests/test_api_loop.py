from __future__ import annotations

from urllib.parse import quote

from tests.conftest import SAMPLE_DOI


def test_http_metadata_event_risk_agent_loop(api_client) -> None:
    import_response = api_client.post(
        "/api/admin/import/doi",
        json={"doi": f"https://doi.org/{SAMPLE_DOI}", "sources": ["openalex", "crossref"]},
    )
    assert import_response.status_code == 200, import_response.text
    imported = import_response.json()
    assert imported["doi"] == SAMPLE_DOI
    assert imported["authorship_count"] == 2
    assert imported["source_record_count"] == 2

    event_response = api_client.post(
        "/api/admin/events",
        json={
            "doi": SAMPLE_DOI,
            "event_type": "institution_notice",
            "status_level": "institution_investigation",
            "source_type": "institution",
            "source_name": "Example University",
            "source_url": "https://example.edu/notice",
            "event_date": "2026-05-12",
            "claim_summary": "机构公告称已成立调查组。",
            "verification_status": "source_verified",
        },
    )
    assert event_response.status_code == 200, event_response.text

    encoded = quote(SAMPLE_DOI, safe="")
    detail_response = api_client.get(f"/api/papers/{encoded}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["paper"]["title"] == "Example integrity metadata paper"
    assert len(detail["authorships"]) == 2
    assert detail["authorships"][0]["author_id"]
    assert detail["authorships"][0]["institution_id"]
    assert detail["authorships"][0]["institution_display_name"] == "Example University"
    assert detail["risk_status"]["institution_status"] == "investigation"

    risk_response = api_client.get(f"/api/papers/{encoded}/risk-card")
    assert risk_response.status_code == 200, risk_response.text
    risk = risk_response.json()
    assert risk["highest_signal_level"] == "investigation"
    assert "机构调查" in risk["summary"]

    agent_response = api_client.get(f"/api/agent/doi/{encoded}")
    assert agent_response.status_code == 200, agent_response.text
    agent = agent_response.json()
    assert agent["paper"]["doi"] == SAMPLE_DOI
    assert agent["risk_card"]["institution_status"] == "investigation"
    assert "不能据此直接认定论文造假" in agent["conclusion_boundary"]


def test_batch_agent_reports_missing_doi(api_client) -> None:
    response = api_client.post("/api/agent/batch-risk-cards", json={"dois": [SAMPLE_DOI]})
    assert response.status_code == 200
    assert response.json()["items"][0]["error"] == "paper_not_found"
