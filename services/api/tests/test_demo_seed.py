from __future__ import annotations

from gengscope_api.demo_seed import seed_demo_data
from gengscope_api.services.entities import entity_profile


def test_demo_seed_is_idempotent_and_profile_ready(db_session) -> None:
    first = seed_demo_data(db_session)
    second = seed_demo_data(db_session)

    assert first["author"]["id"] == second["author"]["id"]
    assert first["institution"]["id"] == second["institution"]["id"]
    assert first["primary_doi"] == "10.5555/gengscope.demo.1"
    assert len(second["papers"]) == 2

    profile = entity_profile(db_session, "author", second["author"]["id"])
    assert profile["paper_count"] == 2
    assert profile["auditable_paper_count"] == 1
    assert "不能直接认定" in profile["conclusion_boundary"]
