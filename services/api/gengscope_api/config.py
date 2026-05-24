from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./gengscope_api.db"
    openalex_email: str | None = None
    http_timeout_seconds: float = 20.0
    artifact_storage_dir: str = "data/artifacts"
    artifact_fetch_max_bytes: int = 50 * 1024 * 1024
    artifact_fetch_allow_private_networks: bool = False
    artifact_fetch_min_interval_seconds: float = 0.0
    entity_search_cache_ttl_seconds: int = 7 * 24 * 60 * 60
    api_keys: tuple[str, ...] = ()
    api_key_roles: dict[str, str] | None = None


@lru_cache
def get_settings() -> Settings:
    api_keys = _api_keys()
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./gengscope_api.db"),
        openalex_email=os.getenv("OPENALEX_EMAIL"),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
        artifact_storage_dir=os.getenv("ARTIFACT_STORAGE_DIR", "data/artifacts"),
        artifact_fetch_max_bytes=int(os.getenv("ARTIFACT_FETCH_MAX_BYTES", str(50 * 1024 * 1024))),
        artifact_fetch_allow_private_networks=_bool_env("ARTIFACT_FETCH_ALLOW_PRIVATE_NETWORKS", default=False),
        artifact_fetch_min_interval_seconds=float(os.getenv("ARTIFACT_FETCH_MIN_INTERVAL_SECONDS", "0")),
        entity_search_cache_ttl_seconds=int(os.getenv("ENTITY_SEARCH_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60))),
        api_keys=api_keys,
        api_key_roles=_api_key_roles(api_keys),
    )


def _api_keys() -> tuple[str, ...]:
    values = []
    single_key = os.getenv("GENGSCOPE_API_KEY")
    if single_key:
        values.append(single_key)
    keys = os.getenv("GENGSCOPE_API_KEYS")
    if keys:
        values.extend(keys.split(","))
    return tuple(key.strip() for key in values if key.strip())


def _api_key_roles(api_keys: tuple[str, ...]) -> dict[str, str]:
    roles = {key: "admin" for key in api_keys}
    configured = os.getenv("GENGSCOPE_API_KEY_ROLES")
    if not configured:
        return roles
    allowed = {"read", "reviewer", "admin"}
    for item in configured.split(","):
        if ":" not in item:
            continue
        key, role = item.split(":", 1)
        cleaned_key = key.strip()
        cleaned_role = role.strip().lower()
        if cleaned_key and cleaned_role in allowed:
            roles[cleaned_key] = cleaned_role
    return roles


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
