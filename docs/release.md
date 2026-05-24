# GengScope Release Checklist

Use this before publishing the repository, skill package, or public demo.

## 1. Local Open-Source Engine

Required artifacts:

- `services/api` installable Python package.
- `gengscope` CLI entrypoint.
- Docker Compose API, worker and PostgreSQL stack.
- Workbench at `/`.
- Verification scripts.

Commands:

```bash
cd services/api
python -m pip install -e ".[postgres]" pytest
gengscope serve --reload
```

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build api worker
scripts/verify_deploy.sh
```

## 2. Skill Package

Publish `skills/gengscope`.

Validate:

```bash
scripts/validate_skill.py skills/gengscope
```

The skill must keep the conclusion boundary: GengScope produces public statuses, material coverage, and algorithmic review signals, not misconduct findings.

## 3. Public Demo

The demo should use synthetic data and a read-only API key.

Commands:

```bash
scripts/verify_demo_publish.sh
```

Expected properties:

- `/health/ready` passes.
- `demo-read` can call `GET /api/agent/doi/10.5555%2Fgengscope.demo.1`.
- `demo-read` cannot call write/admin endpoints.
- The workbench is reachable at the configured API port.

Static public demo URL:

```text
https://leimizzou.github.io/gengscope/demo/
```

## 4. Release Gates

Run:

```bash
scripts/verify_local.sh
GENGSCOPE_VERIFY_DOCKER_BUILD=1 scripts/verify_local.sh
scripts/verify_deploy.sh
scripts/verify_demo_publish.sh
```

If a real-case smoke is needed:

```bash
scripts/run_real_case_e2e.py --base-url http://127.0.0.1:8010
```

Do not advertise real-case output as proof of misconduct. It is a workflow and source-attribution check.

## 5. Source Bundle

Build a source bundle for upload to a release page:

```bash
scripts/build_release_bundle.sh
```

The bundle excludes local databases, artifact payloads, virtual environments, caches and backups.
