from __future__ import annotations

from sqlalchemy import select

from gengscope_api.db.models import AlgorithmicSignal, Author, Paper, ReviewTask


def test_entity_author_corpus_profile_and_review_queue(api_client, db_session) -> None:
    search_response = api_client.get("/api/entities/search", params={"entity_type": "author", "query": "Alice Zhang"})
    assert search_response.status_code == 200, search_response.text
    candidates = search_response.json()["items"]
    assert any(candidate["display_name"] == "Alice Zhang" for candidate in candidates)

    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    corpus = corpus_response.json()
    author_id = corpus["entity"]["id"]
    assert corpus["imported_count"] == 2
    assert corpus["entity"]["openalex_id"] == "https://openalex.org/A1"
    assert corpus["profile"]["paper_count"] == 2
    assert corpus["profile"]["auditable_paper_count"] == 1
    assert corpus["profile"]["material_status_counts"]["pdf_found"] == 1
    assert corpus["profile"]["material_status_counts"]["landing_page_found"] == 1
    assert corpus["profile"]["priority"] == "medium"

    queue_response = api_client.post(
        "/api/entities/review-queue",
        json={"entity_type": "author", "entity_id": author_id, "priority": 7},
    )
    assert queue_response.status_code == 200, queue_response.text
    queued = queue_response.json()
    assert queued["created_review_tasks"] == 1
    assert queued["profile"]["review_queue_count"] == 1

    tasks = db_session.scalars(select(ReviewTask)).all()
    assert len(tasks) == 1
    assert tasks[0].priority == 7

    profile_response = api_client.get(f"/api/entities/author/{author_id}/profile")
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()
    assert profile["entity"]["display_name"] == "Alice Zhang"
    assert profile["review_queue_count"] == 1
    assert profile["sample_inference"]["audited_sample_size"] == 1
    assert profile["sample_inference"]["reliability"] == "very_low"
    assert "不能外推为全库造假比例" in profile["sample_inference"]["extrapolation_boundary"]
    assert "不能直接认定作者" in profile["conclusion_boundary"]


def test_entity_search_uses_persistent_cache(api_client, source_clients) -> None:
    first_response = api_client.get("/api/entities/search", params={"entity_type": "author", "query": "Alice Zhang", "limit": 10})
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()
    assert first["source"] == "openalex"
    assert first["cached"] is False
    assert first["cache_status"] == "refreshed"
    assert source_clients.openalex.author_search_calls == 1

    second_response = api_client.get("/api/entities/search", params={"entity_type": "author", "query": " alice   zhang ", "limit": 10})
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    assert second["source"] == "cache"
    assert second["cached"] is True
    assert second["cache_status"] == "fresh"
    assert second["items"] == first["items"]
    assert source_clients.openalex.author_search_calls == 1

    refresh_response = api_client.get("/api/entities/search", params={"entity_type": "author", "query": "Alice Zhang", "limit": 10, "refresh": "true"})
    assert refresh_response.status_code == 200, refresh_response.text
    assert refresh_response.json()["source"] == "openalex"
    assert source_clients.openalex.author_search_calls == 2


def test_entity_profile_counts_algorithmic_signals(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]
    paper = db_session.scalars(select(Paper).where(Paper.doi == "10.1234/example.paper")).first()
    assert paper is not None
    db_session.add(
        AlgorithmicSignal(
            paper_id=paper.id,
            signal_type="numeric_sequence_similarity",
            severity="high",
            confidence=0.91,
            analyzer_name="gengscope.numeric",
            analyzer_version="0.1.0",
            summary="Source data 中存在重复序列，需要人工复核。",
            status="confirmed_signal",
        )
    )
    paper.audit_status = "metadata_screened"
    db_session.commit()

    profile_response = api_client.get(f"/api/entities/author/{author_id}/profile")
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()
    assert profile["algorithmic_signal_count"] == 1
    assert profile["signal_paper_count"] == 1
    assert profile["audited_paper_count"] == 1
    assert profile["signal_rate_among_audited"] == 1.0
    assert profile["sample_inference"]["observed_signal_rate"] == 1.0
    assert profile["sample_inference"]["wilson_signal_rate_interval_95"]["upper"] == 1.0


def test_entity_institution_corpus_profile(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "institution", "query": "Example University", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    corpus = corpus_response.json()
    assert corpus["entity"]["display_name"] == "Example University"
    assert corpus["profile"]["paper_count"] == 2
    assert corpus["profile"]["auditable_coverage"] == 0.5

    author = db_session.scalars(select(Author).where(Author.display_name == "Alice Zhang")).first()
    assert author is not None

    breakdown_response = api_client.get(f"/api/entities/institution/{corpus['entity']['id']}/breakdown")
    assert breakdown_response.status_code == 200, breakdown_response.text
    breakdown = breakdown_response.json()
    assert breakdown["entity"]["display_name"] == "Example University"
    assert breakdown["affiliation_unit_count"] >= 1
    assert any(unit["unit_name"] == "School of Life Sciences" for unit in breakdown["affiliation_units"])
    assert breakdown["top_authors"][0]["display_name"] == "Alice Zhang"
    assert "不能作为院系归属" in breakdown["conclusion_boundary"]


def test_batch_entity_corpus_builds_multiple_entities(api_client) -> None:
    response = api_client.post(
        "/api/entities/corpus/batch",
        json={
            "items": [
                {"entity_type": "author", "query": "Alice Zhang", "limit": 10},
                {"entity_type": "institution", "query": "Example University", "limit": 10},
            ],
            "continue_on_error": True,
        },
        headers={"X-GengScope-Actor": "batch-test"},
    )

    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["item_count"] == 2
    assert batch["succeeded_count"] == 2
    assert batch["failed_count"] == 0
    assert batch["total_imported_count"] == 4
    assert [item["entity"]["entity_type"] for item in batch["items"]] == ["author", "institution"]
    assert all(item["profile"]["paper_count"] == 2 for item in batch["items"])
    assert "不能直接认定" in batch["conclusion_boundary"]


def test_group_corpus_aggregates_members_for_lab_level_workflows(api_client) -> None:
    response = api_client.post(
        "/api/entities/groups/corpus",
        json={
            "display_name": "Alice Zhang Lab",
            "description": "Local lab-level corpus made from PI and institution members.",
            "members": [
                {"entity_type": "author", "query": "Alice Zhang", "limit": 10},
                {"entity_type": "institution", "query": "Example University", "limit": 10},
            ],
        },
        headers={"X-GengScope-Actor": "group-test"},
    )

    assert response.status_code == 200, response.text
    group = response.json()
    group_id = group["entity"]["id"]
    assert group["entity"]["entity_type"] == "group"
    assert len(group["entity"]["members"]) == 2
    assert group["member_count"] == 2
    assert group["succeeded_count"] == 2
    assert group["failed_count"] == 0
    assert group["total_imported_count"] == 4
    assert group["profile"]["paper_count"] == 2
    assert "group/lab" in group["conclusion_boundary"]

    profile_response = api_client.get(f"/api/entities/group/{group_id}/profile")
    assert profile_response.status_code == 200, profile_response.text
    assert profile_response.json()["entity"]["display_name"] == "Alice Zhang Lab"
    assert profile_response.json()["paper_count"] == 2

    queue_response = api_client.post(
        "/api/entities/review-queue",
        json={"entity_type": "group", "entity_id": group_id, "priority": 8},
    )
    assert queue_response.status_code == 200, queue_response.text
    assert queue_response.json()["created_review_tasks"] == 1

    audit_response = api_client.post(
        "/api/audits/metadata",
        json={"entity_type": "group", "entity_id": group_id, "min_cluster_size": 2},
    )
    assert audit_response.status_code == 200, audit_response.text
    assert audit_response.json()["entity_type"] == "group"
    assert audit_response.json()["paper_count"] == 2
    assert audit_response.json()["signal_count"] >= 1

    signals_response = api_client.get(f"/api/entities/group/{group_id}/signals")
    assert signals_response.status_code == 200, signals_response.text
    assert signals_response.json()["total"] >= 1

    report_response = api_client.get("/api/reports/entity", params={"entity_type": "group", "entity_id": group_id})
    assert report_response.status_code == 200, report_response.text
    assert report_response.json()["entity"]["entity_type"] == "group"


def test_import_entity_manifest_csv_builds_batch_corpus(api_client) -> None:
    csv_content = "\n".join(
        [
            "entity_type,query,limit,year_from,year_to",
            "author,Alice Zhang,10,2020,2026",
            "institution,Example University,10,2020,2026",
        ]
    )

    response = api_client.post(
        "/api/entities/corpus/import",
        data={"continue_on_error": "true", "default_limit": "25"},
        files={"file": ("entities.csv", csv_content.encode("utf-8"), "text/csv")},
        headers={"X-GengScope-Actor": "manifest-test"},
    )

    assert response.status_code == 200, response.text
    imported = response.json()
    assert imported["source_filename"] == "entities.csv"
    assert imported["item_count"] == 2
    assert imported["succeeded_count"] == 2
    assert imported["failed_count"] == 0
    assert [item["entity"]["entity_type"] for item in imported["items"]] == ["author", "institution"]
    assert imported["total_imported_count"] == 4


def test_import_entity_manifest_json_uses_defaults(api_client) -> None:
    response = api_client.post(
        "/api/entities/corpus/import",
        data={"default_limit": "10", "default_year_from": "2020", "default_year_to": "2026"},
        files={
            "file": (
                "entities.json",
                b'{"items":[{"entity_type":"author","query":"Alice Zhang"}]}',
                "application/json",
            )
        },
    )

    assert response.status_code == 200, response.text
    imported = response.json()
    assert imported["item_count"] == 1
    assert imported["succeeded_count"] == 1
    assert imported["items"][0]["entity"]["display_name"] == "Alice Zhang"


def test_import_entity_manifest_rejects_missing_entity_type(api_client) -> None:
    response = api_client.post(
        "/api/entities/corpus/import",
        files={"file": ("bad.csv", b"query\nAlice Zhang\n", "text/csv")},
    )

    assert response.status_code == 422
    assert "entity_type" in response.text
