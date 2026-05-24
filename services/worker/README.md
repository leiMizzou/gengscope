# GengScope Worker

The deployable worker is currently the `gengscope-worker` console script from `services/api`.

It uses the shared PostgreSQL database as a durable queue:

```text
api POST /api/jobs/entity-cycle
  -> job_runs row with status=queued
worker gengscope-worker
  -> polls job_runs
  -> runs the entity audit cycle
  -> stores result_json or error_message
```

Run with Docker Compose from the repo root:

```bash
docker compose -f infra/docker/docker-compose.yml up --build api worker
```

Run one queued job locally:

```bash
cd services/api
gengscope-worker --once
```

Run a long-lived local worker with stale job recovery:

```bash
gengscope-worker --poll-interval 5 --recover-stale-after 3600
```

Worker rules:

- Jobs must be idempotent where possible.
- Workers claim queued jobs through database row locks so multiple workers can run against PostgreSQL without deliberately taking the same queued row.
- Every result remains a workflow record, not a misconduct conclusion.
- Failed jobs keep `error_message`, `attempts`, payload and timestamps.
- Stale recovery only fixes jobs left in `running`; it does not roll back partial side effects from a workflow that had already written records.
- Retry failed jobs through `POST /api/jobs/{job_id}/retry`.

Initial job type:

```text
entity_audit_cycle
```
