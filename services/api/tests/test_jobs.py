from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gengscope_api.db.models import JobRun, JobSchedule
from gengscope_api.services import jobs as job_service
from gengscope_api.services.jobs import enqueue_due_scheduled_jobs, requeue_stale_jobs


def test_entity_cycle_job_queue_and_worker_run(api_client) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    enqueue_response = api_client.post(
        "/api/jobs/entity-cycle",
        json={
            "entity_type": "author",
            "entity_id": author_id,
            "min_cluster_size": 2,
            "priority": 6,
        },
        headers={"X-GengScope-Actor": "worker-test"},
    )
    assert enqueue_response.status_code == 200, enqueue_response.text
    job = enqueue_response.json()
    assert job["job_type"] == "entity_audit_cycle"
    assert job["status"] == "queued"
    assert job["actor"] == "worker-test"

    list_response = api_client.get("/api/jobs", params={"status": "queued"})
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 1

    run_response = api_client.post(f"/api/jobs/{job['id']}/run")
    assert run_response.status_code == 200, run_response.text
    finished = run_response.json()
    assert finished["status"] == "succeeded"
    assert finished["attempts"] == 1
    assert finished["result"]["metadata_audit"]["signal_count"] == 4
    assert finished["result"]["profile"]["review_queue_count"] == 5

    get_response = api_client.get(f"/api/jobs/{job['id']}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["status"] == "succeeded"

    logs_response = api_client.get("/api/audit-log", params={"target_type": "job", "target_id": job["id"]})
    assert logs_response.status_code == 200, logs_response.text
    actions = {item["action"] for item in logs_response.json()["items"]}
    assert {"job_enqueued", "job_succeeded"}.issubset(actions)


def test_entity_corpus_job_builds_corpus_in_worker_path(api_client, source_clients, monkeypatch) -> None:
    monkeypatch.setattr(job_service, "default_source_clients", lambda: source_clients)

    enqueue_response = api_client.post(
        "/api/jobs/entity-corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
        headers={"X-GengScope-Actor": "corpus-worker-test"},
    )
    assert enqueue_response.status_code == 200, enqueue_response.text
    job = enqueue_response.json()
    assert job["job_type"] == "entity_corpus_build"
    assert job["status"] == "queued"

    run_response = api_client.post(f"/api/jobs/{job['id']}/run")
    assert run_response.status_code == 200, run_response.text
    finished = run_response.json()
    assert finished["status"] == "succeeded"
    assert finished["result"]["imported_count"] == 2
    assert finished["result"]["entity"]["entity_type"] == "author"
    assert finished["result"]["profile"]["paper_count"] == 2


def test_job_failure_can_be_retried(api_client) -> None:
    enqueue_response = api_client.post(
        "/api/jobs/entity-cycle",
        json={
            "entity_type": "author",
            "entity_id": "missing-entity",
            "min_cluster_size": 2,
        },
    )
    assert enqueue_response.status_code == 200, enqueue_response.text
    job_id = enqueue_response.json()["id"]

    first_run = api_client.post(f"/api/jobs/{job_id}/run")
    assert first_run.status_code == 200, first_run.text
    assert first_run.json()["status"] == "failed"
    assert first_run.json()["error_message"]

    retry_response = api_client.post(f"/api/jobs/{job_id}/retry")
    assert retry_response.status_code == 200, retry_response.text
    retry = retry_response.json()
    assert retry["status"] == "queued"
    assert retry["max_attempts"] == 2
    assert retry["started_at"] is None


def test_batch_entity_cycle_jobs_are_enqueued(api_client) -> None:
    enqueue_response = api_client.post(
        "/api/jobs/entity-cycle/batch",
        json={
            "items": [
                {"entity_type": "author", "entity_id": "author-1", "min_cluster_size": 2},
                {"entity_type": "institution", "entity_id": "institution-1", "min_cluster_size": 2},
            ]
        },
        headers={"X-GengScope-Actor": "batch-worker-test"},
    )
    assert enqueue_response.status_code == 200, enqueue_response.text
    batch = enqueue_response.json()
    assert batch["job_count"] == 2
    assert {item["status"] for item in batch["items"]} == {"queued"}
    assert {item["actor"] for item in batch["items"]} == {"batch-worker-test"}
    assert "任务成功不代表" in batch["conclusion_boundary"]

    list_response = api_client.get("/api/jobs", params={"status": "queued"})
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 2


def test_entity_cycle_schedule_enqueues_due_jobs(api_client, db_session) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    schedule_response = api_client.post(
        "/api/jobs/schedules/entity-cycle",
        json={
            "name": "alice weekly audit",
            "interval_seconds": 3600,
            "run_immediately": False,
            "max_attempts": 2,
            "job": {
                "entity_type": "author",
                "entity_id": author_id,
                "min_cluster_size": 2,
                "priority": 6,
            },
        },
        headers={"X-GengScope-Actor": "scheduler-test"},
    )
    assert schedule_response.status_code == 200, schedule_response.text
    schedule = schedule_response.json()
    assert schedule["status"] == "active"
    assert schedule["job_type"] == "entity_audit_cycle"
    assert schedule["max_attempts"] == 2
    assert schedule["last_job_id"] is None

    db_schedule = db_session.get(JobSchedule, schedule["id"])
    assert db_schedule is not None
    db_schedule.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    due_response = api_client.post("/api/jobs/schedules/run-due")
    assert due_response.status_code == 200, due_response.text
    due = due_response.json()
    assert due["enqueued_count"] == 1
    job = due["items"][0]["job"]
    assert job["status"] == "queued"
    assert job["max_attempts"] == 2
    assert job["payload"]["entity_id"] == author_id

    db_session.refresh(db_schedule)
    assert db_schedule.last_job_id == job["id"]
    assert db_schedule.last_run_at is not None
    assert db_schedule.next_run_at is not None

    second_due = api_client.post("/api/jobs/schedules/run-due")
    assert second_due.status_code == 200, second_due.text
    assert second_due.json()["enqueued_count"] == 0

    list_response = api_client.get("/api/jobs/schedules", params={"status": "active"})
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 1
    assert "不能作为事实结论" in list_response.json()["conclusion_boundary"]

    pause_response = api_client.post(
        f"/api/jobs/schedules/{schedule['id']}/status",
        json={"status": "paused"},
        headers={"X-GengScope-Actor": "scheduler-test"},
    )
    assert pause_response.status_code == 200, pause_response.text
    assert pause_response.json()["status"] == "paused"


def test_run_immediate_schedule_creates_first_job(api_client) -> None:
    schedule_response = api_client.post(
        "/api/jobs/schedules/entity-cycle",
        json={
            "interval_seconds": 3600,
            "run_immediately": True,
            "job": {"entity_type": "author", "entity_id": "author-1", "min_cluster_size": 2},
        },
    )
    assert schedule_response.status_code == 200, schedule_response.text
    schedule = schedule_response.json()
    assert schedule["last_job_id"]

    job_response = api_client.get(f"/api/jobs/{schedule['last_job_id']}")
    assert job_response.status_code == 200, job_response.text
    assert job_response.json()["status"] == "queued"


def test_stale_running_jobs_are_requeued_or_failed(db_session) -> None:
    stale_started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    retryable = JobRun(
        job_type="entity_audit_cycle",
        status="running",
        payload_json={"entity_type": "author", "entity_id": "author-1"},
        attempts=1,
        max_attempts=2,
        started_at=stale_started_at,
    )
    exhausted = JobRun(
        job_type="entity_audit_cycle",
        status="running",
        payload_json={"entity_type": "author", "entity_id": "author-2"},
        attempts=1,
        max_attempts=1,
        started_at=stale_started_at,
    )
    db_session.add_all([retryable, exhausted])
    db_session.commit()

    result = requeue_stale_jobs(db_session, stale_after_seconds=60)

    assert result == {"requeued": 1, "failed": 1}
    db_session.refresh(retryable)
    db_session.refresh(exhausted)
    assert retryable.status == "queued"
    assert retryable.started_at is None
    assert "stale" in retryable.error_message
    assert exhausted.status == "failed"
    assert exhausted.finished_at is not None


def test_due_schedule_helper_works_without_http(db_session) -> None:
    schedule = JobSchedule(
        name="helper schedule",
        job_type="entity_audit_cycle",
        status="active",
        payload_json={"entity_type": "author", "entity_id": "author-1", "min_cluster_size": 2},
        interval_seconds=3600,
        max_attempts=3,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(schedule)
    db_session.commit()

    result = enqueue_due_scheduled_jobs(db_session)

    assert result["enqueued_count"] == 1
    assert result["items"][0]["job"]["max_attempts"] == 3
    db_session.refresh(schedule)
    assert schedule.last_job_id == result["items"][0]["job"]["id"]
