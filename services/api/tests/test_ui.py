from __future__ import annotations


def test_workbench_page_serves_entity_ui(api_client) -> None:
    response = api_client.get("/")

    assert response.status_code == 200
    assert "GengScope" in response.text
    assert "/api/entities/corpus" in response.text
    assert "/api/audits/numeric" in response.text
    assert "/api/audits/image" in response.text
    assert "/api/audits/metadata" in response.text
    assert "/api/artifacts/discover" in response.text
    assert "/api/artifacts/fetch" in response.text
    assert "/api/admin/import/doi" in response.text
    assert "/api/artifacts/papers/" in response.text
    assert "paperDoi" in response.text
    assert "材料列表" in response.text
    assert "compareArtifactIds" in response.text
    assert "Image Panel" in response.text
    assert "inspect_landing_pages" in response.text
    assert "/signals?status=all" in response.text
    assert "/api/reports/entity" in response.text
    assert "/api/reports/entity/archive" in response.text
    assert "/api/reports/archive" in response.text
    assert "renderReport(data)" in response.text
    assert "renderArchives(data)" in response.text
    assert "归档报告" in response.text
    assert "/api/entities/corpus/import" in response.text
    assert "/api/entities/groups" in response.text
    assert "/api/entities/groups/corpus" in response.text
    assert "entityManifestFile" in response.text
    assert "导入名单" in response.text
    assert "groupMembers" in response.text
    assert "创建课题组" in response.text
    assert "课题组建库" in response.text
    assert "split(/\\n+/)" in response.text
    assert "buildCandidate" in response.text
    assert "立即建库" in response.text
    assert "/api/papers?" in response.text
    assert "/api/agent/doi/" in response.text
    assert "/api/admin/events" in response.text
    assert "/api/reports/archive/prune" in response.text
    assert "renderRiskCard(data)" in response.text
    assert "renderPaperDetail(data)" in response.text
    assert "Paper Risk" in response.text
    assert "登记事件" in response.text
    assert "清理归档" in response.text
    assert "/api/jobs/entity-cycle" in response.text
    assert "/api/jobs?limit=20" in response.text
    assert "/api/jobs/${jobId}/run" in response.text
    assert "/api/jobs/${jobId}/retry" in response.text
    assert "/api/jobs/schedules/entity-cycle" in response.text
    assert "/api/jobs/schedules?limit=20" in response.text
    assert "/api/jobs/schedules/run-due" in response.text
    assert "/api/jobs/schedules/${scheduleId}/status" in response.text
    assert "scheduleInterval" in response.text
    assert "周期审计" in response.text
    assert "调度列表" in response.text
    assert "后台建库" in response.text
    assert "/api/jobs/entity-corpus" in response.text
    assert "Entity Corpus Workbench" in response.text
    assert "Search Results" in response.text
    assert "candidates" in response.text
    assert "candidate-card" in response.text
    assert "openalexId" in response.text
    assert "renderCandidates(data)" in response.text
    assert "enqueueCandidate" in response.text
    assert "结构拆分" in response.text
    assert "/breakdown?limit=24" in response.text
    assert "renderBreakdown(data)" in response.text
    assert "renderArtifacts(data)" in response.text
    assert "renderJobs(data)" in response.text
    assert "renderSchedules(data)" in response.text
    assert "renderAuditLogs(data)" in response.text


def test_favicon_does_not_log_browser_404(api_client) -> None:
    response = api_client.get("/favicon.ico")

    assert response.status_code == 204
