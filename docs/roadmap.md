# Roadmap

## Milestone 0: Foundation

Deliverables:

- Product and technical docs.
- Repository layout.
- Database schema.
- Seed case list.
- Local docker-compose plan.

Acceptance criteria:

- A developer can understand product boundaries in 15 minutes.
- The schema supports paper, author, institution, event, artifact and signal objects.
- The project explicitly avoids unverified fraud labeling.

## Milestone 1: Entity Metadata MVP

Deliverables:

- FastAPI service.
- PostgreSQL migrations.
- DOI normalization for paper identity.
- OpenAlex author/institution search.
- Entity corpus import from OpenAlex works.
- Crossref enrichment where DOI is available.
- Material status tracking.
- Entity profile endpoint.
- Review queue creation for auditable papers.
- Manual event entry.
- Paper detail API.
- Risk card API.
- Same-port local workbench.

Acceptance criteria:

- Given an author or institution, API can build a local paper corpus.
- Given an entity corpus, API returns paper count, auditable coverage and review priority.
- Given a manually entered official event, risk card reflects it.
- Every imported field has source provenance.

## Milestone 2: Artifact Discovery MVP

Deliverables:

- Source artifact registry.
- OA PDF discovery.
- Supplementary/source data URL discovery.
- Manual artifact upload.
- Artifact list on paper detail.

Acceptance criteria:

- System can show which papers are metadata-only, landing-page-only, PDF-available or source-data-available.
- System can queue only genuinely auditable papers.
- Artifact records include URL, checksum, content type and capture time.

## Milestone 3: Public Event Import

Deliverables:

- Crossref Retraction Watch import.
- Crossmark enrichment where available.
- PubPeer link tracker.
- Manual source review workflow.

Acceptance criteria:

- Retractions and corrections can be imported in batch.
- PubPeer is represented as a link/signal, not copied comment content.
- Event status clearly separates official and non-official sources.

## Milestone 4: Source Data and Numeric Audit

Deliverables:

- Artifact registry.
- XLSX/CSV parser.
- Source data viewer.
- Numeric anomaly analyzers.
- Review tasks for algorithmic signals.

Acceptance criteria:

- System can attach source data to a paper.
- Numeric analyzer can produce evidence pointers.
- Signals remain hidden from public default view until reviewed or clearly marked.

## Milestone 5: Image Audit

Deliverables:

- Figure extraction pipeline.
- Panel splitting workflow.
- Perceptual hash duplicate detector.
- Local patch similarity detector.
- Side-by-side evidence viewer.

Acceptance criteria:

- System can flag visually similar panels.
- Every image signal includes comparison artifacts and coordinates.
- Reviewer can mark false positive or promote to public signal.

## Milestone 6: Local API and CI Layer

Deliverables:

- Local HTTP agent endpoints.
- Entity manifest import and batch entity audit endpoints.
- Persistent entity search cache and background corpus-build jobs.
- Docker Compose deployment smoke script.
- CI workflow that runs tests, migration checks and deploy smoke.
- Codex skill draft.
- Claude Code command examples.
- MCP server is out of the core roadmap; if ever needed, keep it as a thin external adapter over the HTTP API.

Acceptance criteria:

- Agent or CI script can answer: “这个作者/机构的本地审计画像、可审计覆盖率和待复核信号是什么？”
- Workbench repeated entity searches return from local cache, and large corpus builds can run through the worker queue.
- Agent output includes links and conclusion boundaries.
- Agent never labels unconfirmed claims as fraud.

## Milestone 7: Production Hardening

Deliverables:

- Auth and roles.
- Audit logs.
- Rate limits.
- Backups.
- Admin moderation.
- Legal review workflow.
- Data correction request mechanism.

Acceptance criteria:

- Users can submit correction requests.
- Admin decisions are logged.
- Sensitive or disputed events can be hidden, corrected or superseded.
