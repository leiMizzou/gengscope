from __future__ import annotations

from gengscope_api.services.import_paper import SourceClients, default_source_clients


def get_source_clients() -> SourceClients:
    return default_source_clients()
