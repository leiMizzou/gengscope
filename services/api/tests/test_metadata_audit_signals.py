from __future__ import annotations

from sqlalchemy import select

from gengscope_api.db.models import AlgorithmicSignal, Author, Authorship, Institution, Paper, ReviewTask


def test_metadata_audit_creates_entity_signals_and_browser(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    audit_response = api_client.post(
        "/api/audits/metadata",
        json={
            "entity_type": "author",
            "entity_id": author_id,
            "min_cluster_size": 2,
            "priority": 6,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    audit = audit_response.json()
    assert audit["paper_count"] == 2
    assert audit["signal_count"] == 4
    assert audit["created_review_tasks"] == 4
    assert {signal["signal_type"] for signal in audit["signals"]} == {
        "metadata_publication_year_cluster",
        "metadata_journal_cluster",
    }
    assert "不能单独证明" in audit["conclusion_boundary"]

    signals_response = api_client.get(f"/api/entities/author/{author_id}/signals")
    assert signals_response.status_code == 200, signals_response.text
    signals = signals_response.json()
    assert signals["total"] == 4
    assert signals["signal_type_counts"]["metadata_publication_year_cluster"] == 2
    assert signals["signal_type_counts"]["metadata_journal_cluster"] == 2
    assert signals["status_counts"]["needs_review"] == 4
    assert signals["items"][0]["paper"]["doi"] in {"10.1234/example.paper", "10.1234/example.second"}
    assert "不能直接认定" in signals["conclusion_boundary"]

    generic_response = api_client.get(
        "/api/signals",
        params={"entity_type": "author", "entity_id": author_id, "signal_type": "metadata_journal_cluster"},
    )
    assert generic_response.status_code == 200, generic_response.text
    assert generic_response.json()["total"] == 2

    report_response = api_client.get(
        "/api/reports/entity",
        params={"entity_type": "author", "entity_id": author_id},
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["entity"]["display_name"] == "Alice Zhang"
    assert report["signals"]["total"] == 4
    assert report["open_review_tasks"]["total"] == 4
    assert "不能据此直接认定" in report["conclusion_boundary"]

    markdown_response = api_client.get(
        "/api/reports/entity",
        params={"entity_type": "author", "entity_id": author_id, "format": "markdown"},
    )
    assert markdown_response.status_code == 200, markdown_response.text
    assert "# GengScope Entity Report: Alice Zhang" in markdown_response.text
    assert "## Conclusion Boundary" in markdown_response.text

    rerun_response = api_client.post(
        "/api/audits/metadata",
        json={
            "entity_type": "author",
            "entity_id": author_id,
            "min_cluster_size": 2,
            "priority": 6,
        },
    )
    assert rerun_response.status_code == 200, rerun_response.text
    rerun = rerun_response.json()
    assert rerun["signal_count"] == 4
    assert rerun["created_review_tasks"] == 0

    assert len(db_session.scalars(select(AlgorithmicSignal)).all()) == 4
    assert len(db_session.scalars(select(ReviewTask)).all()) == 4


def test_metadata_audit_detects_title_template_cluster(api_client, db_session) -> None:
    author = Author(display_name="Template Author", name_variants=["Template Author"])
    institution = Institution(display_name="Template Institute")
    db_session.add_all([author, institution])
    db_session.flush()
    titles = [
        "Compound A suppresses tumor growth in gastric cancer via kinase pathway",
        "Compound B suppresses tumor growth in gastric cancer via kinase pathway",
        "Compound C suppresses tumor growth in gastric cancer via kinase pathway",
    ]
    for index, title in enumerate(titles, start=1):
        paper = Paper(
            doi=f"10.5555/template.{index}",
            title=title,
            journal_name=f"Template Journal {index}",
            publication_year=2020 + index,
            landing_page_url=f"https://example.org/template/{index}",
        )
        db_session.add(paper)
        db_session.flush()
        db_session.add(
            Authorship(
                paper_id=paper.id,
                author_id=author.id,
                author_name_raw=author.display_name,
                author_position=1,
                author_role="first",
                institution_id=institution.id,
                affiliation_raw=institution.display_name,
            )
        )
    db_session.commit()

    response = api_client.post(
        "/api/audits/metadata",
        json={"entity_type": "author", "entity_id": author.id, "min_cluster_size": 3},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["signal_count"] == 3
    assert result["created_review_tasks"] == 3
    assert {signal["signal_type"] for signal in result["signals"]} == {"metadata_title_template_similarity"}
    assert all(signal["metrics"]["cluster_paper_count"] == 3 for signal in result["signals"])
    assert all("gastric" in signal["metrics"]["shared_title_terms"] for signal in result["signals"])
