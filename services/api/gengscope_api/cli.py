from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Any
from urllib.parse import quote

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8010"
DEFAULT_SERVE_PORT = 8010
DOCKER_START_COMMAND = "docker compose -f infra/docker/docker-compose.yml up -d --build api worker"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and operate a local GengScope API service.")
    _add_serve_options(parser)
    parser.set_defaults(command="serve")

    subparsers = parser.add_subparsers(dest="command")
    serve = subparsers.add_parser("serve", help="Run the local FastAPI workbench and API service.")
    _add_serve_options(serve)

    init = subparsers.add_parser("init", help="Create a local Docker .env from the example file.")
    init.add_argument("--repo-root", default=".", help="Repository root. Defaults to the current directory.")
    init.add_argument("--force", action="store_true", help="Overwrite an existing infra/docker/.env.")

    demo_seed = subparsers.add_parser("demo-seed", help="Seed deterministic synthetic demo data into the configured database.")
    demo_seed.add_argument("--database-url", help="Database URL. Defaults to DATABASE_URL or sqlite:///./gengscope_api.db.")

    api_parent = argparse.ArgumentParser(add_help=False)
    api_parent.add_argument("--base-url", default=os.getenv("GENGSCOPE_BASE_URL", DEFAULT_BASE_URL), help="GengScope API base URL.")
    api_parent.add_argument("--api-key", default=os.getenv("GENGSCOPE_API_KEY"), help="Optional API key.")
    api_parent.add_argument("--actor", default=os.getenv("GENGSCOPE_ACTOR"), help="Optional audit-log actor header.")

    subparsers.add_parser("health", parents=[api_parent], help="Check /health/ready on a running API.")
    doctor = subparsers.add_parser(
        "doctor",
        parents=[api_parent],
        help="Diagnose the local API connection and print the next startup command when needed.",
    )
    doctor.add_argument("--timeout", type=float, default=5.0, help="Health-check timeout in seconds.")

    search = subparsers.add_parser("search", parents=[api_parent], help="Search OpenAlex-backed author or institution candidates.")
    search.add_argument("query")
    search.add_argument("--entity-type", choices=["author", "institution"], default="author")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--refresh", action="store_true")

    corpus = subparsers.add_parser("build-corpus", parents=[api_parent], help="Build a local corpus for an author or institution.")
    corpus.add_argument("query")
    corpus.add_argument("--entity-type", choices=["author", "institution"], default="author")
    corpus.add_argument("--openalex-id")
    corpus.add_argument("--display-name")
    corpus.add_argument("--limit", type=int, default=25)
    corpus.add_argument("--year-from", type=int)
    corpus.add_argument("--year-to", type=int)

    import_doi = subparsers.add_parser("import-doi", parents=[api_parent], help="Import DOI metadata through OpenAlex/Crossref.")
    import_doi.add_argument("doi")
    import_doi.add_argument("--sources", default="openalex,crossref", help="Comma-separated metadata sources.")

    for name, help_text in [
        ("risk-card", "Fetch the neutral paper risk card for a DOI."),
        ("agent-summary", "Fetch the agent-oriented DOI summary for a DOI."),
    ]:
        command = subparsers.add_parser(name, parents=[api_parent], help=help_text)
        command.add_argument("doi")

    batch = subparsers.add_parser("batch-risk-cards", parents=[api_parent], help="Fetch risk cards for multiple DOIs.")
    batch.add_argument("dois", nargs="+")

    profile = subparsers.add_parser("entity-profile", parents=[api_parent], help="Fetch an entity coverage/risk profile.")
    profile.add_argument("entity_type", choices=["author", "institution", "group"])
    profile.add_argument("entity_id")

    report = subparsers.add_parser("report", parents=[api_parent], help="Export an entity report.")
    report.add_argument("entity_type", choices=["author", "institution", "group"])
    report.add_argument("entity_id")
    report.add_argument("--format", choices=["json", "markdown"], default="json")

    archive = subparsers.add_parser("archive-report", parents=[api_parent], help="Archive an entity report snapshot.")
    archive.add_argument("entity_type", choices=["author", "institution", "group"])
    archive.add_argument("entity_id")
    archive.add_argument("--formats", default="json,markdown", help="Comma-separated formats: json,markdown.")

    audit = subparsers.add_parser("audit-cycle", parents=[api_parent], help="Run the synchronous entity audit cycle.")
    audit.add_argument("entity_type", choices=["author", "institution", "group"])
    audit.add_argument("entity_id")
    audit.add_argument("--inspect-landing-pages", action="store_true")
    audit.add_argument("--no-discover-artifacts", action="store_true")
    audit.add_argument("--no-metadata-audit", action="store_true")
    audit.add_argument("--no-review-queue", action="store_true")
    audit.add_argument("--priority", type=int, default=6)
    return parser


def _add_serve_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to 127.0.0.1.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GENGSCOPE_API_PORT", str(DEFAULT_SERVE_PORT))),
        help="Bind port. Defaults to 8010.",
    )
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for local development.")
    parser.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL or sqlite:///./gengscope_api.db.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level.",
    )


def build_uvicorn_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    return {
        "app": "gengscope_api.main:app",
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "log_level": args.log_level,
    }


def run_init(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = os.path.abspath(args.repo_root)
    source = os.path.join(repo_root, "infra", "docker", ".env.example")
    target = os.path.join(repo_root, "infra", "docker", ".env")
    if not os.path.exists(source):
        raise FileNotFoundError(f"Missing example env file: {source}")
    if os.path.exists(target) and not args.force:
        return {
            "status": "exists",
            "path": target,
            "next": DOCKER_START_COMMAND,
        }
    shutil.copyfile(source, target)
    return {
        "status": "created",
        "path": target,
        "next": DOCKER_START_COMMAND,
    }


def run_demo_seed(args: argparse.Namespace) -> dict[str, Any]:
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    from gengscope_api.db.session import SessionLocal, init_db
    from gengscope_api.demo_seed import seed_demo_data

    init_db()
    with SessionLocal() as db:
        return seed_demo_data(db)


def api_headers(args: argparse.Namespace) -> dict[str, str]:
    headers: dict[str, str] = {}
    if getattr(args, "api_key", None):
        headers["X-API-Key"] = args.api_key
    if getattr(args, "actor", None):
        headers["X-GengScope-Actor"] = args.actor
    return headers


def api_url(args: argparse.Namespace, path: str) -> str:
    return f"{args.base_url.rstrip('/')}{path}"


def api_request(args: argparse.Namespace, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None):
    response = httpx.request(method, api_url(args, path), params=params, json=json_body, headers=api_headers(args), timeout=60.0)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/"):
        return response.text
    return response.json()


def run_doctor(args: argparse.Namespace) -> dict[str, Any]:
    ready_url = api_url(args, "/health/ready")
    report: dict[str, Any] = {
        "status": "unknown",
        "base_url": args.base_url.rstrip("/"),
        "ready_url": ready_url,
        "api_reachable": False,
        "ready": False,
        "detail": None,
        "suggested_start_command": DOCKER_START_COMMAND,
    }
    try:
        response = httpx.get(ready_url, headers=api_headers(args), timeout=args.timeout)
    except httpx.HTTPError as exc:
        report["status"] = "unreachable"
        report["detail"] = str(exc)
        return report

    report["api_reachable"] = True
    report["http_status"] = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = {"body": response.text[:500]}
    report["detail"] = payload
    if 200 <= response.status_code < 300:
        report["status"] = "ready"
        report["ready"] = True
    else:
        report["status"] = "not_ready"
    return report


def run_api_command(args: argparse.Namespace):
    if args.command == "health":
        return api_request(args, "GET", "/health/ready")
    if args.command == "doctor":
        return run_doctor(args)
    if args.command == "search":
        return api_request(
            args,
            "GET",
            "/api/entities/search",
            params={"entity_type": args.entity_type, "query": args.query, "limit": args.limit, "refresh": str(args.refresh).lower()},
        )
    if args.command == "build-corpus":
        return api_request(
            args,
            "POST",
            "/api/entities/corpus",
            json_body={
                "entity_type": args.entity_type,
                "query": args.query,
                "openalex_id": args.openalex_id,
                "display_name": args.display_name or args.query,
                "limit": args.limit,
                "year_from": args.year_from,
                "year_to": args.year_to,
            },
        )
    if args.command == "import-doi":
        return api_request(args, "POST", "/api/admin/import/doi", json_body={"doi": args.doi, "sources": _csv_list(args.sources)})
    if args.command == "risk-card":
        return api_request(args, "GET", f"/api/papers/{quote(args.doi, safe='')}/risk-card")
    if args.command == "agent-summary":
        return api_request(args, "GET", f"/api/agent/doi/{quote(args.doi, safe='')}")
    if args.command == "batch-risk-cards":
        return api_request(args, "POST", "/api/agent/batch-risk-cards", json_body={"dois": args.dois})
    if args.command == "entity-profile":
        return api_request(args, "GET", f"/api/entities/{args.entity_type}/{args.entity_id}/profile")
    if args.command == "report":
        return api_request(args, "GET", "/api/reports/entity", params={"entity_type": args.entity_type, "entity_id": args.entity_id, "format": args.format})
    if args.command == "archive-report":
        return api_request(args, "POST", "/api/reports/entity/archive", json_body={"entity_type": args.entity_type, "entity_id": args.entity_id, "formats": _csv_list(args.formats)})
    if args.command == "audit-cycle":
        return api_request(
            args,
            "POST",
            "/api/audits/entity-cycle",
            json_body={
                "entity_type": args.entity_type,
                "entity_id": args.entity_id,
                "discover_artifacts": not args.no_discover_artifacts,
                "inspect_landing_pages": args.inspect_landing_pages,
                "queue_review_tasks": not args.no_review_queue,
                "run_metadata_audit": not args.no_metadata_audit,
                "priority": args.priority,
            },
        )
    raise ValueError(f"Unsupported command: {args.command}")


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def print_payload(payload: Any) -> None:
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {None, "serve"}:
            kwargs = build_uvicorn_kwargs(args)

            import uvicorn

            uvicorn.run(**kwargs)
            return 0
        if args.command == "init":
            print_payload(run_init(args))
            return 0
        if args.command == "demo-seed":
            print_payload(run_demo_seed(args))
            return 0
        print_payload(run_api_command(args))
        return 0
    except Exception as exc:
        print(f"gengscope: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
