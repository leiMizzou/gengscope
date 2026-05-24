from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from gengscope_api.api.deps import get_source_clients
from gengscope_api.config import get_settings
from gengscope_api.db.models import AuditLog
from gengscope_api.db.session import get_db
from gengscope_api.main import create_app


def test_audit_log_records_entity_audit_and_report_actions(api_client, db_session) -> None:
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

    report_response = api_client.get(
        "/api/reports/entity",
        params={"entity_type": "author", "entity_id": author_id},
        headers=headers,
    )
    assert report_response.status_code == 200, report_response.text

    list_response = api_client.get(
        "/api/audit-log",
        params={"entity_type": "author", "entity_id": author_id, "limit": 10},
    )
    assert list_response.status_code == 200, list_response.text
    logs = list_response.json()
    assert logs["total"] == 3
    assert {item["action"] for item in logs["items"]} == {
        "entity_corpus_built",
        "metadata_audit_run",
        "entity_report_exported",
    }
    assert all(item["actor"] == "reviewer@example.org" for item in logs["items"])
    assert "不能" in logs["conclusion_boundary"]

    metadata_log = db_session.scalar(select(AuditLog).where(AuditLog.action == "metadata_audit_run"))
    assert metadata_log is not None
    assert metadata_log.metadata_json["signal_count"] == audit_response.json()["signal_count"]


def test_api_key_auth_is_optional_and_enforced_when_configured(db_session, source_clients, monkeypatch) -> None:
    monkeypatch.setenv("GENGSCOPE_API_KEY", "local-secret")
    get_settings.cache_clear()
    app = create_app(init_tables=False)

    def override_db():
        yield db_session

    def override_clients():
        return source_clients

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_source_clients] = override_clients
    try:
        client = TestClient(app)
        assert client.get("/health").status_code == 200
        assert client.get("/api/papers").status_code == 401
        assert client.get("/api/papers", headers={"X-API-Key": "local-secret"}).status_code == 200
    finally:
        get_settings.cache_clear()


def test_api_key_roles_gate_write_and_admin_access(db_session, source_clients, monkeypatch) -> None:
    monkeypatch.setenv("GENGSCOPE_API_KEYS", "reader-key,reviewer-key,admin-key")
    monkeypatch.setenv("GENGSCOPE_API_KEY_ROLES", "reader-key:read,reviewer-key:reviewer,admin-key:admin")
    get_settings.cache_clear()
    app = create_app(init_tables=False)

    def override_db():
        yield db_session

    def override_clients():
        return source_clients

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_source_clients] = override_clients
    try:
        client = TestClient(app)
        assert client.get("/api/papers", headers={"X-API-Key": "reader-key"}).status_code == 200

        read_write_response = client.post(
            "/api/entities/corpus",
            json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
            headers={"X-API-Key": "reader-key"},
        )
        assert read_write_response.status_code == 403

        reviewer_write_response = client.post(
            "/api/entities/corpus",
            json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
            headers={"X-API-Key": "reviewer-key"},
        )
        assert reviewer_write_response.status_code == 200, reviewer_write_response.text

        reviewer_admin_response = client.post(
            "/api/admin/import/doi",
            json={"doi": "10.1234/example.paper", "sources": ["openalex"]},
            headers={"X-API-Key": "reviewer-key"},
        )
        assert reviewer_admin_response.status_code == 403

        admin_response = client.post(
            "/api/admin/import/doi",
            json={"doi": "10.1234/example.paper", "sources": ["openalex"]},
            headers={"X-API-Key": "admin-key"},
        )
        assert admin_response.status_code == 200, admin_response.text

        prune_response = client.post(
            "/api/reports/archive/prune",
            json={"keep_latest": 20, "older_than_days": 180, "dry_run": True},
            headers={"X-API-Key": "reviewer-key"},
        )
        assert prune_response.status_code == 403
    finally:
        get_settings.cache_clear()
