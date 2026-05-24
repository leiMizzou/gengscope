from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from sqlalchemy import select

from gengscope_api.db.models import AuditLog, ReportSnapshot, utcnow


def test_entity_report_archive_round_trip(api_client, db_session) -> None:
    headers = {"X-GengScope-Actor": "reviewer@example.org"}
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
        headers=headers,
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    audit_response = api_client.post(
        "/api/audits/metadata",
        json={"entity_type": "author", "entity_id": author_id, "min_cluster_size": 2},
        headers=headers,
    )
    assert audit_response.status_code == 200, audit_response.text

    archive_response = api_client.post(
        "/api/reports/entity/archive",
        json={"entity_type": "author", "entity_id": author_id, "formats": ["json", "markdown"]},
        headers=headers,
    )
    assert archive_response.status_code == 200, archive_response.text
    archive = archive_response.json()
    assert archive["total"] == 2
    assert archive["entity"]["display_name"] == "Alice Zhang"
    assert "可复核快照" in archive["conclusion_boundary"]

    json_snapshot = next(item for item in archive["items"] if item["report_format"] == "json")
    markdown_snapshot = next(item for item in archive["items"] if item["report_format"] == "markdown")
    assert json_snapshot["actor"] == "reviewer@example.org"
    assert markdown_snapshot["entity_id"] == author_id

    list_response = api_client.get(
        "/api/reports/archive",
        params={"entity_type": "author", "entity_id": author_id, "format": "all"},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed["total"] == 2
    assert {item["id"] for item in listed["items"]} == {json_snapshot["id"], markdown_snapshot["id"]}

    snapshot_response = api_client.get(
        f"/api/reports/archive/{json_snapshot['id']}",
        headers=headers,
    )
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot = snapshot_response.json()
    assert snapshot["content_json"]["entity"]["display_name"] == "Alice Zhang"
    assert snapshot["content_json"]["signals"]["total"] == 4
    assert "不能据此直接认定" in snapshot["content_json"]["conclusion_boundary"]
    expected_json_hash = hashlib.sha256(
        json.dumps(snapshot["content_json"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert snapshot["content_sha256"] == expected_json_hash

    markdown_response = api_client.get(
        f"/api/reports/archive/{markdown_snapshot['id']}",
        params={"format": "markdown"},
        headers=headers,
    )
    assert markdown_response.status_code == 200, markdown_response.text
    assert "# GengScope Entity Report: Alice Zhang" in markdown_response.text
    assert "## Conclusion Boundary" in markdown_response.text
    assert hashlib.sha256(markdown_response.text.encode("utf-8")).hexdigest() == markdown_snapshot["content_sha256"]

    archived_log = db_session.scalar(select(AuditLog).where(AuditLog.action == "entity_report_archived"))
    assert archived_log is not None
    assert archived_log.actor == "reviewer@example.org"
    assert set(archived_log.metadata_json["snapshot_ids"]) == {json_snapshot["id"], markdown_snapshot["id"]}

    read_logs = db_session.scalars(select(AuditLog).where(AuditLog.action == "entity_report_archive_read")).all()
    assert len(read_logs) == 2
    assert {log.metadata_json["format"] for log in read_logs} == {"json", "markdown"}


def test_entity_report_archive_prune_keeps_latest_per_format(api_client, db_session) -> None:
    headers = {"X-GengScope-Actor": "retention@example.org"}
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
        headers=headers,
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    first_archive_response = api_client.post(
        "/api/reports/entity/archive",
        json={"entity_type": "author", "entity_id": author_id, "formats": ["json", "markdown"]},
        headers=headers,
    )
    assert first_archive_response.status_code == 200, first_archive_response.text
    old_snapshots = db_session.scalars(select(ReportSnapshot).where(ReportSnapshot.entity_id == author_id)).all()
    old_snapshot_ids = {snapshot.id for snapshot in old_snapshots}
    for snapshot in old_snapshots:
        snapshot.created_at = utcnow() - timedelta(days=200)
    db_session.commit()

    second_archive_response = api_client.post(
        "/api/reports/entity/archive",
        json={"entity_type": "author", "entity_id": author_id, "formats": ["json", "markdown"]},
        headers=headers,
    )
    assert second_archive_response.status_code == 200, second_archive_response.text

    dry_run_response = api_client.post(
        "/api/reports/archive/prune",
        json={"entity_type": "author", "entity_id": author_id, "keep_latest": 1, "older_than_days": 30, "dry_run": True},
        headers=headers,
    )
    assert dry_run_response.status_code == 200, dry_run_response.text
    dry_run = dry_run_response.json()
    assert dry_run["dry_run"] is True
    assert dry_run["matched_count"] == 4
    assert dry_run["pruned_count"] == 2
    assert len(db_session.scalars(select(ReportSnapshot).where(ReportSnapshot.entity_id == author_id)).all()) == 4

    prune_response = api_client.post(
        "/api/reports/archive/prune",
        json={"entity_type": "author", "entity_id": author_id, "keep_latest": 1, "older_than_days": 30, "dry_run": False},
        headers=headers,
    )
    assert prune_response.status_code == 200, prune_response.text
    pruned = prune_response.json()
    assert pruned["dry_run"] is False
    assert pruned["pruned_count"] == 2

    remaining = db_session.scalars(select(ReportSnapshot).where(ReportSnapshot.entity_id == author_id)).all()
    assert len(remaining) == 2
    assert {snapshot.report_format for snapshot in remaining} == {"json", "markdown"}
    assert not ({snapshot.id for snapshot in remaining} & old_snapshot_ids)

    prune_log = db_session.scalar(select(AuditLog).where(AuditLog.action == "entity_report_archive_pruned"))
    assert prune_log is not None
    assert prune_log.actor == "retention@example.org"
    assert prune_log.metadata_json["pruned_count"] == 2
