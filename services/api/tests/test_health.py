from __future__ import annotations

from gengscope_api.api.routes import health as health_routes


def test_readiness_required_tables_tracks_current_schema() -> None:
    assert {
        "papers",
        "authors",
        "institutions",
        "source_artifacts",
        "algorithmic_signals",
        "review_tasks",
        "audit_logs",
        "report_snapshots",
        "job_runs",
        "job_schedules",
        "entity_groups",
        "entity_group_members",
        "entity_search_cache",
    }.issubset(health_routes.REQUIRED_TABLES)


def test_health_and_readiness(api_client) -> None:
    health_response = api_client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    ready_response = api_client.get("/health/ready")
    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "database": "ok",
        "required_tables": "ok",
        "artifact_storage": "ok",
    }


def test_readiness_reports_missing_required_tables(api_client, monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "_missing_required_tables", lambda db: ["source_artifacts"])

    response = api_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database schema missing tables: source_artifacts"


def test_readiness_reports_unwritable_artifact_storage(api_client, monkeypatch) -> None:
    def fail_storage_check(storage_dir: str) -> None:
        raise PermissionError("read-only storage")

    monkeypatch.setattr(health_routes, "_check_artifact_storage_writable", fail_storage_check)

    response = api_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "artifact storage not writable: read-only storage"
