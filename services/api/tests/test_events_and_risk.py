from __future__ import annotations

import pytest

from gengscope_api.db.models import AlgorithmicSignal
from gengscope_api.schemas.admin import ManualEventRequest
from gengscope_api.services.events import create_manual_event
from gengscope_api.services.import_paper import import_doi
from gengscope_api.services.risk_card import risk_card_for_doi
from tests.conftest import SAMPLE_DOI


def test_manual_event_requires_source_url_and_rejects_unofficial_official_status(db_session, source_clients) -> None:
    import_doi(db_session, SAMPLE_DOI, clients=source_clients)
    request = ManualEventRequest(
        doi=SAMPLE_DOI,
        event_type="media_report",
        status_level="official_retraction",
        source_type="media",
        source_url="https://example.org/report",
        claim_summary="公开报道称该论文存在争议。",
    )

    with pytest.raises(ValueError, match="Unofficial sources"):
        create_manual_event(db_session, request)


def test_manual_event_requires_imported_paper(db_session) -> None:
    request = ManualEventRequest(
        doi=SAMPLE_DOI,
        event_type="public_discussion",
        status_level="public_discussion",
        source_type="pubpeer",
        source_url="https://pubpeer.com/example",
        claim_summary="PubPeer 页面存在公开讨论。",
    )

    with pytest.raises(LookupError):
        create_manual_event(db_session, request)


def test_risk_card_counts_public_and_algorithmic_signals_separately(db_session, source_clients) -> None:
    paper = import_doi(db_session, SAMPLE_DOI, clients=source_clients)
    create_manual_event(
        db_session,
        ManualEventRequest(
            doi=SAMPLE_DOI,
            event_type="public_discussion",
            status_level="public_discussion",
            source_type="pubpeer",
            source_url="https://pubpeer.com/example",
            claim_summary="PubPeer 页面存在关于 Figure 4c 的公开讨论。",
            verification_status="source_verified",
        ),
    )
    db_session.add(
        AlgorithmicSignal(
            paper_id=paper.id,
            signal_type="numeric_last_digit_anomaly",
            severity="medium",
            confidence=0.82,
            analyzer_name="gengscope.numeric",
            analyzer_version="0.1.0",
            summary="Source data 中末位数字分布偏离均匀分布，需要人工复核。",
            status="needs_review",
        )
    )
    db_session.commit()

    card = risk_card_for_doi(db_session, SAMPLE_DOI)

    assert card["official_status"] == "none"
    assert card["public_discussion_count"] == 1
    assert card["algorithmic_signal_count"] == 1
    assert card["highest_signal_level"] == "public_discussion"
    assert "公开讨论" in card["summary"]


def test_risk_card_prefers_retraction_over_correction(db_session, source_clients) -> None:
    import_doi(db_session, SAMPLE_DOI, clients=source_clients)
    create_manual_event(
        db_session,
        ManualEventRequest(
            doi=SAMPLE_DOI,
            event_type="correction",
            status_level="official_correction",
            source_type="publisher",
            source_name="Example Publisher",
            source_url="https://example.org/correction",
            claim_summary="出版方发布更正说明。",
            verification_status="official_confirmed",
        ),
    )
    create_manual_event(
        db_session,
        ManualEventRequest(
            doi=SAMPLE_DOI,
            event_type="retraction",
            status_level="official_retraction",
            source_type="publisher",
            source_name="Example Publisher",
            source_url="https://example.org/retraction",
            claim_summary="出版方发布撤稿说明。",
            verification_status="official_confirmed",
        ),
    )

    card = risk_card_for_doi(db_session, SAMPLE_DOI)

    assert card["official_status"] == "retracted"
    assert card["publisher_status"] == "retraction"
    assert card["highest_signal_level"] == "official"
    assert "撤稿" in card["summary"]
