# Skill Integration

## 1. Goal

Provide a Codex / Claude Code skill that lets an agent query GengScope and produce neutral, evidence-linked paper integrity summaries.

The skill should not independently judge misconduct. It should retrieve structured data, cite sources and preserve status boundaries.

## 2. Skill Name

English package and trigger name:

```text
gengscope
```

Chinese display name:

```text
耿同学.skill
```

Use `耿同学.skill` in public-facing Chinese posts, demos, marketplace copy and screenshots. Keep `gengscope` for the folder name, install name, CLI/API examples and agent trigger token, because skill package names should stay ASCII and stable.

The publishable skill package lives at:

```text
skills/gengscope
```

Avoid:

```text
paper-fraud-detector
academic-fraud-blacklist
```

## 3. Agent Capabilities

The skill should support:

- DOI risk lookup.
- Batch DOI risk lookup.
- Author profile lookup.
- Institution profile lookup.
- Event timeline summary.
- Source data audit request.
- Numeric anomaly report generation.
- Image similarity report generation.

## 4. Tool API Contract

### lookup_paper

Input:

```json
{
  "doi": "10.1038/example"
}
```

Output:

```json
{
  "paper": {
    "doi": "10.1038/example",
    "title": "...",
    "journal": "...",
    "publication_year": 2024
  },
  "risk_card": {
    "official_status": "none",
    "institution_status": "investigation",
    "public_discussion_count": 1,
    "algorithmic_signal_count": 0,
    "summary": "存在机构调查和公开讨论，尚未发现官方结论。"
  },
  "events": [],
  "evidence": []
}
```

### lookup_institution

Input:

```json
{
  "query": "Tongji University",
  "year_from": 2020,
  "year_to": 2026
}
```

Output:

```json
{
  "institution": {
    "id": "...",
    "display_name": "Tongji University",
    "ror_id": "..."
  },
  "metrics": {
    "paper_count": 0,
    "official_event_count": 0,
    "public_discussion_count": 0,
    "algorithmic_signal_count": 0,
    "normalized_official_events_per_1000_papers": 0
  },
  "recent_events": []
}
```

### batch_risk_cards

Input:

```json
{
  "dois": ["10.xxxx/a", "10.xxxx/b"]
}
```

Output:

```json
{
  "items": [
    {
      "doi": "10.xxxx/a",
      "title": "...",
      "official_status": "none",
      "highest_signal_level": "public_discussion",
      "summary": "存在公开讨论，未发现官方结论。"
    }
  ]
}
```

## 5. Agent Response Rules

The skill instructions must include:

```text
1. Do not call a paper fraudulent unless an official source states that.
2. Separate official events, public discussion and algorithmic signals.
3. Cite source URLs for every material claim.
4. When evidence points to figures or source data, include figure labels and file names.
5. If the source is media or PubPeer, say "公开报道/公开讨论称".
6. If data is unavailable, say so plainly.
7. Avoid author or institution moral judgments.
```

## 6. Example Agent Output

```text
这篇论文目前有 2 类公开信号：

1. 机构调查：某大学于 2026-05-12 发布说明，称已成立调查组。
2. 公开讨论：PubPeer 页面存在关于 Figure 4c 数据模式的讨论。

未检索到期刊撤稿、官方更正或最终调查结论。

结论边界：以上只能说明存在公开质疑和调查状态，不能据此认定论文造假。
```

## 7. HTTP API and CI Adapter

The core integration surface is the local CLI plus HTTP API. CI jobs, shell scripts, notebooks and agents should call these commands/endpoints directly; an MCP server is intentionally outside the core product and should only be a thin external adapter if a separate integration later requires it.

Preferred CLI calls:

```text
gengscope health
gengscope search
gengscope build-corpus
gengscope import-doi
gengscope risk-card
gengscope agent-summary
gengscope entity-profile
gengscope audit-cycle
gengscope report
gengscope archive-report
```

Core API calls:

```text
GET  /api/entities/search
POST /api/entities/corpus
POST /api/entities/corpus/import
POST /api/audits/entity-cycle
POST /api/jobs/entity-cycle
POST /api/jobs/schedules/entity-cycle
GET  /api/reports/entity
POST /api/reports/entity/archive
GET  /api/reports/archive
```

CI should treat outputs as review-priority evidence and provenance snapshots:

```text
entity corpus JSON
artifact discovery/fetch results
algorithmic_signal records
review task queue
archived report snapshots
```
