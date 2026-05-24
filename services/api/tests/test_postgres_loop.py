from __future__ import annotations

import os
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from gengscope_api.api.deps import get_source_clients
from gengscope_api.db.models import Base
from gengscope_api.db.session import build_engine, get_db
from gengscope_api.main import create_app
from gengscope_api.services.import_paper import SourceClients
from tests.conftest import FakeCrossrefClient, FakeOpenAlexClient, SAMPLE_DOI

pytestmark = pytest.mark.postgres


def test_postgres_http_metadata_event_risk_agent_loop() -> None:
    database_url = os.getenv("GENGSCOPE_POSTGRES_URL")
    if not database_url:
        pytest.skip("set GENGSCOPE_POSTGRES_URL to run PostgreSQL integration tests")
    if os.getenv("GENGSCOPE_ALLOW_DB_RESET") != "1":
        pytest.skip("set GENGSCOPE_ALLOW_DB_RESET=1; this test drops and recreates GengScope tables")

    pytest.importorskip("psycopg")

    engine = build_engine(database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    db_session = TestingSessionLocal()
    try:
        app = create_app(init_tables=False)

        def override_db():
            yield db_session

        def override_clients():
            return SourceClients(openalex=FakeOpenAlexClient(), crossref=FakeCrossrefClient())

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_source_clients] = override_clients
        client = TestClient(app)

        import_response = client.post(
            "/api/admin/import/doi",
            json={"doi": SAMPLE_DOI, "sources": ["openalex", "crossref"]},
        )
        assert import_response.status_code == 200, import_response.text
        assert import_response.json()["source_record_count"] == 2

        event_response = client.post(
            "/api/admin/events",
            json={
                "doi": SAMPLE_DOI,
                "event_type": "institution_notice",
                "status_level": "institution_investigation",
                "source_type": "institution",
                "source_name": "Example University",
                "source_url": "https://example.edu/notice",
                "claim_summary": "机构公告称已成立调查组。",
                "verification_status": "source_verified",
            },
        )
        assert event_response.status_code == 200, event_response.text

        agent_response = client.get(f"/api/agent/doi/{quote(SAMPLE_DOI, safe='')}")
        assert agent_response.status_code == 200, agent_response.text
        agent = agent_response.json()
        assert agent["paper"]["doi"] == SAMPLE_DOI
        assert agent["risk_card"]["institution_status"] == "investigation"
        assert agent["risk_card"]["highest_signal_level"] == "investigation"

        corpus_response = client.post(
            "/api/entities/corpus",
            json={"entity_type": "author", "query": "Alice Zhang", "limit": 10},
        )
        assert corpus_response.status_code == 200, corpus_response.text
        corpus = corpus_response.json()
        assert corpus["profile"]["paper_count"] == 2
        assert corpus["profile"]["auditable_paper_count"] == 1

        queue_response = client.post(
            "/api/entities/review-queue",
            json={"entity_type": "author", "entity_id": corpus["entity"]["id"], "priority": 6},
        )
        assert queue_response.status_code == 200, queue_response.text
        assert queue_response.json()["created_review_tasks"] == 1

        metadata_response = client.post(
            "/api/audits/metadata",
            json={"entity_type": "author", "entity_id": corpus["entity"]["id"], "min_cluster_size": 2, "priority": 6},
        )
        assert metadata_response.status_code == 200, metadata_response.text
        metadata = metadata_response.json()
        assert metadata["signal_count"] >= 5
        assert {
            "metadata_publication_year_cluster",
            "metadata_journal_cluster",
            "metadata_official_event_density",
        }.issubset({signal["signal_type"] for signal in metadata["signals"]})

        signals_response = client.get(f"/api/entities/author/{corpus['entity']['id']}/signals")
        assert signals_response.status_code == 200, signals_response.text
        assert signals_response.json()["total"] >= 5
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
