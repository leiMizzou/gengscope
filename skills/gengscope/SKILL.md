---
name: gengscope
description: Use when investigating a DOI, paper, author, institution, lab/group, or local corpus for research-integrity risk signals with the GengScope local API or CLI, including when the user refers to the Chinese display name 耿同学.skill. Triggers include paper risk cards, author/institution corpus audits, source-data or image anomaly review, public event timelines, report archives, and requests to preserve the boundary that signals support human review rather than proving misconduct.
---

# GengScope / 耿同学.skill

Use GengScope as an evidence-linked investigation workflow, not as a misconduct classifier.

Public naming: keep the installable skill package, trigger name, CLI, and API namespace as `gengscope`. Use `耿同学.skill` as the Chinese display name in user-facing posts, marketplace copy, demos, and prompts.

## Core Rules

1. Never call a paper, author, lab, or institution fraudulent unless an official source explicitly says so.
2. Separate official events, institution notices, public discussion, media reports, and algorithmic signals.
3. Cite source URLs or local evidence pointers for every material claim.
4. Include figure labels, table labels, panel labels, column names, filenames, and artifact IDs when present.
5. Treat PubPeer, media, and algorithmic findings as review signals unless independently confirmed by official sources.
6. If GengScope has no indexed signal, say no indexed signal was found. Do not say the work is clean.
7. Avoid moral judgments about authors, labs, or institutions.

## Runtime Selection

Prefer the local CLI when available:

```bash
gengscope doctor
gengscope health --base-url http://127.0.0.1:8010
gengscope agent-summary "10.xxxx/example" --base-url http://127.0.0.1:8010
gengscope risk-card "10.xxxx/example" --base-url http://127.0.0.1:8010
gengscope search "Tsinghua University" --entity-type institution --base-url http://127.0.0.1:8010
```

Use direct HTTP only when the CLI is unavailable. If neither is running, tell the user to start the local engine:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build api worker
```

Then use `http://127.0.0.1:8010/`.

## DOI Workflow

1. Fetch `gengscope agent-summary <doi>` or `GET /api/agent/doi/{doi}`.
2. Report official status first: retraction, correction, expression of concern, institution conclusion, or none.
3. Report public discussion and media second.
4. Report algorithmic signals third, with evidence pointers.
5. End with the conclusion boundary.

If the DOI is not indexed, offer to import metadata with:

```bash
gengscope import-doi "10.xxxx/example" --base-url http://127.0.0.1:8010
```

## Entity Workflow

1. Search candidates with `gengscope search`.
2. Ask the user to choose when multiple plausible entities exist.
3. Build or use the local corpus with `gengscope build-corpus`.
4. Run or inspect the entity audit cycle with `gengscope audit-cycle`.
5. Fetch the entity report with `gengscope report`.
6. Use coverage and sample-inference boundaries when discussing signal rates.

Do not rank institutions by raw signal counts. Always include denominators and material coverage.

## Artifact And Signal Workflow

For source-data or image questions, use the API/workbench to upload, discover, fetch, or list artifacts, then run numeric or image audits. Summaries must distinguish:

- Whole-image similarity.
- Local patch/crop similarity.
- Shift-correlation image similarity.
- Numeric duplicate runs.
- Last-digit distribution anomalies.
- Fixed ratio/offset numeric column relationships.
- Metadata clustering/event-density signals.

Treat each as a review cue. Do not claim fabrication without external official confirmation.

## Output Shape

Use concise, neutral language:

```text
这篇论文目前索引到的状态是：

- 官方状态：未发现撤稿/更正/关注表达。
- 公开讨论：有 1 条公开讨论，来源为 ...
- 算法信号：有 2 条待复核信号，涉及 Figure 3b 和 source-data.csv 的 tumor_a 列。

结论边界：以上是公开状态和算法信号，用于人工复核优先级排序，不能据此直接认定论文造假。
```

For endpoint details, read `references/api.md` only when you need exact CLI/API calls.
