# GengScope

面向中国研究机构公开论文的科研完整性索引平台。

GengScope 的第一目标不是判定论文造假，而是建立一个可检索、可追溯、可纠错的基础索引：把论文、作者、机构、实验室、期刊、公开质疑、官方处理、算法异常信号和证据位置放在同一个结构化系统里。

当前产品方向是 entity-driven：以作者、机构、实验室或本地名单为入口，先建立该实体的论文全库，再寻找 PDF、supplementary、source data 等可审计材料，最后生成实体级覆盖率、审计队列和风险画像。DOI 是论文标识，不是唯一入口。

中文产品名可使用“耿同学科研索引”或“耿同学论文索引”。对外发布时应明确本项目是独立工具，不代表任何个人或第三方官方授权。

## Product Scope

第一版聚焦 2020 年以来中国大陆机构参与发表的生命科学、医学、生物材料、纳米医学方向论文。

平台回答五类问题：

- 某篇论文有哪些公开风险信号？
- 某个作者或机构涉及哪些论文、事件和官方状态？
- 某个作者、实验室或机构的论文全库中，有多少论文找到了可审计材料？
- 某个公开质疑是否能定位到具体图、表、source data 或 supplementary 文件？
- Codex / Claude Code 等 agent 能否通过本地 HTTP API 查询并生成可复核的审计摘要？

## Repository Layout

```text
apps/
  web/                 Web 产品前端，后续建议 Next.js
services/
  api/                 后端 API，后续建议 FastAPI
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

## Core Principle

除非期刊、机构、监管部门或作者公开确认，不得把任何论文标记为“造假”。平台只使用分级状态：

- official_retraction
- official_correction
- official_expression_of_concern
- institution_investigation
- institution_conclusion
- public_discussion
- media_report
- algorithmic_signal
- manual_review_needed

## Planning Docs

- [Product Design](docs/product-design.md)
- [Entity-Driven System Design](docs/entity-driven-system.md)
- [Technical Plan](docs/technical-plan.md)
- [Data Model](docs/data-model.md)
- [API Contract](docs/api-contract.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Seed Cases](docs/seed-cases.md)
- [Roadmap](docs/roadmap.md)
- [Skill Integration](docs/skill-integration.md)
- [Governance](docs/governance.md)

## Run The Current MVP

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

Docker exposes the API on `http://127.0.0.1:8010/` by default. Override with `GENGSCOPE_API_PORT=8000` if that port is free.
The compose stack waits for PostgreSQL readiness, exposes `/health/ready` for database, migration and artifact-volume checks, runs a background worker, and stores uploaded artifacts in the `gengscope_artifacts` Docker volume.

The installed CLI is the local automation surface used by skills, CI and shell users:

```bash
gengscope health --base-url http://127.0.0.1:8010
gengscope search "Tsinghua University" --entity-type institution --base-url http://127.0.0.1:8010
gengscope import-doi "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
gengscope agent-summary "10.1038/s41586-024-08248-5" --base-url http://127.0.0.1:8010
```

For daily use, open the Workbench first. Search an author or institution, choose the right candidate card, then either build the corpus immediately or queue “后台建库” so the browser does not wait on OpenAlex and Crossref. Entity search results are persisted in `entity_search_cache`; repeated searches return from the local database and show whether the result is cached, stale or freshly refreshed. Add `refresh=true` to `/api/entities/search` when you explicitly want a live OpenAlex refresh.

After building an institution corpus, use `GET /api/entities/institution/<id>/breakdown` or the Workbench “结构拆分” button to group raw affiliations into likely schools, departments, institutes, laboratories and author clusters. This is deliberately heuristic and review-oriented; it helps decide where to expand audit coverage, not assign definitive administrative responsibility.

Back up and restore the local PostgreSQL database:

```bash
scripts/db_migrate.sh
scripts/db_backup.sh
GENGSCOPE_ALLOW_RESTORE=1 scripts/db_restore.sh backups/gengscope_YYYYMMDD_HHMMSS.sql
```

## First Engineering Target

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

## Verification

Run the local verification script from the repo root:

```bash
scripts/verify_local.sh
```

Set `GENGSCOPE_VERIFY_DOCKER_BUILD=1` to include Docker API and worker image builds. The GitHub Actions workflow in `.github/workflows/gengscope-api-ci.yml` runs offline tests, the PostgreSQL integration loop, Docker image builds and the deploy smoke test.

Run the deploy smoke test from the repo root when you want to verify the Docker stack end to end:

```bash
scripts/verify_deploy.sh
```

The deploy smoke test now seeds deterministic synthetic demo records inside the Docker database and exercises the deployed API path for entity profile, artifact upload, numeric audit, review decision, report archive, job execution and recurring schedule creation. Remote artifact fetching refuses private, loopback and link-local network targets by default; set `ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS=1` only for a trusted private mirror. Use `ARTIFACT_FETCH_MIN_INTERVAL_SECONDS` to add a per-host delay for polite publisher downloads.

## Skill And Public Demo

The publishable skill is in `skills/gengscope`. It is intentionally a thin workflow entrypoint: it tells an AI agent how to call the local GengScope CLI/API, how to preserve evidence boundaries, and how to summarize DOI/entity risk signals without making misconduct claims.

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

Build a source bundle for a release page:

```bash
scripts/build_release_bundle.sh
```

Run a public, source-attributed real-case smoke against a running local API:

```bash
scripts/run_real_case_e2e.py --base-url http://127.0.0.1:8010
```

This imports a real retracted article, records the publisher notice as an official event, discovers linked material records, and reports the connected authors, institution and affiliation breakdown. It should be used as an end-to-end workflow check, not as an independent misconduct determination.
