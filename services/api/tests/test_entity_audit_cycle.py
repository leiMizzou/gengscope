from __future__ import annotations


def test_entity_audit_cycle_runs_discovery_queue_and_metadata_audit(api_client) -> None:
    corpus_response = api_client.post(
        "/api/entities/corpus",
        json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
    )
    assert corpus_response.status_code == 200, corpus_response.text
    author_id = corpus_response.json()["entity"]["id"]

    cycle_response = api_client.post(
        "/api/audits/entity-cycle",
        json={
            "entity_type": "author",
            "entity_id": author_id,
            "min_cluster_size": 2,
            "priority": 6,
        },
        headers={"X-GengScope-Actor": "cycle-runner"},
    )
    assert cycle_response.status_code == 200, cycle_response.text
    cycle = cycle_response.json()
    assert cycle["paper_count"] == 2
    assert cycle["discovered_artifact_papers"] == 2
    assert cycle["discovered_artifact_count"] == 3
    assert cycle["queued_review_tasks"] == 1
    assert cycle["metadata_audit"]["signal_count"] == 4
    assert cycle["metadata_audit"]["created_review_tasks"] == 4
    assert cycle["profile"]["review_queue_count"] == 5
    assert "不能直接认定" in cycle["conclusion_boundary"]

    log_response = api_client.get(
        "/api/audit-log",
        params={"action": "entity_audit_cycle_run", "entity_type": "author", "entity_id": author_id},
    )
    assert log_response.status_code == 200, log_response.text
    logs = log_response.json()
    assert logs["total"] == 1
    assert logs["items"][0]["actor"] == "cycle-runner"
    assert logs["items"][0]["metadata"]["metadata_signal_count"] == 4
