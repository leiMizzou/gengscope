from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from gengscope_api.config import get_settings
from gengscope_api.db.models import AlgorithmicSignal, Paper, ReviewTask, SourceArtifact
from gengscope_api.services import artifacts as artifact_service


def test_upload_numeric_audit_and_review_decision_loop(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text

    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    csv_content = "\n".join(
        [
            "replicate,tumor_a,tumor_b,tumor_copy,last_digit",
            "r1,1.10,4.11,1.10,10",
            "r2,2.20,5.12,2.20,20",
            "r3,3.30,6.13,3.30,30",
            "r4,4.40,7.14,4.40,40",
            "r5,5.50,8.15,5.50,50",
            "r6,6.60,9.16,6.60,60",
            "r7,7.70,10.17,7.70,70",
            "r8,8.80,11.18,8.80,80",
            "r9,9.90,12.19,9.90,90",
            "r10,10.00,13.10,10.00,100",
        ]
    )

    upload_response = api_client.post(
        "/api/artifacts/upload",
        data={"doi": paper.doi, "artifact_type": "source_data", "license_status": "manual_upload"},
        files={"file": ("source-data.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded = upload_response.json()
    artifact_id = uploaded["artifact"]["id"]
    assert uploaded["material_status"] == "full_auditable"
    assert uploaded["artifact"]["checksum_sha256"]

    artifact = db_session.get(SourceArtifact, artifact_id)
    assert artifact is not None
    assert artifact.storage_uri is not None

    audit_response = api_client.post(
        "/api/audits/numeric",
        json={"artifact_id": artifact_id, "min_duplicate_length": 3, "min_last_digit_sample": 10, "priority": 8},
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["analyzed_rows"] == 10
    assert audit["analyzed_numeric_columns"] == 4
    assert audit["signal_count"] >= 2
    assert audit["created_review_tasks"] == audit["signal_count"]
    assert {signal["signal_type"] for signal in audit["signals"]} >= {
        "numeric_duplicate_sequence",
        "numeric_last_digit_anomaly",
    }
    assert "不能单独证明" in audit["conclusion_boundary"]

    tasks_response = api_client.get("/api/review/tasks")
    assert tasks_response.status_code == 200, tasks_response.text
    tasks = tasks_response.json()
    assert tasks["total"] == audit["signal_count"]
    first_task = tasks["items"][0]
    assert first_task["paper"]["doi"] == "10.1234/example.paper"
    assert first_task["signal"]["status"] == "needs_review"

    decision_response = api_client.post(
        f"/api/review/tasks/{first_task['id']}/decision",
        json={"decision": "confirmed_signal", "reviewer_note": "fixture confirms expected numeric anomaly"},
    )
    assert decision_response.status_code == 200, decision_response.text
    decided = decision_response.json()
    assert decided["status"] == "closed"
    assert decided["decision"] == "confirmed_signal"
    assert decided["signal"]["status"] == "confirmed_signal"

    signal = db_session.get(AlgorithmicSignal, decided["signal"]["id"])
    assert signal is not None
    assert signal.status == "confirmed_signal"

    rerun_response = api_client.post(
        "/api/audits/numeric",
        json={"artifact_id": artifact_id, "min_duplicate_length": 3, "min_last_digit_sample": 10, "priority": 8},
    )
    assert rerun_response.status_code == 200, rerun_response.text
    rerun = rerun_response.json()
    assert rerun["signal_count"] == audit["signal_count"]
    assert rerun["created_review_tasks"] == 0

    review_tasks = db_session.scalars(select(ReviewTask).where(ReviewTask.paper_id == paper.id)).all()
    assert len(review_tasks) == audit["signal_count"]


def test_numeric_audit_flags_fixed_ratio_columns(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text

    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    csv_content = "\n".join(
        [
            "replicate,dose,response_scaled,noise",
            "r1,1.00,2.00,1.13",
            "r2,2.00,4.00,1.29",
            "r3,3.00,6.00,1.41",
            "r4,4.00,8.00,1.58",
            "r5,5.00,10.00,1.62",
            "r6,6.00,12.00,1.79",
            "r7,7.00,14.00,1.83",
            "r8,8.00,16.00,1.96",
        ]
    )

    upload_response = api_client.post(
        "/api/artifacts/upload",
        data={"doi": paper.doi, "artifact_type": "source_data", "license_status": "manual_upload"},
        files={"file": ("fixed-ratio-source-data.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert upload_response.status_code == 200, upload_response.text
    artifact_id = upload_response.json()["artifact"]["id"]

    audit_response = api_client.post(
        "/api/audits/numeric",
        json={"artifact_id": artifact_id, "min_duplicate_length": 3, "min_last_digit_sample": 10, "priority": 8},
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()

    assert audit["signal_count"] == 1
    signal = audit["signals"][0]
    assert signal["signal_type"] == "numeric_fixed_ratio_columns"
    assert signal["metrics"]["relationship"] == "fixed_ratio"
    assert signal["metrics"]["left_column"] == "dose"
    assert signal["metrics"]["right_column"] == "response_scaled"
    assert signal["metrics"]["paired_sample_size"] == 8
    assert "不能单独证明" in audit["conclusion_boundary"]


def test_fetch_remote_artifact_stores_known_url_locally(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    discover_response = api_client.post("/api/artifacts/discover", json={"paper_id": paper.id})
    assert discover_response.status_code == 200, discover_response.text
    pdf_artifact = next(item for item in discover_response.json()["items"] if item["artifact_type"] == "paper_pdf")

    def fake_download(source_url: str, *, max_bytes: int, http_client=None) -> dict:
        assert source_url == "https://example.org/paper.pdf"
        assert max_bytes > 0
        return {
            "content": b"%PDF-1.4\nfixture\n",
            "content_type": "application/pdf",
            "filename": "paper.pdf",
            "final_url": source_url,
        }

    monkeypatch.setattr(artifact_service, "_download_bytes", fake_download)

    fetch_response = api_client.post(
        "/api/artifacts/fetch",
        json={"artifact_id": pdf_artifact["id"], "license_status": "open_or_linked"},
        headers={"X-GengScope-Actor": "fetch-test"},
    )
    assert fetch_response.status_code == 200, fetch_response.text
    fetched = fetch_response.json()
    assert fetched["material_status"] == "pdf_found"
    assert fetched["artifact"]["checksum_sha256"]
    assert fetched["artifact"]["content_type"] == "application/pdf"
    assert fetched["artifact"]["filename"] == "paper.pdf"
    assert Path(fetched["artifact"]["storage_uri"]).read_bytes() == b"%PDF-1.4\nfixture\n"


def test_deep_artifact_discovery_adds_pmc_and_landing_page_links(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    paper.pmcid = "PMC7654321"
    paper.landing_page_url = "https://publisher.example/articles/demo"
    db_session.commit()

    def fake_fetch_html(page_url: str, *, http_client=None) -> str:
        assert page_url in {
            "https://publisher.example/articles/demo",
            "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/",
            "https://pubmed.ncbi.nlm.nih.gov/12345/",
        }
        return """
          <html><body>
            <a href="/articles/demo.pdf">Article PDF</a>
            <a href="/articles/source-data.xlsx">Source data</a>
            <a href="supplementary-file.zip">Supplementary materials</a>
            <a href="fig1.png">Figure 1 panel</a>
          </body></html>
        """

    monkeypatch.setattr(artifact_service, "_fetch_html", fake_fetch_html)

    discover_response = api_client.post(
        "/api/artifacts/discover",
        json={"paper_id": paper.id, "inspect_landing_pages": True, "max_landing_pages": 3, "max_discovered_links": 20},
    )
    assert discover_response.status_code == 200, discover_response.text
    result = discover_response.json()
    artifact_by_url = {item["source_url"]: item for item in result["items"]}
    assert "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/" in artifact_by_url
    assert "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/pdf/" in artifact_by_url
    assert artifact_by_url["https://publisher.example/articles/source-data.xlsx"]["artifact_type"] == "source_data"
    assert artifact_by_url["https://publisher.example/articles/supplementary-file.zip"]["artifact_type"] == "supplementary_data"
    assert artifact_by_url["https://publisher.example/articles/fig1.png"]["artifact_type"] == "figure_image"
    assert result["discovered_link_count"] >= 4
    assert len(result["inspected_landing_pages"]) == 3
    assert result["discovery_errors"] == []


def test_deep_discovery_prioritizes_pmc_page_and_extracts_figure_images(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    paper.landing_page_url = "https://publisher.example/articles/demo"
    db_session.add(
        SourceArtifact(
            paper=paper,
            artifact_type="publisher_landing_page",
            source_url="https://www.ncbi.nlm.nih.gov/pmc/articles/7654321",
            license_status="unknown",
        )
    )
    db_session.commit()

    def fake_fetch_html(page_url: str, *, http_client=None) -> str:
        assert page_url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/"
        return """
          <html><body>
            <img class="graphic"
                 src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/abcd/7654321/demo.001.jpg"
                 alt="Figure 1">
          </body></html>
        """

    monkeypatch.setattr(artifact_service, "_fetch_html", fake_fetch_html)

    discover_response = api_client.post(
        "/api/artifacts/discover",
        json={"paper_id": paper.id, "inspect_landing_pages": True, "max_landing_pages": 1, "max_discovered_links": 10},
    )
    assert discover_response.status_code == 200, discover_response.text
    result = discover_response.json()
    artifact_by_url = {item["source_url"]: item for item in result["items"]}
    assert result["inspected_landing_pages"] == ["https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/"]
    assert (
        artifact_by_url["https://cdn.ncbi.nlm.nih.gov/pmc/blobs/abcd/7654321/demo.001.jpg"]["artifact_type"]
        == "figure_image"
    )


def test_deep_discovery_extracts_publisher_embedded_assets(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    paper.landing_page_url = "https://www.nature.com/articles/s41586-024-08248-5"
    db_session.commit()

    def fake_fetch_html(page_url: str, *, http_client=None) -> str:
        assert page_url == "https://www.nature.com/articles/s41586-024-08248-5"
        return """
          <html><head>
            <meta name="citation_pdf_url" content="https://www.nature.com/articles/s41586-024-08248-5.pdf">
            <meta name="citation_supplementary_material"
                  content="https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-08248-5/MediaObjects/41586_2024_8248_MOESM1_ESM.pdf">
          </head><body>
            <script type="application/json">
              {"downloadUrl":"https:\\/\\/static-content.springer.com\\/esm\\/art%3A10.1038%2Fs41586-024-08248-5\\/MediaObjects\\/41586_2024_8248_MOESM2_ESM.xlsx","label":"Source data"}
            </script>
          </body></html>
        """

    monkeypatch.setattr(artifact_service, "_fetch_html", fake_fetch_html)

    discover_response = api_client.post(
        "/api/artifacts/discover",
        json={"paper_id": paper.id, "inspect_landing_pages": True, "max_landing_pages": 1, "max_discovered_links": 20},
    )
    assert discover_response.status_code == 200, discover_response.text
    artifact_by_url = {item["source_url"]: item for item in discover_response.json()["items"]}
    assert artifact_by_url["https://www.nature.com/articles/s41586-024-08248-5.pdf"]["artifact_type"] == "paper_pdf"
    assert (
        artifact_by_url[
            "https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-08248-5/MediaObjects/41586_2024_8248_MOESM1_ESM.pdf"
        ]["artifact_type"]
        == "supplementary_data"
    )
    assert (
        artifact_by_url[
            "https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-08248-5/MediaObjects/41586_2024_8248_MOESM2_ESM.xlsx"
        ]["artifact_type"]
        == "source_data"
    )


def test_deep_discovery_classifies_elsevier_and_wiley_supplements(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    paper.landing_page_url = "https://www.sciencedirect.com/science/article/pii/S1234567890123456"
    db_session.commit()

    def fake_fetch_html(page_url: str, *, http_client=None) -> str:
        assert page_url == "https://www.sciencedirect.com/science/article/pii/S1234567890123456"
        return """
          <html><body>
            <a href="/science/article/pii/S1234567890123456/mmc1">Supplementary material 1</a>
            <script>
              window.assets = ["https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1002/example&file=abc-sup-0001-TableS1.xlsx"];
            </script>
          </body></html>
        """

    monkeypatch.setattr(artifact_service, "_fetch_html", fake_fetch_html)

    discover_response = api_client.post(
        "/api/artifacts/discover",
        json={"paper_id": paper.id, "inspect_landing_pages": True, "max_landing_pages": 1, "max_discovered_links": 20},
    )
    assert discover_response.status_code == 200, discover_response.text
    artifact_by_url = {item["source_url"]: item for item in discover_response.json()["items"]}
    assert artifact_by_url["https://www.sciencedirect.com/science/article/pii/S1234567890123456/mmc1"]["artifact_type"] == "supplementary_data"
    assert (
        artifact_by_url[
            "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1002/example&file=abc-sup-0001-TableS1.xlsx"
        ]["artifact_type"]
        == "supplementary_table"
    )


def test_deep_discovery_classifies_more_publisher_supplements(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()
    paper.landing_page_url = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001"
    db_session.commit()

    def fake_fetch_html(page_url: str, *, http_client=None) -> str:
        assert page_url == "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000001"
        return """
          <html><body>
            <a href="https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0000001.s001">Source data</a>
            <a href="https://www.mdpi.com/article_deployments/12345/attachment/supplementary/sensors-01-00001-s001.xlsx">Source data workbook</a>
            <a href="https://www.frontiersin.org/files/Articles/123456/fncel-13-123456-HTML-r1/data_sheet_1.xlsx">Data Sheet 1</a>
            <a href="https://www.tandfonline.com/doi/suppl/10.1080/example/suppl_file/example_suppl.xlsx">Supplementary table</a>
            <a href="https://gut.bmj.com/content/gutjnl/early/2026/01/01/gutjnl-2026-000001/DC1/embed/inline-supplementary-material-1.pdf">Supplementary PDF</a>
          </body></html>
        """

    monkeypatch.setattr(artifact_service, "_fetch_html", fake_fetch_html)

    discover_response = api_client.post(
        "/api/artifacts/discover",
        json={"paper_id": paper.id, "inspect_landing_pages": True, "max_landing_pages": 1, "max_discovered_links": 20},
    )
    assert discover_response.status_code == 200, discover_response.text
    artifact_by_url = {item["source_url"]: item for item in discover_response.json()["items"]}
    assert (
        artifact_by_url[
            "https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0000001.s001"
        ]["artifact_type"]
        == "source_data"
    )
    assert (
        artifact_by_url["https://www.mdpi.com/article_deployments/12345/attachment/supplementary/sensors-01-00001-s001.xlsx"][
            "artifact_type"
        ]
        == "source_data"
    )
    assert (
        artifact_by_url["https://www.frontiersin.org/files/Articles/123456/fncel-13-123456-HTML-r1/data_sheet_1.xlsx"][
            "artifact_type"
        ]
        == "source_data"
    )
    assert (
        artifact_by_url["https://www.tandfonline.com/doi/suppl/10.1080/example/suppl_file/example_suppl.xlsx"]["artifact_type"]
        == "supplementary_table"
    )
    assert (
        artifact_by_url[
            "https://gut.bmj.com/content/gutjnl/early/2026/01/01/gutjnl-2026-000001/DC1/embed/inline-supplementary-material-1.pdf"
        ]["artifact_type"]
        == "supplementary_data"
    )


def test_remote_artifact_fetch_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http and https"):
        artifact_service._download_bytes("file:///tmp/paper.pdf", max_bytes=1024)


def test_remote_artifact_fetch_rejects_private_networks_by_default(monkeypatch) -> None:
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="private"):
            artifact_service._validate_fetch_url("http://127.0.0.1:8000/private.csv")
        with pytest.raises(ValueError, match="private"):
            artifact_service._validate_fetch_url("http://localhost:8000/private.csv")
    finally:
        get_settings.cache_clear()


def test_remote_artifact_fetch_private_network_override(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS", "1")
    get_settings.cache_clear()
    try:
        artifact_service._validate_fetch_url("http://127.0.0.1:8000/private.csv")
    finally:
        get_settings.cache_clear()


def test_remote_artifact_fetch_requires_fetchable_license(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    def fake_download(source_url: str, *, max_bytes: int, http_client=None) -> dict:
        return {
            "content": b"%PDF-1.4\nfixture\n",
            "content_type": "application/pdf",
            "filename": "paper.pdf",
            "final_url": source_url,
        }

    monkeypatch.setattr(artifact_service, "_download_bytes", fake_download)

    response = api_client.post(
        "/api/artifacts/fetch",
        json={
            "paper_id": paper.id,
            "artifact_type": "paper_pdf",
            "source_url": "https://example.org/paper.pdf",
            "license_status": "reference_only",
        },
    )
    assert response.status_code == 422
    assert "fetchable license_status" in response.json()["detail"]


def test_remote_artifact_fetch_rejects_html_payload_for_auditable_file(api_client, db_session, monkeypatch) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).one()

    def fake_download(source_url: str, *, max_bytes: int, http_client=None) -> dict:
        return {
            "content": b"<html><body>not a pdf</body></html>",
            "content_type": "text/html",
            "filename": "paper.html",
            "final_url": source_url,
        }

    monkeypatch.setattr(artifact_service, "_download_bytes", fake_download)

    response = api_client.post(
        "/api/artifacts/fetch",
        json={
            "paper_id": paper.id,
            "artifact_type": "paper_pdf",
            "source_url": "https://example.org/paper.pdf",
            "license_status": "open_or_linked",
        },
    )
    assert response.status_code == 422
    assert "HTML page" in response.json()["detail"]


def test_artifact_fetch_host_throttle_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_FETCH_MIN_INTERVAL_SECONDS", "0.5")
    get_settings.cache_clear()
    artifact_service._LAST_FETCH_BY_HOST.clear()
    current_time = {"value": 100.0}
    sleeps = []

    def fake_monotonic() -> float:
        return current_time["value"]

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        current_time["value"] += seconds

    monkeypatch.setattr(artifact_service.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(artifact_service.time, "sleep", fake_sleep)
    try:
        artifact_service._respect_host_throttle("https://example.org/one.csv")
        artifact_service._respect_host_throttle("https://example.org/two.csv")
    finally:
        get_settings.cache_clear()
        artifact_service._LAST_FETCH_BY_HOST.clear()

    assert sleeps == [0.5]
