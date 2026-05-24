from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gengscope_api.api.deps import get_source_clients
from gengscope_api.config import get_settings
from gengscope_api.db.models import Base
from gengscope_api.db.session import get_db
from gengscope_api.main import create_app
from gengscope_api.services.import_paper import SourceClients


SAMPLE_DOI = "10.1234/example.paper"


class FakeOpenAlexClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or openalex_payload()
        self.author_candidate = {
            "id": "https://openalex.org/A1",
            "display_name": "Alice Zhang",
            "works_count": 2,
            "last_known_institution": {"display_name": "Example University", "country_code": "CN"},
        }
        self.other_author_candidate = {
            "id": "https://openalex.org/A9",
            "display_name": "Alicia Zhang",
            "works_count": 99,
            "last_known_institution": {"display_name": "Other University", "country_code": "CN"},
        }
        self.institution_candidate = {
            "id": "https://openalex.org/I1",
            "display_name": "Example University",
            "works_count": 2,
            "country_code": "CN",
            "city": "Shanghai",
        }
        self.entity_works = [
            openalex_payload(
                doi="10.1234/example.paper",
                openalex_id="https://openalex.org/W123",
                title="Example integrity metadata paper",
                pdf_url="https://example.org/paper.pdf",
            ),
            openalex_payload(
                doi="10.1234/example.second",
                openalex_id="https://openalex.org/W124",
                title="Second auditable paper",
                pdf_url=None,
            ),
        ]
        self.calls = 0
        self.author_search_calls = 0
        self.institution_search_calls = 0

    def fetch_work_by_doi(self, doi: str) -> dict:
        self.calls += 1
        payload = dict(self.payload)
        payload["doi"] = f"https://doi.org/{doi}"
        return payload

    def search_authors(self, query: str, limit: int = 10) -> list[dict]:
        self.author_search_calls += 1
        return [self.other_author_candidate, self.author_candidate][:limit]

    def search_institutions(self, query: str, limit: int = 10) -> list[dict]:
        self.institution_search_calls += 1
        return [self.institution_candidate][:limit]

    def fetch_works_by_author(
        self,
        author_openalex_id: str,
        limit: int = 25,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict]:
        return self.entity_works[:limit]

    def fetch_works_by_institution(
        self,
        institution_openalex_id: str,
        limit: int = 25,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[dict]:
        return self.entity_works[:limit]


class FakeCrossrefClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or crossref_payload()
        self.calls = 0

    def fetch_work_by_doi(self, doi: str) -> dict:
        self.calls += 1
        payload = dict(self.payload)
        payload["DOI"] = doi
        payload["URL"] = f"https://doi.org/{doi}"
        return payload


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def source_clients() -> SourceClients:
    return SourceClients(openalex=FakeOpenAlexClient(), crossref=FakeCrossrefClient())


@pytest.fixture
def api_client(db_session, source_clients, tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_STORAGE_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    app = create_app(init_tables=False)

    def override_db():
        yield db_session

    def override_clients():
        return source_clients

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_source_clients] = override_clients
    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def openalex_payload(
    doi: str = SAMPLE_DOI,
    openalex_id: str = "https://openalex.org/W123",
    title: str = "Example integrity metadata paper",
    pdf_url: str | None = "https://example.org/paper.pdf",
) -> dict:
    return {
        "id": openalex_id,
        "doi": f"https://doi.org/{doi}",
        "title": title,
        "abstract_inverted_index": {"A": [0], "metadata": [1], "test": [2]},
        "publication_year": 2024,
        "publication_date": "2024-05-12",
        "type": "journal-article",
        "is_retracted": False,
        "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345"},
        "primary_location": {
            "landing_page_url": f"https://doi.org/{doi}",
            "pdf_url": pdf_url,
            "source": {
                "display_name": "Journal of Metadata Integrity",
                "host_organization_name": "Example Publisher",
            },
        },
        "authorships": [
            {
                "author_position": "first",
                "is_corresponding": False,
                "raw_affiliation_strings": ["School of Life Sciences, Example University"],
                "author": {"id": "https://openalex.org/A1", "display_name": "Alice Zhang", "orcid": None},
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "display_name": "Example University",
                        "ror": "https://ror.org/12345",
                        "country_code": "CN",
                        "city": "Shanghai",
                    }
                ],
            },
            {
                "author_position": "last",
                "is_corresponding": True,
                "raw_affiliation_strings": ["Department of Medicine, Example Hospital"],
                "author": {"id": "https://openalex.org/A2", "display_name": "Bo Li", "orcid": "https://orcid.org/0000-0000-0000-0002"},
                "institutions": [
                    {
                        "id": "https://openalex.org/I2",
                        "display_name": "Example Hospital",
                        "ror": None,
                        "country_code": "CN",
                        "city": "Beijing",
                    }
                ],
            },
        ],
    }


def crossref_payload() -> dict:
    return {
        "DOI": SAMPLE_DOI,
        "title": ["Example integrity metadata paper"],
        "container-title": ["Journal of Metadata Integrity"],
        "publisher": "Example Publisher",
        "type": "journal-article",
        "member": "123",
        "URL": f"https://doi.org/{SAMPLE_DOI}",
        "published-online": {"date-parts": [[2024, 5, 12]]},
        "author": [
            {"given": "Alice", "family": "Zhang"},
            {"given": "Bo", "family": "Li"},
        ],
    }
