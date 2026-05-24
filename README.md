# 耿同学.skill / GengScope

- [中文说明](#中文说明)
- [English README](#english-readme)

## 中文说明

### 项目定位

耿同学.skill / GengScope 是一个面向中国研究机构公开论文的科研完整性索引平台。

GengScope 的第一目标不是判定论文造假，而是建立一个可检索、可追溯、可纠错的基础索引：把论文、作者、机构、实验室、期刊、公开质疑、官方处理、算法异常信号和证据位置放在同一个结构化系统里。

当前产品方向是 entity-driven：以作者、机构、实验室或本地名单为入口，先建立该实体的论文全库，再寻找 PDF、supplementary、source data 等可审计材料，最后生成实体级覆盖率、审计队列和风险画像。DOI 是论文标识，不是唯一入口。

中文产品名可使用“耿同学科研索引”或“耿同学论文索引”。对外发布 skill 时，中文展示名使用“耿同学.skill”，英文包名、触发名和 CLI 保持 `gengscope`。对外发布时应明确本项目是独立工具，不代表任何个人或第三方官方授权。

### 产品范围

第一版聚焦 2020 年以来中国大陆机构参与发表的生命科学、医学、生物材料、纳米医学方向论文。

平台回答五类问题：

- 某篇论文有哪些公开风险信号？
- 某个作者或机构涉及哪些论文、事件和官方状态？
- 某个作者、实验室或机构的论文全库中，有多少论文找到了可审计材料？
- 某个公开质疑是否能定位到具体图、表、source data 或 supplementary 文件？
- Codex、Claude Code 等 agent 能否通过本地 HTTP API 查询并生成可复核的审计摘要？

### 核心边界

除非期刊、机构、监管部门或作者公开确认，不得把任何论文标记为“造假”。平台只使用分级状态：

- `official_retraction`
- `official_correction`
- `official_expression_of_concern`
- `institution_investigation`
- `institution_conclusion`
- `public_discussion`
- `media_report`
- `algorithmic_signal`
- `manual_review_needed`

### 代码结构

```text
apps/
  web/                 Web 产品前端
services/
  api/                 后端 API
  worker/              数据采集、清洗、审计任务
packages/
  shared-schema/       JSON Schema / OpenAPI / TypeScript 类型
data/
  seeds/               可提交的小型种子数据
  samples/             小型测试样本，不提交大文件
skills/
  gengscope/           可发布的 Codex/GPT 工作流 skill
infra/
  docker/              本地开发依赖
  migrations/          数据库迁移
scripts/
  ingest/              命令行采集脚本
docs/
  product-design.md
  technical-plan.md
  data-model.md
  roadmap.md
  skill-integration.md
  governance.md
```

### 文档入口

- [Product Design](docs/product-design.md)
- [Entity-Driven System Design](docs/entity-driven-system.md)
- [Technical Plan](docs/technical-plan.md)
- [Data Model](docs/data-model.md)
- [API Contract](docs/api-contract.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Seed Cases](docs/seed-cases.md)
- [Roadmap](docs/roadmap.md)
- [Skill Integration](docs/skill-integration.md)
- [耿同学.skill Case Demo](docs/skill-case-demo.md)
- [Retraction Calibration](docs/retraction-calibration.md)
- [Governance](docs/governance.md)

### 运行当前 MVP

当前可运行部分是本地 HTTP API 和同端口 workbench，不是 MCP server。

```bash
cd services/api
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest
gengscope serve --reload
```

打开：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

也可以从仓库根目录使用 Docker Compose：

```bash
cp infra/docker/.env.example infra/docker/.env
docker compose -f infra/docker/docker-compose.yml up --build api worker
```

Docker 默认把 API 暴露在 `http://127.0.0.1:8010/`。如果该端口空闲，也可以设置 `GENGSCOPE_API_PORT=8000`。Compose stack 会等待 PostgreSQL ready，暴露 `/health/ready` 用于检查数据库、迁移和 artifact volume，运行后台 worker，并把上传材料存储在 `gengscope_artifacts` Docker volume。

安装后的 CLI 是 skill、CI 和 shell 用户使用的本地自动化入口：

```bash
gengscope health --base-url http://127.0.0.1:8010
gengscope search "Tsinghua University" --entity-type institution --base-url http://127.0.0.1:8010
gengscope import-doi "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
gengscope agent-summary "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
```

日常使用时，先打开 Workbench。搜索作者或机构，选择正确 candidate card，然后立即建立 corpus，或排队“后台建库”，避免浏览器等待 OpenAlex 和 Crossref。Entity search 结果会持久化到 `entity_search_cache`；同一个 query 被 OpenAlex 服务过一次后，重复搜索会从本地数据库返回，并在响应里标记结果是 `cached`、`stale` 还是 freshly `refreshed`。需要强制实时刷新时，可以给 `/api/entities/search` 加 `refresh=true`。

构建机构 corpus 后，可使用 `GET /api/entities/institution/<id>/breakdown` 或 Workbench 的“结构拆分”按钮，把原始 affiliation 分组成可能的学院、系、研究所、实验室和作者集群。这个拆分是启发式、复核导向的，用于决定扩展审计覆盖范围，不用于确定行政责任。

备份和恢复本地 PostgreSQL 数据库：

```bash
scripts/db_migrate.sh
scripts/db_backup.sh
GENGSCOPE_ALLOW_RESTORE=1 scripts/db_restore.sh backups/gengscope_YYYYMMDD_HHMMSS.sql
```

### 第一阶段工程目标

当前工程目标是构建 entity-driven 本地 API MVP：

1. 通过 OpenAlex 搜索作者和机构。
2. 为作者或机构建立本地论文 corpus。
3. 从本地 entity list 批量建立 corpus。
4. 导入 CSV、TSV、JSON entity manifest。
5. 从多个 resolved authors 和 institutions 创建本地 group/lab entity。
6. 追踪论文材料状态：metadata only、landing page、PDF、source data 或 fully auditable。
7. 生成实体级覆盖率和风险画像。
8. 加入小样本推断边界，让高信号密度提高复核优先级，但不暗示全库 misconduct。
9. 将可审计论文加入复核队列。
10. 发现 PMC、landing page 和 publisher-specific 材料链接，并把 source data、PDF、image artifact 上传、登记或 HTTP-fetch 到本地存储。
11. 运行 numeric、image 和 metadata audit checks，并写入带证据位置的 algorithmic signals。
12. 在第一版 deterministic image analyzer 中检测 whole-image、flip/rotation 和 local crop/patch image similarity。
13. 维护 numeric、image 和 metadata analyzer 的 deterministic、review-labeled golden regression cases。
14. 按全局、作者、机构或 group 浏览 signals。
15. 将 signals 复核为 confirmed、false positive、not actionable 或 needing more evidence。
16. 生成中性 paper 和 entity risk cards。
17. 导出并归档可复现的 JSON/Markdown entity reports。
18. 记录 corpus builds、artifact operations、audit runs、report exports、report archives、job runs 和 review decisions 的 audit logs。
19. 排队单个或批量 entity audit jobs，或 recurring entity audit schedules，并用可部署后台 worker 处理。
20. 本地缓存 entity search candidates，并提供 background corpus-build job，让大型 entity workflow 更快、更可检查。
21. 对 `/api/*` 提供可选本地 API keys，并支持 read、reviewer、admin 简单角色，方便部署到非可信本地 shell 之外。
22. 保留结论边界：signals 只提高复核优先级，不证明 misconduct。

### 验证

从仓库根目录运行本地验证：

```bash
scripts/verify_local.sh
```

设置 `GENGSCOPE_VERIFY_DOCKER_BUILD=1` 可以包含 Docker API 和 worker image build。GitHub Actions workflow `.github/workflows/gengscope-api-ci.yml` 会运行 offline tests、PostgreSQL integration loop、Docker image builds 和 deploy smoke test。

端到端验证 Docker stack：

```bash
scripts/verify_deploy.sh
```

Deploy smoke test 会在 Docker 数据库里写入 deterministic synthetic demo records，并验证 entity profile、artifact upload、numeric audit、review decision、report archive、job execution 和 recurring schedule creation 等部署路径。远程 artifact fetching 默认拒绝 private、loopback 和 link-local network targets；只有可信私有 mirror 才应设置 `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1`。可用 `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS` 为每个 host 增加访问间隔。

### Skill 与公开演示

可发布的 skill 位于 `skills/gengscope`。英文包名和触发名是 `gengscope`，中文展示名是 `耿同学.skill`。

它有意保持为一个轻量工作流入口：告诉 AI agent 如何调用本地 GengScope CLI/API，如何保留证据边界，以及如何在不作出“造假”判断的前提下总结 DOI 或实体级风险信号。

验证 skill package：

```bash
scripts/validate_skill.py skills/gengscope
```

使用合成记录和只读 demo key 运行轻量公开演示栈：

```bash
scripts/verify_demo_publish.sh
```

演示栈使用 `infra/docker/docker-compose.demo.yml`，写入 `10.5555/gengscope.demo.1` 合成样例，并验证 `demo-read` 只能读取 agent summary、不能写入 admin event。对公网开放时，写入和管理 key 必须保持私有，只发布用于浏览演示数据的只读 key。

静态公开演示：

```text
https://leimizzou.github.io/gengscope/demo/
```

运行本地合成案例演示，模拟 Codex 通过 `耿同学.skill` 调用本地引擎，并打印 numeric/image 审计信号：

```bash
python3 scripts/run_skill_case_demo.py --base-url http://127.0.0.1:8010
```

为 release page 构建 source bundle：

```bash
scripts/build_release_bundle.sh
```

运行带公开来源引用的真实案例 smoke test：

```bash
scripts/run_real_case_e2e.py --base-url http://127.0.0.1:8010
```

该脚本会导入一篇真实撤稿论文，把出版方通知记录为 official event，发现关联材料，并报告作者、机构和 affiliation breakdown。它只应用作端到端流程检查，不能当作独立的 misconduct 判定。

### 撤稿校准

当需要把盲提取的 GengScope 信号与官方撤稿原因对齐时，运行回顾性撤稿校准流程：

```bash
python3 scripts/run_retraction_calibration.py --base-url http://127.0.0.1:8010 --limit 5
```

详细说明见 [撤稿校准 / Retraction Calibration](docs/retraction-calibration.md)。

## English README

### Project Positioning

GengScope is an evidence-linked research integrity indexing platform for public papers involving Chinese research institutions.

GengScope is not designed to decide whether a paper is fraudulent. Its first goal is to build a searchable, traceable and correctable evidence index that connects papers, authors, institutions, laboratories, journals, public discussions, official actions, algorithmic review signals and evidence locations in one structured system.

The product direction is entity-driven: start from an author, institution, laboratory or local entity list; build the paper corpus for that entity; discover auditable materials such as PDFs, supplementary files and source data; then generate entity-level coverage, review queues and risk cards. DOI is a paper identifier, not the only entry point.

The Chinese display name for the skill is `耿同学.skill`; the English package, trigger name and CLI remain `gengscope`. Public communication should state clearly that this is an independent tool and does not represent any person or third-party official authorization.

### Product Scope

The first version focuses on life science, medicine, biomaterials and nanomedicine papers published since 2020 with participation from mainland Chinese institutions.

The platform answers five questions:

- What public risk signals are linked to a paper?
- Which papers, events and official statuses are linked to an author or institution?
- How much of an author, laboratory or institution corpus has auditable material?
- Can a public concern be traced to a specific figure, table, source data file or supplementary file?
- Can Codex, Claude Code or another agent query the local HTTP API and produce a reviewable audit summary?

### Core Boundary

Unless a journal, institution, regulator or author has publicly confirmed an issue, no paper should be labeled as "fraudulent". The platform only uses tiered status labels:

- `official_retraction`
- `official_correction`
- `official_expression_of_concern`
- `institution_investigation`
- `institution_conclusion`
- `public_discussion`
- `media_report`
- `algorithmic_signal`
- `manual_review_needed`

### Repository Layout

```text
apps/
  web/                 Web product frontend
services/
  api/                 Backend API
  worker/              Data collection, cleaning and audit jobs
packages/
  shared-schema/       JSON Schema / OpenAPI / TypeScript types
data/
  seeds/               Small committed seed data
  samples/             Small test samples; no large files
skills/
  gengscope/           Publishable Codex/GPT workflow skill
infra/
  docker/              Local development dependencies
  migrations/          Database migrations
scripts/
  ingest/              Command-line ingest scripts
docs/
  product-design.md
  technical-plan.md
  data-model.md
  roadmap.md
  skill-integration.md
  governance.md
```

### Documentation

- [Product Design](docs/product-design.md)
- [Entity-Driven System Design](docs/entity-driven-system.md)
- [Technical Plan](docs/technical-plan.md)
- [Data Model](docs/data-model.md)
- [API Contract](docs/api-contract.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Seed Cases](docs/seed-cases.md)
- [Roadmap](docs/roadmap.md)
- [Skill Integration](docs/skill-integration.md)
- [耿同学.skill Case Demo](docs/skill-case-demo.md)
- [Retraction Calibration](docs/retraction-calibration.md)
- [Governance](docs/governance.md)

### Run The Current MVP

The current runnable slice is a local HTTP API and same-port workbench, not an MCP server.

```bash
cd services/api
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest
gengscope serve --reload
```

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

Docker Compose from the repo root:

```bash
cp infra/docker/.env.example infra/docker/.env
docker compose -f infra/docker/docker-compose.yml up --build api worker
```

Docker exposes the API on `http://127.0.0.1:8010/` by default. Override with `GENGSCOPE_API_PORT=8000` if that port is free. The compose stack waits for PostgreSQL readiness, exposes `/health/ready` for database, migration and artifact-volume checks, runs a background worker, and stores uploaded artifacts in the `gengscope_artifacts` Docker volume.

The installed CLI is the local automation surface used by skills, CI and shell users:

```bash
gengscope health --base-url http://127.0.0.1:8010
gengscope search "Tsinghua University" --entity-type institution --base-url http://127.0.0.1:8010
gengscope import-doi "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
gengscope agent-summary "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
```

For daily use, open the Workbench first. Search an author or institution, choose the right candidate card, then either build the corpus immediately or queue "background corpus build" so the browser does not wait on OpenAlex and Crossref. Entity search results are persisted in `entity_search_cache`; once a query has been served by OpenAlex, repeated searches with the same query return from the local database and the response reports whether the result is `cached`, `stale` or freshly `refreshed`. Add `refresh=true` to `/api/entities/search` when you explicitly want a live OpenAlex refresh.

After building an institution corpus, use `GET /api/entities/institution/<id>/breakdown` or the Workbench breakdown action to group raw affiliations into likely schools, departments, institutes, laboratories and author clusters. This is deliberately heuristic and review-oriented; it helps decide where to expand audit coverage, not assign definitive administrative responsibility.

Back up and restore the local PostgreSQL database:

```bash
scripts/db_migrate.sh
scripts/db_backup.sh
GENGSCOPE_ALLOW_RESTORE=1 scripts/db_restore.sh backups/gengscope_YYYYMMDD_HHMMSS.sql
```

### First Engineering Target

Build an entity-driven local API MVP:

1. Search authors and institutions through OpenAlex.
2. Build a local corpus for an author or institution.
3. Build corpora in batches from a local entity list.
4. Import CSV/TSV/JSON entity manifests for local entity lists.
5. Create local group/lab entities from multiple resolved authors and institutions.
6. Track paper material status: metadata only, landing page, PDF, source data or fully auditable.
7. Generate entity-level coverage and risk profiles.
8. Add small-sample inference boundaries so high signal density raises review priority without implying full-corpus misconduct.
9. Queue auditable papers for review.
10. Discover PMC/landing-page and publisher-specific material links, then upload, register or HTTP-fetch source data, PDF and image artifacts into local storage.
11. Run numeric, image and metadata audit checks and write algorithmic signals with evidence pointers.
12. Detect whole-image, flip/rotation and local crop/patch image similarity in the first deterministic image analyzer.
13. Maintain deterministic, review-labeled golden regression cases for numeric, image and metadata analyzers.
14. Browse signals globally or by author/institution/group.
15. Review signals as confirmed, false positive, not actionable or needing more evidence.
16. Generate neutral paper and entity risk cards.
17. Export and archive entity reports as reproducible JSON/Markdown snapshots.
18. Record audit logs for corpus builds, artifact operations, audit runs, report exports, report archives, job runs and review decisions.
19. Queue single or batch entity audit jobs, or recurring entity audit schedules, and process them with a deployable background worker.
20. Cache entity search candidates locally and expose a background corpus-build job so large entity workflows feel fast and inspectable.
21. Protect `/api/*` with optional local API keys and simple read/reviewer/admin roles when deployed outside a trusted local shell.
22. Preserve the conclusion boundary: signals prioritize review, they do not prove misconduct.

### Verification

Run the local verification script from the repo root:

```bash
scripts/verify_local.sh
```

Set `GENGSCOPE_VERIFY_DOCKER_BUILD=1` to include Docker API and worker image builds. The GitHub Actions workflow in `.github/workflows/gengscope-api-ci.yml` runs offline tests, the PostgreSQL integration loop, Docker image builds and the deploy smoke test.

Run the deploy smoke test from the repo root when you want to verify the Docker stack end to end:

```bash
scripts/verify_deploy.sh
```

The deploy smoke test seeds deterministic synthetic demo records inside the Docker database and exercises the deployed API path for entity profile, artifact upload, numeric audit, review decision, report archive, job execution and recurring schedule creation. Remote artifact fetching refuses private, loopback and link-local network targets by default; set `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1` only for a trusted private mirror. Use `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS` to add a per-host delay for polite publisher downloads.

### Skill And Public Demo

The publishable skill is in `skills/gengscope`. Its English package and trigger name is `gengscope`; its Chinese display name is `耿同学.skill`.

It is intentionally a thin workflow entrypoint: it tells an AI agent how to call the local GengScope CLI/API, how to preserve evidence boundaries, and how to summarize DOI/entity risk signals without making misconduct claims.

Validate the skill package:

```bash
scripts/validate_skill.py skills/gengscope
```

Run a lightweight public-demo stack with synthetic records and a read-only demo key:

```bash
scripts/verify_demo_publish.sh
```

The demo stack uses `infra/docker/docker-compose.demo.yml`, seeds `10.5555/gengscope.demo.1`, and verifies that `demo-read` can read the agent summary but cannot write admin events. For public exposure, keep write/admin keys private and publish only a read key for browsing demo data.

Static public demo:

```text
https://leimizzou.github.io/gengscope/demo/
```

Run a local synthetic case demo that simulates Codex using `耿同学.skill` against the local engine and prints the numeric/image review signals:

```bash
python3 scripts/run_skill_case_demo.py --base-url http://127.0.0.1:8010
```

Build a source bundle for a release page:

```bash
scripts/build_release_bundle.sh
```

Run a public, source-attributed real-case smoke against a running local API:

```bash
scripts/run_real_case_e2e.py --base-url http://127.0.0.1:8010
```

This imports a real retracted article, records the publisher notice as an official event, discovers linked material records, and reports the connected authors, institution and affiliation breakdown. It should be used as an end-to-end workflow check, not as an independent misconduct determination.

### Retraction Calibration

Run the retrospective calibration workflow when you want to compare blind GengScope signals against official retraction reasons:

```bash
python3 scripts/run_retraction_calibration.py --base-url http://127.0.0.1:8010 --limit 5
```

See [Retraction Calibration](docs/retraction-calibration.md) for details.
