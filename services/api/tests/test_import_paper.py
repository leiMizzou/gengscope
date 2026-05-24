from __future__ import annotations

from sqlalchemy import select

from gengscope_api.db.models import Author, Authorship, Institution, Paper, SourceRecord
from gengscope_api.services.import_paper import import_doi
from tests.conftest import SAMPLE_DOI


def test_import_same_doi_twice_is_idempotent(db_session, source_clients) -> None:
    first = import_doi(db_session, f"https://doi.org/{SAMPLE_DOI.upper()}", clients=source_clients)
    second = import_doi(db_session, SAMPLE_DOI, clients=source_clients)

    assert first.id == second.id
    assert second.doi == SAMPLE_DOI
    assert second.title == "Example integrity metadata paper"
    assert second.abstract == "A metadata test"
    assert len(db_session.scalars(select(Paper)).all()) == 1
    assert len(db_session.scalars(select(Author)).all()) == 2
    assert len(db_session.scalars(select(Institution)).all()) == 2
    assert len(db_session.scalars(select(Authorship)).all()) == 2
    assert len(db_session.scalars(select(SourceRecord)).all()) == 2


def test_import_preserves_raw_affiliations_and_source_provenance(db_session, source_clients) -> None:
    paper = import_doi(db_session, SAMPLE_DOI, clients=source_clients)
    authorships = db_session.scalars(select(Authorship).where(Authorship.paper_id == paper.id).order_by(Authorship.author_position)).all()
    records = db_session.scalars(select(SourceRecord).where(SourceRecord.entity_id == paper.id)).all()

    assert authorships[0].affiliation_raw == "School of Life Sciences, Example University"
    assert authorships[1].is_corresponding is True
    assert {record.source_name for record in records} == {"openalex", "crossref"}
    assert all(record.raw_payload_hash for record in records)
