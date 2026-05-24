from __future__ import annotations

import os

from gengscope_api import cli
from gengscope_api.cli import build_parser, build_uvicorn_kwargs
from gengscope_api.worker import build_parser as build_worker_parser


def test_cli_builds_local_api_server_command(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    args = build_parser().parse_args(
        [
            "--host",
            "0.0.0.0",
            "--port",
            "8010",
            "--reload",
            "--database-url",
            "sqlite:///./local.db",
            "--log-level",
            "debug",
        ]
    )

    kwargs = build_uvicorn_kwargs(args)

    assert kwargs == {
        "app": "gengscope_api.main:app",
        "host": "0.0.0.0",
        "port": 8010,
        "reload": True,
        "log_level": "debug",
    }
    assert os.environ["DATABASE_URL"] == "sqlite:///./local.db"


def test_worker_cli_parses_poll_options() -> None:
    args = build_worker_parser().parse_args(
        [
            "--database-url",
            "sqlite:///./worker.db",
            "--poll-interval",
            "0.1",
            "--recover-stale-after",
            "60",
            "--disable-schedules",
            "--once",
        ]
    )

    assert args.database_url == "sqlite:///./worker.db"
    assert args.poll_interval == 0.1
    assert args.recover_stale_after == 60
    assert args.disable_schedules is True
    assert args.once is True


class _Response:
    headers = {"content-type": "application/json"}

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_cli_agent_summary_calls_local_http_api(monkeypatch) -> None:
    calls = []

    def fake_request(method, url, *, params=None, json=None, headers=None, timeout=None):
        calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers, "timeout": timeout})
        return _Response({"paper": {"doi": "10.5555/example"}, "conclusion_boundary": "不能据此直接认定论文造假。"})

    monkeypatch.setattr(cli.httpx, "request", fake_request)
    args = build_parser().parse_args(
        [
            "agent-summary",
            "10.5555/example",
            "--base-url",
            "http://127.0.0.1:8010",
            "--api-key",
            "local-key",
            "--actor",
            "cli-test",
        ]
    )

    result = cli.run_api_command(args)

    assert result["paper"]["doi"] == "10.5555/example"
    assert calls == [
        {
            "method": "GET",
            "url": "http://127.0.0.1:8010/api/agent/doi/10.5555%2Fexample",
            "params": None,
            "json": None,
            "headers": {"X-API-Key": "local-key", "X-GengScope-Actor": "cli-test"},
            "timeout": 60.0,
        }
    ]


def test_cli_build_corpus_payload_uses_entity_options(monkeypatch) -> None:
    calls = []

    def fake_request(method, url, *, params=None, json=None, headers=None, timeout=None):
        calls.append({"method": method, "url": url, "json": json})
        return _Response({"entity": {"entity_type": "institution"}, "imported_count": 0})

    monkeypatch.setattr(cli.httpx, "request", fake_request)
    args = build_parser().parse_args(
        [
            "build-corpus",
            "Tsinghua University",
            "--entity-type",
            "institution",
            "--limit",
            "50",
            "--year-from",
            "2020",
            "--year-to",
            "2026",
        ]
    )

    result = cli.run_api_command(args)

    assert result["entity"]["entity_type"] == "institution"
    assert calls[0]["url"] == "http://127.0.0.1:8000/api/entities/corpus"
    assert calls[0]["json"] == {
        "entity_type": "institution",
        "query": "Tsinghua University",
        "openalex_id": None,
        "display_name": "Tsinghua University",
        "limit": 50,
        "year_from": 2020,
        "year_to": 2026,
    }


def test_cli_init_reports_existing_env(tmp_path) -> None:
    env_dir = tmp_path / "infra" / "docker"
    env_dir.mkdir(parents=True)
    (env_dir / ".env.example").write_text("GENGSCOPE_API_PORT=8010\n", encoding="utf-8")
    (env_dir / ".env").write_text("GENGSCOPE_API_PORT=9000\n", encoding="utf-8")
    args = build_parser().parse_args(["init", "--repo-root", str(tmp_path)])

    result = cli.run_init(args)

    assert result["status"] == "exists"
    assert (env_dir / ".env").read_text(encoding="utf-8") == "GENGSCOPE_API_PORT=9000\n"
