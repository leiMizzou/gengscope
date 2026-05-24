---
name: gengscope
description: Inspect a DOI, author, institution, or local GengScope report with evidence-linked research-integrity signals. Use when the user asks for 耿同学.skill, paper risk cards, entity corpus audits, source-data or image anomaly review, public event timelines, report archives, or neutral summaries that preserve the boundary between review signals and misconduct conclusions.
---

# GengScope / 耿同学.skill

Use this Claude Code project skill as the entrypoint for GengScope research-integrity review.

## Runtime

Prefer the local CLI against the Docker API:

```bash
gengscope doctor
gengscope health --base-url http://127.0.0.1:8010
gengscope agent-summary "<doi>" --base-url http://127.0.0.1:8010
gengscope risk-card "<doi>" --base-url http://127.0.0.1:8010
gengscope search "<author or institution>" --entity-type institution --base-url http://127.0.0.1:8010
```

If the API is not running, ask the user before starting it:

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build api worker
```

Use direct HTTP only when the CLI is unavailable. The default local API is `http://127.0.0.1:8010/`.

## Evidence Rules

1. Never call a paper, author, lab, or institution fraudulent unless an official source explicitly says so.
2. Separate official events, institution notices, public discussion, media reports, and algorithmic signals.
3. Cite source URLs or local evidence pointers for every material claim.
4. Include figure labels, table labels, panel labels, column names, filenames, and artifact IDs when present.
5. Treat PubPeer, media, and algorithmic findings as review signals unless independently confirmed by official sources.
6. If GengScope has no indexed signal, say no indexed signal was found. Do not say the work is clean.

## Output

Return a concise, neutral review summary:

- official status;
- public discussion or media reports;
- material coverage;
- algorithmic signals with evidence pointers;
- gaps or missing materials;
- conclusion boundary.

End with this boundary: indexed public statuses and algorithmic signals support human review priority; they do not by themselves prove misconduct.
