from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from gengscope_api.db.models import Authorship, SourceRecord
from gengscope_api.services.doi import normalize_doi
from gengscope_api.services.import_paper import import_doi

pytestmark = pytest.mark.live


def test_live_openalex_crossref_import_smoke(db_session) -> None:
    if os.getenv("GENGSCOPE_RUN_LIVE") != "1":
        pytest.skip("set GENGSCOPE_RUN_LIVE=1 to hit external metadata APIs")

    doi = os.getenv("GENGSCOPE_LIVE_DOI", "10.1038/s41586-024-08248-5")

    paper = import_doi(db_session, doi)
    authorships = db_session.scalars(select(Authorship).where(Authorship.paper_id == paper.id)).all()
    records = db_session.scalars(select(SourceRecord).where(SourceRecord.entity_id == paper.id)).all()

    assert paper.doi == normalize_doi(doi)
    assert paper.title
    assert paper.landing_page_url
    assert authorships
    assert {record.source_name for record in records} == {"openalex", "crossref"}
    assert all(record.raw_payload_hash for record in records)
