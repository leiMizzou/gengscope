from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["ui"])


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
def workbench() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GengScope Workbench</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #17202a;
      --muted: #667085;
      --accent: #0f766e;
      --warn: #a16207;
      --risk: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    header h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: calc(100vh - 56px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 20px;
    }
    section {
      padding: 20px 24px;
    }
    label {
      display: block;
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    input, select, textarea, button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
    }
    input, select, button {
      height: 36px;
      padding: 0 10px;
    }
    textarea {
      min-height: 88px;
      padding: 8px 10px;
      resize: vertical;
    }
    input[type="file"] {
      height: auto;
      padding: 7px 10px;
    }
    button {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 600;
    }
    button:disabled {
      cursor: wait;
      opacity: 0.65;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
    }
    button.small {
      width: auto;
      height: 30px;
      padding: 0 8px;
      font-size: 12px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .field { margin-bottom: 14px; }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 8px;
    }
    .section-title {
      margin: 20px 0 10px;
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
    }
    .task-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .inline-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .inline-actions button {
      width: auto;
    }
    .link-list {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .link-list a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .candidate-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .candidate-card {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px;
      min-height: 148px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 12px;
    }
    .candidate-card h3 {
      margin: 0 0 4px;
      font-size: 15px;
      line-height: 1.25;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .metric {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px;
      min-height: 74px;
    }
    .metric b {
      display: block;
      font-size: 22px;
      line-height: 1.1;
      margin-top: 6px;
    }
    .muted { color: var(--muted); }
    .status {
      display: inline-flex;
      align-items: center;
      height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: #e6f4f1;
      color: var(--accent);
      font-weight: 650;
      text-transform: uppercase;
      font-size: 11px;
    }
    .status.high { background: #fee4e2; color: var(--risk); }
    .status.medium { background: #fef3c7; color: var(--warn); }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      background: #fbfcfe;
      font-size: 12px;
    }
    tr:last-child td { border-bottom: 0; }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #101828;
      color: #e5e7eb;
      border-radius: 8px;
      padding: 12px;
      min-height: 96px;
      max-height: 320px;
      overflow: auto;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .summary { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>GengScope</h1>
    <span class="muted">Entity Corpus Workbench</span>
  </header>
  <main>
    <aside>
      <div class="field">
        <label for="entityType">实体类型</label>
        <select id="entityType">
          <option value="author">作者</option>
          <option value="institution">机构</option>
          <option value="group">课题组</option>
        </select>
      </div>
      <div class="field">
        <label for="query">名称</label>
        <input id="query" value="Alice Zhang" />
      </div>
      <div class="field">
        <label for="openalexId">OpenAlex ID</label>
        <input id="openalexId" placeholder="搜索候选后自动填入，可手动清空" />
      </div>
      <div class="row">
        <div class="field">
          <label for="yearFrom">开始年份</label>
          <input id="yearFrom" value="2020" inputmode="numeric" />
        </div>
        <div class="field">
          <label for="yearTo">结束年份</label>
          <input id="yearTo" value="2026" inputmode="numeric" />
        </div>
      </div>
      <div class="field">
        <label for="limit">论文上限</label>
        <input id="limit" value="25" inputmode="numeric" />
      </div>
      <div class="field">
        <label for="apiKey">API Key</label>
        <input id="apiKey" type="password" autocomplete="off" />
      </div>
      <div class="actions">
        <button id="searchBtn" class="secondary">搜索</button>
        <button id="buildBtn">建库</button>
        <button id="corpusJobBtn" class="secondary">后台建库</button>
      </div>
      <div class="field" style="margin-top:14px">
        <label for="entityManifestFile">实体名单文件</label>
        <input id="entityManifestFile" type="file" accept=".csv,.tsv,.json,.txt" />
      </div>
      <div class="actions">
        <button id="importCorpusBtn" class="secondary">导入名单</button>
      </div>
      <div class="field" style="margin-top:14px">
        <label for="groupMembers">组成员</label>
        <textarea id="groupMembers" rows="4" placeholder="author:本地作者ID&#10;institution:本地机构ID&#10;author:姓名|OpenAlexID"></textarea>
      </div>
      <div class="actions">
        <button id="createGroupBtn" class="secondary">创建课题组</button>
        <button id="buildGroupCorpusBtn">课题组建库</button>
      </div>
      <div class="field" style="margin-top:14px">
        <label for="entityId">本地实体 ID</label>
        <input id="entityId" />
      </div>
      <div class="field">
        <label for="scheduleInterval">调度间隔秒</label>
        <input id="scheduleInterval" value="604800" inputmode="numeric" />
      </div>
      <div class="actions">
        <button id="profileBtn" class="secondary">画像</button>
        <button id="breakdownBtn" class="secondary">结构拆分</button>
        <button id="queueBtn">复核队列</button>
        <button id="metadataAuditBtn">元数据审计</button>
        <button id="signalsBtn" class="secondary">实体信号</button>
        <button id="reportBtn" class="secondary">实体报告</button>
        <button id="archiveReportBtn" class="secondary">归档报告</button>
        <button id="archiveListBtn" class="secondary">报告归档</button>
        <button id="jobBtn">后台审计</button>
        <button id="scheduleBtn">周期审计</button>
        <button id="jobsBtn" class="secondary">任务列表</button>
        <button id="schedulesBtn" class="secondary">调度列表</button>
      </div>
      <div class="row" style="margin-top:14px">
        <div class="field">
          <label for="archiveKeepLatest">保留归档数</label>
          <input id="archiveKeepLatest" value="20" inputmode="numeric" />
        </div>
        <div class="field">
          <label for="archiveOlderDays">归档天数</label>
          <input id="archiveOlderDays" value="180" inputmode="numeric" />
        </div>
      </div>
      <div class="field">
        <label for="archiveDryRun">
          <input id="archiveDryRun" type="checkbox" checked style="width:auto;height:auto;margin-right:6px" />
          仅预览清理
        </label>
      </div>
      <div class="actions">
        <button id="pruneArchiveBtn" class="secondary">清理归档</button>
      </div>
      <div class="section-title">材料审计</div>
      <div class="field">
        <label for="paperDoi">DOI</label>
        <input id="paperDoi" placeholder="10.xxxx/..." />
      </div>
      <div class="actions">
        <button id="importDoiBtn" class="secondary">导入 DOI</button>
        <button id="paperSearchBtn" class="secondary">搜索论文</button>
        <button id="paperDetailBtn" class="secondary">论文详情</button>
        <button id="agentSummaryBtn" class="secondary">Agent 摘要</button>
        <button id="paperArtifactsBtn" class="secondary">材料列表</button>
        <button id="riskCardBtn" class="secondary">风险卡</button>
      </div>
      <div class="field">
        <label for="paperId">论文 ID</label>
        <input id="paperId" />
      </div>
      <div class="field">
        <label for="artifactType">材料类型</label>
        <select id="artifactType">
          <option value="source_data">Source Data</option>
          <option value="figure_image">Figure Image</option>
          <option value="image_panel">Image Panel</option>
          <option value="supplementary_image">Supplementary Image</option>
          <option value="supplementary_table">Supplementary Table</option>
          <option value="paper_pdf">Paper PDF</option>
        </select>
      </div>
      <div class="field">
        <label for="sourceUrl">材料 URL</label>
        <input id="sourceUrl" placeholder="https://..." />
      </div>
      <div class="field">
        <label for="inspectLanding">
          <input id="inspectLanding" type="checkbox" style="width:auto;height:auto;margin-right:6px" />
          解析页面链接
        </label>
      </div>
      <div class="field">
        <label for="artifactFile">文件</label>
        <input id="artifactFile" type="file" accept=".csv,.tsv,.xlsx,.xlsm,.png,.jpg,.jpeg,.webp,.tif,.tiff" />
      </div>
      <div class="actions">
        <button id="uploadBtn" class="secondary">上传</button>
        <button id="discoverBtn" class="secondary">发现材料</button>
        <button id="fetchBtn" class="secondary">拉取URL</button>
        <button id="auditBtn">数值审计</button>
        <button id="imageAuditBtn">图像审计</button>
      </div>
      <div class="field" style="margin-top:14px">
        <label for="artifactId">材料 ID</label>
        <input id="artifactId" />
      </div>
      <div class="field">
        <label for="compareArtifactIds">图像对比材料 ID</label>
        <textarea id="compareArtifactIds" rows="3" placeholder="一行一个或逗号分隔。材料列表中点“加入对比”会自动填入。"></textarea>
      </div>
      <div class="actions">
        <button id="tasksBtn" class="secondary">查看复核任务</button>
        <button id="auditLogBtn" class="secondary">操作日志</button>
      </div>
      <div class="section-title">公开事件</div>
      <div class="row">
        <div class="field">
          <label for="eventType">事件类型</label>
          <select id="eventType">
            <option value="public_discussion">公开讨论</option>
            <option value="media_report">媒体报道</option>
            <option value="institution_notice">机构调查</option>
            <option value="correction">官方更正</option>
            <option value="retraction">官方撤稿</option>
          </select>
        </div>
        <div class="field">
          <label for="eventStatusLevel">状态级别</label>
          <select id="eventStatusLevel">
            <option value="public_discussion">公开讨论</option>
            <option value="media_report">媒体报道</option>
            <option value="institution_investigation">机构调查</option>
            <option value="official_correction">官方更正</option>
            <option value="official_retraction">官方撤稿</option>
          </select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="eventSourceType">来源类型</label>
          <select id="eventSourceType">
            <option value="pubpeer">PubPeer</option>
            <option value="media">媒体</option>
            <option value="institution">机构</option>
            <option value="publisher">出版方</option>
            <option value="official">官方</option>
          </select>
        </div>
        <div class="field">
          <label for="eventVerification">核验状态</label>
          <select id="eventVerification">
            <option value="unverified">未核验</option>
            <option value="source_verified">来源已核验</option>
            <option value="official_confirmed">官方确认</option>
            <option value="disputed">存在争议</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label for="eventSourceUrl">事件 URL</label>
        <input id="eventSourceUrl" placeholder="https://..." />
      </div>
      <div class="field">
        <label for="eventSummary">事件摘要</label>
        <textarea id="eventSummary" rows="3"></textarea>
      </div>
      <div class="actions">
        <button id="eventBtn" class="secondary">登记事件</button>
      </div>
      <pre id="log"></pre>
    </aside>
    <section>
      <div class="section-title">Search Results</div>
      <div id="candidateStatus" class="muted"></div>
      <div id="candidates" class="candidate-grid"></div>
      <div id="profile"></div>
      <div class="section-title">Breakdown</div>
      <div id="breakdownStatus" class="muted"></div>
      <div id="breakdown" class="candidate-grid"></div>
      <div class="section-title">Paper Risk</div>
      <div id="paperRisk"></div>
      <div class="section-title">Artifacts</div>
      <div id="artifactStatus" class="muted"></div>
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>文件/来源</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="artifacts"></tbody>
      </table>
      <table>
        <thead>
          <tr>
            <th>年份</th>
            <th>论文</th>
            <th>材料</th>
            <th>审计</th>
            <th>信号</th>
          </tr>
        </thead>
        <tbody id="papers"></tbody>
      </table>
      <div class="section-title">Signals</div>
      <table>
        <thead>
          <tr>
            <th>级别</th>
            <th>类型</th>
            <th>论文</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody id="signals"></tbody>
      </table>
      <div class="section-title">Review Tasks</div>
      <table>
        <thead>
          <tr>
            <th>优先级</th>
            <th>论文</th>
            <th>信号</th>
            <th>状态</th>
            <th>处理</th>
          </tr>
        </thead>
        <tbody id="tasks"></tbody>
      </table>
      <div class="section-title">Jobs</div>
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>状态</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="jobs"></tbody>
      </table>
      <div class="section-title">Schedules</div>
      <div class="inline-actions" style="margin-bottom:8px">
        <button id="runDueBtn" class="small secondary">运行到期调度</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>下次运行</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="schedules"></tbody>
      </table>
      <div class="section-title">Reports</div>
      <div id="report"></div>
      <table>
        <thead>
          <tr>
            <th>实体</th>
            <th>格式</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="archives"></tbody>
      </table>
      <div class="section-title">Audit Log</div>
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>动作</th>
            <th>对象</th>
            <th>摘要</th>
          </tr>
        </thead>
        <tbody id="auditLogs"></tbody>
      </table>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const log = (data) => { $("log").textContent = JSON.stringify(data, null, 2); };
    const value = (id) => $(id).value.trim();
    const html = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char]));
    const shortId = (id) => id ? `${id.slice(0, 8)}…` : "";
    const sourceLink = (url) => {
      if (!url) return "";
      if (!/^https?:\\/\\//i.test(url)) return html(url);
      return `<a href="${html(url)}" target="_blank" rel="noopener noreferrer">打开来源</a>`;
    };
    $("apiKey").value = localStorage.getItem("gengscope_api_key") || "";
    $("apiKey").onchange = () => localStorage.setItem("gengscope_api_key", value("apiKey"));
    $("query").oninput = () => { $("openalexId").value = ""; };
    $("entityType").onchange = () => { $("openalexId").value = ""; $("candidates").innerHTML = ""; syncEntityControls(); };
    const intValue = (id) => {
      const raw = value(id);
      return raw ? Number(raw) : null;
    };

    async function withBusy(buttonId, label, action) {
      const button = $(buttonId);
      const original = button.textContent;
      button.disabled = true;
      button.textContent = label;
      try {
        return await action();
      } finally {
        button.textContent = original;
        button.disabled = false;
      }
    }

    async function request(path, options = {}) {
      const headers = { "content-type": "application/json", ...(options.headers || {}) };
      if (value("apiKey")) headers["x-api-key"] = value("apiKey");
      const response = await fetch(path, {
        ...options,
        headers
      });
      const data = await response.json();
      if (!response.ok) throw data;
      return data;
    }

    function syncEntityControls() {
      const isGroup = value("entityType") === "group";
      $("searchBtn").disabled = isGroup;
      $("corpusJobBtn").disabled = isGroup;
      $("openalexId").disabled = isGroup;
    }

    function renderProfile(profile) {
      if (!profile || !profile.entity) return;
      $("entityId").value = profile.entity.id;
      if ((profile.top_papers || []).length && !$("paperId").value) {
        $("paperId").value = profile.top_papers[0].id;
      }
      const priority = profile.priority || "unknown";
      $("profile").innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:12px">
          <div>
            <h2 style="margin:0 0 4px;font-size:20px">${profile.entity.display_name}</h2>
            <div class="muted">${profile.entity.entity_type} · ${profile.entity.openalex_id || ""}</div>
          </div>
          <span class="status ${priority}">${priority}</span>
        </div>
        <div class="summary">
          <div class="metric"><span class="muted">论文</span><b>${profile.paper_count}</b></div>
          <div class="metric"><span class="muted">可审计</span><b>${profile.auditable_paper_count}</b></div>
          <div class="metric"><span class="muted">已审计/排队</span><b>${profile.audited_paper_count + profile.review_queue_count}</b></div>
          <div class="metric"><span class="muted">信号论文</span><b>${profile.signal_paper_count}</b></div>
        </div>
        <p>${profile.summary}</p>
        <p class="muted">${profile.conclusion_boundary}</p>
      `;
      $("papers").innerHTML = (profile.top_papers || []).map((paper) => `
        <tr>
          <td>${paper.publication_year || ""}</td>
          <td><b>${paper.title}</b><div class="muted">${paper.doi || paper.id}</div><button class="small secondary" onclick="selectPaper('${paper.id}')">选择</button></td>
          <td>${paper.material_status}</td>
          <td>${paper.audit_status}</td>
          <td>${paper.algorithmic_signal_count}</td>
        </tr>
      `).join("");
    }

    function renderCandidates(data) {
      const items = data.items || [];
      const status = data.cached ? `本地缓存 · ${data.cache_status}` : `OpenAlex · ${data.cache_status || "live"}`;
      $("candidateStatus").textContent = `${items.length} 个候选 · ${status}`;
      if (!items.length) {
        $("candidates").innerHTML = `<div class="candidate-card muted">没有找到候选。可以换英文名、拼音、机构英文名，或直接粘贴 OpenAlex ID 后建库。</div>`;
        return;
      }
      $("candidates").innerHTML = items.map((item) => `
        <div class="candidate-card">
          <div>
            <h3>${item.display_name || "Unknown"}</h3>
            <div class="muted">${item.entity_type} · ${item.openalex_id || ""}</div>
            <div class="muted">${item.hint || item.country_code || ""}</div>
          </div>
          <div class="summary" style="grid-template-columns:1fr 1fr;margin:0">
            <div class="metric"><span class="muted">论文数</span><b>${item.works_count ?? ""}</b></div>
            <div class="metric"><span class="muted">来源</span><b style="font-size:14px">${data.cached ? "cache" : "live"}</b></div>
          </div>
          <div class="task-actions">
            <button class="small secondary" onclick="selectCandidate('${item.entity_type}', '${item.openalex_id || ""}', '${encodeURIComponent(item.display_name || "")}')">选择</button>
            <button class="small" onclick="buildCandidate('${item.entity_type}', '${item.openalex_id || ""}', '${encodeURIComponent(item.display_name || "")}')">立即建库</button>
            <button class="small" onclick="enqueueCandidate('${item.entity_type}', '${item.openalex_id || ""}', '${encodeURIComponent(item.display_name || "")}')">后台建库</button>
          </div>
        </div>
      `).join("");
    }

    function renderTasks(data) {
      const items = data.items || [];
      $("tasks").innerHTML = items.map((task) => `
        <tr>
          <td>${task.priority}</td>
          <td><b>${task.paper ? task.paper.title : ""}</b><div class="muted">${task.paper ? (task.paper.doi || task.paper.id) : ""}</div></td>
          <td>${task.signal ? task.signal.summary : task.task_type}<div class="muted">${task.artifact ? (task.artifact.filename || task.artifact.artifact_type) : ""}</div></td>
          <td>${task.status}<div class="muted">${task.decision || ""}</div></td>
          <td>
            <div class="task-actions">
              <button class="small" onclick="decideTask('${task.id}', 'confirmed_signal')">确认</button>
              <button class="small secondary" onclick="decideTask('${task.id}', 'false_positive')">误报</button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    function renderSignals(data) {
      const items = data.items || [];
      $("signals").innerHTML = items.map((signal) => `
        <tr>
          <td>${signal.severity}<div class="muted">${signal.confidence ?? ""}</div></td>
          <td><b>${signal.signal_type}</b><div class="muted">${signal.analyzer_name}</div><div>${signal.summary}</div></td>
          <td>${signal.paper ? `<b>${signal.paper.title}</b><div class="muted">${signal.paper.doi || signal.paper.id}</div>` : ""}</td>
          <td>${signal.status}</td>
        </tr>
      `).join("");
    }

    function renderBreakdown(data) {
      const units = data.affiliation_units || [];
      const authors = data.top_authors || [];
      $("breakdownStatus").textContent = `${units.length} 个 affiliation 单元 · ${authors.length} 个作者群 · ${data.method ? data.method.classification : ""}`;
      $("breakdown").innerHTML = [
        ...units.slice(0, 12).map((unit) => `
          <div class="candidate-card">
            <div>
              <h3>${unit.unit_name}</h3>
              <div class="muted">${unit.unit_type} · ${unit.paper_count} papers · ${unit.author_count} authors</div>
              <div class="muted">${(unit.sample_affiliations || [])[0] || ""}</div>
            </div>
            <div class="summary" style="grid-template-columns:1fr 1fr;margin:0">
              <div class="metric"><span class="muted">可审计</span><b>${unit.auditable_paper_count}</b></div>
              <div class="metric"><span class="muted">信号</span><b>${unit.signal_paper_count}</b></div>
            </div>
          </div>
        `),
        ...authors.slice(0, 8).map((author) => `
          <div class="candidate-card">
            <div>
              <h3>${author.display_name}</h3>
              <div class="muted">author · ${author.author_id || "raw metadata"}</div>
              <div class="muted">${(author.sample_affiliations || [])[0] || ""}</div>
            </div>
            <div class="summary" style="grid-template-columns:1fr 1fr;margin:0">
              <div class="metric"><span class="muted">论文</span><b>${author.paper_count}</b></div>
              <div class="metric"><span class="muted">通讯</span><b>${author.corresponding_author_paper_count}</b></div>
            </div>
          </div>
        `)
      ].join("");
    }

    function renderPaperSearch(data) {
      const items = data.items || [];
      $("papers").innerHTML = items.map((paper) => `
        <tr>
          <td>${paper.publication_year || ""}</td>
          <td>
            <b>${html(paper.title)}</b>
            <div class="muted">${html(paper.doi || paper.id)}</div>
            <button class="small secondary" onclick="selectPaper('${paper.id}', '${encodeURIComponent(paper.doi || "")}')">选择</button>
          </td>
          <td>${html(paper.risk_status ? paper.risk_status.highest_signal_level : "")}</td>
          <td>${html(paper.risk_status ? paper.risk_status.summary : "")}</td>
          <td>${paper.risk_status ? paper.risk_status.algorithmic_signal_count : ""}</td>
        </tr>
      `).join("");
      $("paperRisk").innerHTML = `<p class="muted">找到 ${data.total ?? items.length} 篇论文。</p>`;
    }

    function renderPaperDetail(data) {
      const paper = data.paper || {};
      if (paper.id) $("paperId").value = paper.id;
      if (paper.doi) $("paperDoi").value = paper.doi;
      const events = data.events || [];
      const signals = data.algorithmic_signals || [];
      const artifacts = data.artifacts || [];
      const risk = data.risk_status || {};
      $("paperRisk").innerHTML = `
        <div class="summary">
          <div class="metric"><span class="muted">论文</span><b style="font-size:16px">${html(paper.publication_year || "")}</b></div>
          <div class="metric"><span class="muted">材料</span><b>${artifacts.length}</b></div>
          <div class="metric"><span class="muted">事件</span><b>${events.length}</b></div>
          <div class="metric"><span class="muted">风险级别</span><b style="font-size:16px">${html(risk.highest_signal_level || "none")}</b></div>
        </div>
        <p><b>${html(paper.title || "")}</b></p>
        <p>${html(risk.summary || "")}</p>
        <p class="muted">${html(paper.journal_name || "")} · ${html(paper.doi || "")}</p>
        <div class="link-list">${sourceLink(paper.landing_page_url)}${paper.open_access_url ? sourceLink(paper.open_access_url) : ""}</div>
        ${events.length ? `<table><thead><tr><th>事件</th><th>级别</th><th>来源</th><th>摘要</th></tr></thead><tbody>${events.map((event) => `
          <tr>
            <td>${html(event.event_type)}</td>
            <td>${html(event.status_level)}</td>
            <td>${sourceLink(event.source_url)}<div class="muted">${html(event.verification_status || "")}</div></td>
            <td>${html(event.claim_summary || "")}</td>
          </tr>
        `).join("")}</tbody></table>` : ""}
      `;
      if (artifacts.length) renderArtifacts({ items: artifacts, material_status: paper.material_status });
    }

    function renderRiskCard(data) {
      const card = data.risk_card || data.risk_status || data;
      const paper = data.paper || {};
      const evidence = card.evidence || data.evidence || [];
      $("paperRisk").innerHTML = `
        <div class="summary">
          <div class="metric"><span class="muted">最高级别</span><b style="font-size:16px">${html(card.highest_signal_level || "")}</b></div>
          <div class="metric"><span class="muted">官方状态</span><b style="font-size:16px">${html(card.official_status || "")}</b></div>
          <div class="metric"><span class="muted">机构状态</span><b style="font-size:16px">${html(card.institution_status || "")}</b></div>
          <div class="metric"><span class="muted">算法信号</span><b>${card.algorithmic_signal_count ?? 0}</b></div>
        </div>
        <p><b>${html(paper.title || card.title || "")}</b></p>
        <p>${html(card.summary || "")}</p>
        <p class="muted">${html(data.conclusion_boundary || "这些只是索引事件与算法信号，不能直接认定论文造假。")}</p>
        ${evidence.length ? `<table><thead><tr><th>证据</th><th>位置</th><th>来源</th></tr></thead><tbody>${evidence.map((item) => `
          <tr>
            <td>${html(item.summary || item.signal_type || item.status_level || "")}</td>
            <td>${html([item.figure_label, item.panel_label, item.table_label, item.column_name].filter(Boolean).join(" / "))}</td>
            <td>${sourceLink(item.evidence_url || item.source_url || item.artifact_url)}</td>
          </tr>
        `).join("")}</tbody></table>` : ""}
      `;
    }

    function renderArtifacts(data) {
      const items = data.items || (data.artifact ? [data.artifact] : []);
      $("artifactStatus").textContent = `${items.length} 个材料 · ${data.material_status || ""}`;
      $("artifacts").innerHTML = items.map((artifact) => {
        const fetched = artifact.storage_uri ? "已本地化" : "仅登记";
        const type = artifact.artifact_type || "";
        const filename = artifact.filename || artifact.source_url || "";
        const contentType = artifact.content_type || "";
        const isImage = ["figure_image", "image_panel", "supplementary_image"].includes(type) || contentType.startsWith("image/");
        const isNumeric = ["source_data", "supplementary_table"].includes(type) || /\\.(csv|tsv|tab|xlsx|xlsm)$/i.test(filename);
        const canFetch = /^https?:\\/\\//i.test(artifact.source_url || "") && !artifact.storage_uri;
        const actions = [
          `<button class="small secondary" onclick="selectArtifact('${artifact.id}', '${encodeURIComponent(type)}', '${encodeURIComponent(artifact.source_url || "")}')">选择</button>`,
          isImage ? `<button class="small secondary" onclick="addCompareArtifact('${artifact.id}')">加入对比</button>` : "",
          canFetch ? `<button class="small secondary" onclick="fetchArtifact('${artifact.id}')">拉取</button>` : "",
          isNumeric ? `<button class="small" onclick="auditArtifact('${artifact.id}', 'numeric')">数值审计</button>` : "",
          isImage ? `<button class="small" onclick="auditArtifact('${artifact.id}', 'image')">图像审计</button>` : ""
        ].filter(Boolean).join("");
        return `
          <tr>
            <td><b>${html(artifact.artifact_type)}</b><div class="muted">${html(artifact.content_type || "")}</div></td>
            <td>
              <b>${html(artifact.filename || shortId(artifact.id))}</b>
              <div class="muted">${html(artifact.id)}</div>
              <div class="link-list">${sourceLink(artifact.source_url)}</div>
            </td>
            <td>${fetched}<div class="muted">${html(artifact.license_status || "")}</div></td>
            <td>
              <div class="task-actions">
                ${actions}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }

    function renderJobs(data) {
      const items = data.items || [data].filter((item) => item && item.id);
      $("jobs").innerHTML = items.map((job) => {
        const actions = [
          job.status === "queued" ? `<button class="small secondary" onclick="runJob('${job.id}')">运行</button>` : "",
          job.status === "failed" ? `<button class="small secondary" onclick="retryJob('${job.id}')">重试</button>` : ""
        ].filter(Boolean).join("") || `<span class="muted">无待执行操作</span>`;
        return `
          <tr>
            <td><b>${html(job.job_type)}</b><div class="muted">${html(job.id)}</div></td>
            <td>${html(job.status)}<div class="muted">${job.attempts}/${job.max_attempts}</div>${job.error_message ? `<div>${html(job.error_message)}</div>` : ""}</td>
            <td><div class="muted">queued ${html(job.queued_at || "")}</div><div class="muted">done ${html(job.finished_at || "")}</div></td>
            <td><div class="task-actions">${actions}</div></td>
          </tr>
        `;
      }).join("");
    }

    function renderSchedules(data) {
      const items = data.items || [data].filter((item) => item && item.id);
      $("schedules").innerHTML = items.map((schedule) => {
        const actions = [
          schedule.status === "paused" ? `<button class="small secondary" onclick="setScheduleStatus('${schedule.id}', 'active')">恢复</button>` : "",
          schedule.status === "active" ? `<button class="small secondary" onclick="setScheduleStatus('${schedule.id}', 'paused')">暂停</button>` : "",
          schedule.status !== "cancelled" ? `<button class="small secondary" onclick="setScheduleStatus('${schedule.id}', 'cancelled')">取消</button>` : ""
        ].filter(Boolean).join("") || `<span class="muted">无待执行操作</span>`;
        return `
          <tr>
            <td><b>${html(schedule.name)}</b><div class="muted">${html(schedule.job_type)} · ${html(schedule.id)}</div></td>
            <td>${html(schedule.status)}<div class="muted">${schedule.interval_seconds}s</div></td>
            <td>${html(schedule.next_run_at || "")}<div class="muted">last ${html(schedule.last_run_at || "")}</div></td>
            <td><div class="task-actions">${actions}</div></td>
          </tr>
        `;
      }).join("");
    }

    function renderReport(data) {
      if (!data || !data.entity) return;
      const profile = data.profile || {};
      const signals = data.signals || { items: [] };
      const tasks = data.open_review_tasks || { items: [] };
      $("report").innerHTML = `
        <div class="summary">
          <div class="metric"><span class="muted">报告实体</span><b style="font-size:16px">${html(data.entity.display_name)}</b></div>
          <div class="metric"><span class="muted">论文</span><b>${profile.paper_count ?? 0}</b></div>
          <div class="metric"><span class="muted">可见信号</span><b>${signals.total ?? (signals.items || []).length}</b></div>
          <div class="metric"><span class="muted">开放复核</span><b>${tasks.total ?? (tasks.items || []).length}</b></div>
        </div>
        <p>${html(profile.summary || "")}</p>
        <p class="muted">${html(data.conclusion_boundary || "")}</p>
      `;
      renderSignals(signals);
      renderTasks(tasks);
    }

    function renderArchives(data) {
      const items = data.items || [];
      $("archives").innerHTML = items.map((snapshot) => `
        <tr>
          <td><b>${html(snapshot.entity_display_name || snapshot.entity_id)}</b><div class="muted">${html(snapshot.entity_type)} · ${html(snapshot.entity_id)}</div></td>
          <td>${html(snapshot.report_format)}<div class="muted">${html(snapshot.content_sha256 || "")}</div></td>
          <td>${html(snapshot.created_at || "")}</td>
          <td>
            <div class="task-actions">
              <button class="small secondary" onclick="openArchive('${snapshot.id}', 'json')">查看 JSON</button>
              <a href="/api/reports/archive/${snapshot.id}?format=markdown" target="_blank" rel="noopener noreferrer">Markdown</a>
            </div>
          </td>
        </tr>
      `).join("");
    }

    function renderAuditLogs(data) {
      const items = data.items || [];
      $("auditLogs").innerHTML = items.map((item) => `
        <tr>
          <td>${html(item.created_at || "")}</td>
          <td><b>${html(item.action)}</b><div class="muted">${html(item.actor || "")}</div></td>
          <td>${html(item.target_type || "")}<div class="muted">${html(item.target_id || item.paper_id || item.artifact_id || "")}</div></td>
          <td>${html(item.summary || "")}</td>
        </tr>
      `).join("");
    }

    window.selectPaper = (paperId, encodedDoi = "") => {
      $("paperId").value = paperId;
      const doi = decodeURIComponent(encodedDoi || "");
      if (doi) $("paperDoi").value = doi;
    };

    window.selectArtifact = (artifactId, artifactType, encodedSourceUrl) => {
      $("artifactId").value = artifactId;
      const decodedType = decodeURIComponent(artifactType || "");
      if (decodedType) $("artifactType").value = decodedType;
      const sourceUrl = decodeURIComponent(encodedSourceUrl || "");
      if (sourceUrl) $("sourceUrl").value = sourceUrl;
    };

    window.addCompareArtifact = (artifactId) => {
      const existing = compareArtifactIds();
      if (!existing.includes(artifactId)) existing.push(artifactId);
      $("compareArtifactIds").value = existing.join("\\n");
    };

    function compareArtifactIds() {
      return value("compareArtifactIds")
        .split(/[\\n,]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    window.selectCandidate = (entityType, openalexId, encodedName) => {
      $("entityType").value = entityType;
      $("openalexId").value = openalexId;
      $("query").value = decodeURIComponent(encodedName || "");
    };

    window.buildCandidate = async (entityType, openalexId, encodedName) => {
      try {
        selectCandidate(entityType, openalexId, encodedName);
        await buildCorpus();
      } catch (error) { log(error); }
    };

    window.enqueueCandidate = async (entityType, openalexId, encodedName) => {
      try {
        selectCandidate(entityType, openalexId, encodedName);
        await enqueueCorpusJob();
      } catch (error) { log(error); }
    };

    window.decideTask = async (taskId, decision) => {
      try {
        const data = await request(`/api/review/tasks/${taskId}/decision`, {
          method: "POST",
          body: JSON.stringify({ decision })
        });
        log(data);
        const tasks = await request("/api/review/tasks?status=all");
        renderTasks(tasks);
      } catch (error) { log(error); }
    };

    window.fetchArtifact = async (artifactId) => {
      try {
        const data = await request("/api/artifacts/fetch", {
          method: "POST",
          body: JSON.stringify({ artifact_id: artifactId, license_status: "open_or_linked" })
        });
        $("artifactId").value = data.artifact.id;
        log(data);
        await refreshArtifacts();
      } catch (error) { log(error); }
    };

    window.auditArtifact = async (artifactId, analyzer) => {
      try {
        const path = analyzer === "image" ? "/api/audits/image" : "/api/audits/numeric";
        const payload = analyzer === "image"
          ? { artifact_id: artifactId, compare_artifact_ids: compareArtifactIds(), priority: 8 }
          : { artifact_id: artifactId, priority: 8 };
        if (analyzer === "image" && !payload.compare_artifact_ids.length) delete payload.compare_artifact_ids;
        const data = await request(path, { method: "POST", body: JSON.stringify(payload) });
        log(data);
        const tasks = await request("/api/review/tasks");
        renderTasks(tasks);
        const signals = await request("/api/signals?status=all");
        renderSignals(signals);
      } catch (error) { log(error); }
    };

    window.runJob = async (jobId) => {
      try {
        const data = await request(`/api/jobs/${jobId}/run`, { method: "POST", body: JSON.stringify({}) });
        log(data);
        const jobs = await request("/api/jobs?limit=20");
        renderJobs(jobs);
      } catch (error) { log(error); }
    };

    window.retryJob = async (jobId) => {
      try {
        const data = await request(`/api/jobs/${jobId}/retry`, { method: "POST", body: JSON.stringify({}) });
        log(data);
        const jobs = await request("/api/jobs?limit=20");
        renderJobs(jobs);
      } catch (error) { log(error); }
    };

    window.setScheduleStatus = async (scheduleId, status) => {
      try {
        const data = await request(`/api/jobs/schedules/${scheduleId}/status`, {
          method: "POST",
          body: JSON.stringify({ status })
        });
        log(data);
        const schedules = await request("/api/jobs/schedules?limit=20");
        renderSchedules(schedules);
      } catch (error) { log(error); }
    };

    window.openArchive = async (snapshotId, format) => {
      try {
        const data = await request(`/api/reports/archive/${snapshotId}?format=${format}`);
        log(data);
        if (data.content_json) renderReport(data.content_json);
      } catch (error) { log(error); }
    };

    async function refreshArtifacts() {
      const paperId = value("paperId");
      if (!paperId) return;
      const data = await request(`/api/artifacts/papers/${paperId}`);
      renderArtifacts(data);
      return data;
    }

    $("searchBtn").onclick = async () => {
      try {
        await withBusy("searchBtn", "搜索中", async () => {
          if (value("entityType") === "group") throw { detail: "课题组需要先用本地作者/机构 ID 创建，不能直接 OpenAlex 搜索" };
          const data = await request(`/api/entities/search?entity_type=${value("entityType")}&query=${encodeURIComponent(value("query"))}`);
          log(data);
          renderCandidates(data);
        });
      } catch (error) { log(error); }
    };

    function corpusPayload() {
      return {
        entity_type: value("entityType"),
        query: value("query"),
        openalex_id: value("openalexId") || null,
        display_name: value("query") || null,
        limit: intValue("limit") || 25,
        year_from: intValue("yearFrom"),
        year_to: intValue("yearTo")
      };
    }

    async function buildCorpus() {
      if (value("entityType") === "group") return buildGroupCorpus();
      const data = await request("/api/entities/corpus", {
        method: "POST",
        body: JSON.stringify(corpusPayload())
      });
      log(data);
      renderProfile(data.profile);
    }

    async function buildGroupCorpus() {
      const data = await request("/api/entities/groups/corpus", {
        method: "POST",
        body: JSON.stringify({
          display_name: value("query") || "Local group",
          members: parseGroupCorpusMembers(),
          continue_on_error: true
        })
      });
      $("entityType").value = "group";
      $("entityId").value = data.entity.id;
      log(data);
      renderProfile(data.profile);
      syncEntityControls();
      return data;
    }

    async function enqueueCorpusJob() {
      if (value("entityType") === "group") throw { detail: "课题组后台建库暂未开放；请使用课题组建库立即执行" };
      const data = await request("/api/jobs/entity-corpus", {
        method: "POST",
        body: JSON.stringify(corpusPayload())
      });
      log(data);
    }

    $("buildBtn").onclick = async () => {
      try {
        await withBusy("buildBtn", "建库中", buildCorpus);
      } catch (error) { log(error); }
    };

    $("corpusJobBtn").onclick = async () => {
      try {
        await withBusy("corpusJobBtn", "已加入队列", enqueueCorpusJob);
      } catch (error) { log(error); }
    };

    $("importCorpusBtn").onclick = async () => {
      try {
        const file = $("entityManifestFile").files[0];
        if (!file) throw { detail: "请选择实体名单文件" };
        const form = new FormData();
        form.append("file", file);
        form.append("default_limit", String(intValue("limit") || 25));
        if (value("yearFrom")) form.append("default_year_from", value("yearFrom"));
        if (value("yearTo")) form.append("default_year_to", value("yearTo"));
        form.append("continue_on_error", "true");
        const headers = {};
        if (value("apiKey")) headers["x-api-key"] = value("apiKey");
        const response = await fetch("/api/entities/corpus/import", { method: "POST", headers, body: form });
        const data = await response.json();
        if (!response.ok) throw data;
        log(data);
        if ((data.items || []).length) renderProfile(data.items[0].profile);
      } catch (error) { log(error); }
    };

    function parseGroupMembers() {
      return value("groupMembers").split(/\\n+/).map((line) => line.trim()).filter(Boolean).map((line) => {
        const [entityType, entityId] = splitMemberLine(line);
        if (!entityType || !entityId) throw { detail: "组成员格式应为 author:<id> 或 institution:<id>" };
        return { entity_type: entityType, entity_id: entityId };
      });
    }

    function splitMemberLine(line) {
      const index = line.indexOf(":");
      if (index < 0) return ["", ""];
      return [line.slice(0, index).trim(), line.slice(index + 1).trim()];
    }

    function parseGroupCorpusMembers() {
      return value("groupMembers").split(/\\n+/).map((line) => line.trim()).filter(Boolean).map((line) => {
        const [entityType, rest] = splitMemberLine(line);
        if (!entityType || !rest) throw { detail: "组成员格式应为 author:<name|OpenAlexID> 或 institution:<name|OpenAlexID>" };
        const parts = rest.split("|").map((part) => part.trim()).filter(Boolean);
        const first = parts[0] || "";
        const second = parts[1] || "";
        const firstIsOpenAlex = /^(https?:\\/\\/openalex\\.org\\/)?[AI]\\d+$/i.test(first);
        const secondIsOpenAlex = /^(https?:\\/\\/openalex\\.org\\/)?[AI]\\d+$/i.test(second);
        return {
          entity_type: entityType,
          query: firstIsOpenAlex ? null : first,
          openalex_id: secondIsOpenAlex ? second : (firstIsOpenAlex ? first : null),
          display_name: firstIsOpenAlex ? null : first,
          limit: intValue("limit") || 25,
          year_from: intValue("yearFrom"),
          year_to: intValue("yearTo")
        };
      });
    }

    $("createGroupBtn").onclick = async () => {
      try {
        const data = await request("/api/entities/groups", {
          method: "POST",
          body: JSON.stringify({
            display_name: value("query") || "Local group",
            members: parseGroupMembers()
          })
        });
        $("entityType").value = "group";
        $("entityId").value = data.entity.id;
        log(data);
        renderProfile(data.profile);
      } catch (error) { log(error); }
    };

    $("buildGroupCorpusBtn").onclick = async () => {
      try {
        await withBusy("buildGroupCorpusBtn", "建库中", buildGroupCorpus);
      } catch (error) { log(error); }
    };

    $("profileBtn").onclick = async () => {
      try {
        const data = await request(`/api/entities/${value("entityType")}/${value("entityId")}/profile`);
        log(data);
        renderProfile(data);
      } catch (error) { log(error); }
    };

    $("breakdownBtn").onclick = async () => {
      try {
        const data = await request(`/api/entities/${value("entityType")}/${value("entityId")}/breakdown?limit=24&min_papers=1`);
        log(data);
        renderBreakdown(data);
      } catch (error) { log(error); }
    };

    $("queueBtn").onclick = async () => {
      try {
        const data = await request("/api/entities/review-queue", {
          method: "POST",
          body: JSON.stringify({ entity_type: value("entityType"), entity_id: value("entityId"), priority: 7 })
        });
        log(data);
        renderProfile(data.profile);
      } catch (error) { log(error); }
    };

    $("metadataAuditBtn").onclick = async () => {
      try {
        const data = await request("/api/audits/metadata", {
          method: "POST",
          body: JSON.stringify({
            entity_type: value("entityType"),
            entity_id: value("entityId"),
            min_cluster_size: 5,
            priority: 6
          })
        });
        log(data);
        const signals = await request(`/api/entities/${value("entityType")}/${value("entityId")}/signals?status=all`);
        renderSignals(signals);
        const tasks = await request("/api/review/tasks");
        renderTasks(tasks);
      } catch (error) { log(error); }
    };

    $("signalsBtn").onclick = async () => {
      try {
        const data = await request(`/api/entities/${value("entityType")}/${value("entityId")}/signals?status=all`);
        log(data);
        renderSignals(data);
      } catch (error) { log(error); }
    };

    $("reportBtn").onclick = async () => {
      try {
        const data = await request(`/api/reports/entity?entity_type=${value("entityType")}&entity_id=${value("entityId")}`);
        log(data);
        renderReport(data);
      } catch (error) { log(error); }
    };

    $("archiveReportBtn").onclick = async () => {
      try {
        const data = await request("/api/reports/entity/archive", {
          method: "POST",
          body: JSON.stringify({
            entity_type: value("entityType"),
            entity_id: value("entityId"),
            formats: ["json", "markdown"]
          })
        });
        log(data);
        renderArchives(data);
      } catch (error) { log(error); }
    };

    $("archiveListBtn").onclick = async () => {
      try {
        const query = value("entityId") ? `?entity_type=${value("entityType")}&entity_id=${value("entityId")}` : "";
        const data = await request(`/api/reports/archive${query}`);
        log(data);
        renderArchives(data);
      } catch (error) { log(error); }
    };

    $("pruneArchiveBtn").onclick = async () => {
      try {
        const data = await request("/api/reports/archive/prune", {
          method: "POST",
          body: JSON.stringify({
            entity_type: value("entityId") ? value("entityType") : null,
            entity_id: value("entityId") || null,
            format: "all",
            keep_latest: intValue("archiveKeepLatest"),
            older_than_days: intValue("archiveOlderDays"),
            dry_run: $("archiveDryRun").checked
          })
        });
        log(data);
        renderArchives(data);
        $("report").innerHTML = `<p>${data.dry_run ? "预计清理" : "已清理"} ${data.pruned_count} 个归档快照。</p>`;
      } catch (error) { log(error); }
    };

    $("jobBtn").onclick = async () => {
      try {
        const data = await request("/api/jobs/entity-cycle", {
          method: "POST",
          body: JSON.stringify({
            entity_type: value("entityType"),
            entity_id: value("entityId"),
            min_cluster_size: 5,
            priority: 6
          })
        });
        log(data);
        const jobs = await request("/api/jobs?limit=20");
        renderJobs(jobs);
      } catch (error) { log(error); }
    };

    $("scheduleBtn").onclick = async () => {
      try {
        const data = await request("/api/jobs/schedules/entity-cycle", {
          method: "POST",
          body: JSON.stringify({
            name: `${value("entityType")} ${value("entityId")} audit`,
            interval_seconds: intValue("scheduleInterval") || 604800,
            run_immediately: false,
            job: {
              entity_type: value("entityType"),
              entity_id: value("entityId"),
              inspect_landing_pages: $("inspectLanding").checked,
              min_cluster_size: 5,
              priority: 6
            }
          })
        });
        log(data);
        const schedules = await request("/api/jobs/schedules?limit=20");
        renderSchedules(schedules);
      } catch (error) { log(error); }
    };

    $("jobsBtn").onclick = async () => {
      try {
        const data = await request("/api/jobs?limit=20");
        log(data);
        renderJobs(data);
      } catch (error) { log(error); }
    };

    $("schedulesBtn").onclick = async () => {
      try {
        const data = await request("/api/jobs/schedules?limit=20");
        log(data);
        renderSchedules(data);
      } catch (error) { log(error); }
    };

    $("runDueBtn").onclick = async () => {
      try {
        const data = await request("/api/jobs/schedules/run-due", { method: "POST", body: JSON.stringify({}) });
        log(data);
        const jobs = await request("/api/jobs?limit=20");
        renderJobs(jobs);
        const schedules = await request("/api/jobs/schedules?limit=20");
        renderSchedules(schedules);
      } catch (error) { log(error); }
    };

    $("importDoiBtn").onclick = async () => {
      try {
        await withBusy("importDoiBtn", "导入中", async () => {
          const doi = value("paperDoi") || value("sourceUrl");
          if (!doi) throw { detail: "请输入 DOI" };
          const data = await request("/api/admin/import/doi", {
            method: "POST",
            body: JSON.stringify({ doi, sources: ["openalex", "crossref"] })
          });
          $("paperId").value = data.id;
          log(data);
          await refreshArtifacts();
        });
      } catch (error) { log(error); }
    };

    $("paperSearchBtn").onclick = async () => {
      try {
        const params = new URLSearchParams({ limit: "20" });
        if (value("paperDoi")) params.set("doi", value("paperDoi"));
        else params.set("query", value("query"));
        const data = await request(`/api/papers?${params.toString()}`);
        log(data);
        renderPaperSearch(data);
      } catch (error) { log(error); }
    };

    $("paperDetailBtn").onclick = async () => {
      try {
        const doi = value("paperDoi");
        if (!doi) throw { detail: "请输入 DOI" };
        const data = await request(`/api/papers/${encodeURIComponent(doi)}`);
        log(data);
        renderPaperDetail(data);
      } catch (error) { log(error); }
    };

    $("riskCardBtn").onclick = async () => {
      try {
        const doi = value("paperDoi");
        if (!doi) throw { detail: "请输入 DOI" };
        const data = await request(`/api/papers/${encodeURIComponent(doi)}/risk-card`);
        log(data);
        renderRiskCard(data);
      } catch (error) { log(error); }
    };

    $("agentSummaryBtn").onclick = async () => {
      try {
        const doi = value("paperDoi");
        if (!doi) throw { detail: "请输入 DOI" };
        const data = await request(`/api/agent/doi/${encodeURIComponent(doi)}`);
        log(data);
        renderRiskCard(data);
      } catch (error) { log(error); }
    };

    $("paperArtifactsBtn").onclick = async () => {
      try {
        const data = await refreshArtifacts();
        log(data || { detail: "请先填写论文 ID，或先导入 DOI" });
      } catch (error) { log(error); }
    };

    $("uploadBtn").onclick = async () => {
      try {
        const file = $("artifactFile").files[0];
        if (!file) throw { detail: "请选择文件" };
        const form = new FormData();
        if (value("paperId")) form.append("paper_id", value("paperId"));
        if (value("paperDoi")) form.append("doi", value("paperDoi"));
        form.append("artifact_type", value("artifactType"));
        form.append("license_status", "manual_upload");
        if (value("sourceUrl")) form.append("source_url", value("sourceUrl"));
        form.append("file", file);
        const headers = {};
        if (value("apiKey")) headers["x-api-key"] = value("apiKey");
        const response = await fetch("/api/artifacts/upload", { method: "POST", headers, body: form });
        const data = await response.json();
        if (!response.ok) throw data;
        $("artifactId").value = data.artifact.id;
        log(data);
        await refreshArtifacts();
      } catch (error) { log(error); }
    };

    $("discoverBtn").onclick = async () => {
      try {
        const data = await request("/api/artifacts/discover", {
          method: "POST",
          body: JSON.stringify({
            paper_id: value("paperId") || null,
            doi: value("paperDoi") || null,
            inspect_landing_pages: $("inspectLanding").checked
          })
        });
        const first = (data.items || []).find((item) => item.artifact_type === "paper_pdf") || (data.items || [])[0];
        if (first) {
          $("artifactId").value = first.id;
          $("sourceUrl").value = first.source_url || "";
        }
        log(data);
        renderArtifacts(data);
      } catch (error) { log(error); }
    };

    $("fetchBtn").onclick = async () => {
      try {
        const data = await request("/api/artifacts/fetch", {
          method: "POST",
          body: JSON.stringify({
            artifact_id: value("artifactId") || null,
            paper_id: value("paperId") || null,
            doi: value("paperDoi") || null,
            artifact_type: value("artifactType"),
            source_url: value("sourceUrl") || null,
            license_status: "open_or_linked"
          })
        });
        $("artifactId").value = data.artifact.id;
        log(data);
        await refreshArtifacts();
      } catch (error) { log(error); }
    };

    $("auditBtn").onclick = async () => {
      try {
        await auditArtifact(value("artifactId"), "numeric");
      } catch (error) { log(error); }
    };

    $("imageAuditBtn").onclick = async () => {
      try {
        await auditArtifact(value("artifactId"), "image");
      } catch (error) { log(error); }
    };

    $("tasksBtn").onclick = async () => {
      try {
        const data = await request("/api/review/tasks?status=all");
        log(data);
        renderTasks(data);
      } catch (error) { log(error); }
    };

    $("auditLogBtn").onclick = async () => {
      try {
        const query = value("entityId") ? `?entity_type=${value("entityType")}&entity_id=${value("entityId")}` : "";
        const data = await request(`/api/audit-log${query}`);
        log(data);
        renderAuditLogs(data);
      } catch (error) { log(error); }
    };

    const eventPresets = {
      public_discussion: { status: "public_discussion", source: "pubpeer", verification: "unverified" },
      media_report: { status: "media_report", source: "media", verification: "source_verified" },
      institution_notice: { status: "institution_investigation", source: "institution", verification: "source_verified" },
      correction: { status: "official_correction", source: "publisher", verification: "official_confirmed" },
      retraction: { status: "official_retraction", source: "publisher", verification: "official_confirmed" }
    };

    $("eventType").onchange = () => {
      const preset = eventPresets[value("eventType")];
      if (!preset) return;
      $("eventStatusLevel").value = preset.status;
      $("eventSourceType").value = preset.source;
      $("eventVerification").value = preset.verification;
    };

    $("eventBtn").onclick = async () => {
      try {
        const doi = value("paperDoi");
        if (!doi) throw { detail: "请输入 DOI" };
        const data = await request("/api/admin/events", {
          method: "POST",
          body: JSON.stringify({
            doi,
            event_type: value("eventType"),
            status_level: value("eventStatusLevel"),
            source_type: value("eventSourceType"),
            source_url: value("eventSourceUrl"),
            claim_summary: value("eventSummary"),
            verification_status: value("eventVerification")
          })
        });
        log(data);
        const agent = await request(`/api/agent/doi/${encodeURIComponent(doi)}`);
        renderRiskCard(agent);
      } catch (error) { log(error); }
    };

    syncEntityControls();
    $("eventType").onchange();
  </script>
</body>
</html>
"""
