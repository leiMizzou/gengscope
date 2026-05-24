from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gengscope_api.api.routes import admin, agent, artifacts, audit_log, audits, entities, health, jobs, papers, reports, review, signals, ui
from gengscope_api.config import get_settings
from gengscope_api.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app(init_tables: bool = True) -> FastAPI:
    app = FastAPI(title="GengScope API", version="0.1.0", lifespan=lifespan if init_tables else None)

    @app.middleware("http")
    async def api_key_auth(request: Request, call_next):
        settings = get_settings()
        if settings.api_keys and request.url.path.startswith("/api/"):
            supplied_key = _request_api_key(request)
            role = _api_key_role(settings.api_key_roles or {}, supplied_key)
            if not role:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Valid API key required. Send X-API-Key or Authorization: Bearer <key>."},
                )
            if not _role_allowed(role, request):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"API key role '{role}' is not allowed to call this endpoint."},
                )
            request.state.gengscope_role = role
        return await call_next(request)

    app.include_router(ui.router)
    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(papers.router)
    app.include_router(entities.router)
    app.include_router(artifacts.router)
    app.include_router(audits.router)
    app.include_router(review.router)
    app.include_router(signals.router)
    app.include_router(reports.router)
    app.include_router(audit_log.router)
    app.include_router(jobs.router)
    app.include_router(agent.router)
    return app


app = create_app()


def _request_api_key(request: Request) -> str | None:
    explicit = request.headers.get("x-api-key") or request.headers.get("x-gengscope-api-key")
    if explicit:
        return explicit.strip()
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _api_key_role(api_key_roles: dict[str, str], supplied_key: str | None) -> str | None:
    if not supplied_key:
        return None
    for key, role in api_key_roles.items():
        if secrets.compare_digest(supplied_key, key):
            return role
    return None


def _role_allowed(role: str, request: Request) -> bool:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    if role == "admin":
        return True
    path = request.url.path
    if role == "reviewer":
        return not (path.startswith("/api/admin/") or path == "/api/reports/archive/prune")
    return False
