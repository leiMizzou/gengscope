from __future__ import annotations

import argparse
import json
import os
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gengscope_api.db.models import Author, Authorship, Institution, Paper
from gengscope_api.db.session import SessionLocal, init_db


DEMO_AUTHOR_OPENALEX_ID = "https://openalex.org/A-GENGSCOPE-DEMO"
DEMO_INSTITUTION_OPENALEX_ID = "https://openalex.org/I-GENGSCOPE-DEMO"
DEMO_DOI = "10.5555/gengscope.demo.1"


def seed_demo_data(db: Session) -> dict[str, Any]:
    author = _upsert_author(db)
    institution = _upsert_institution(db)
    papers = [_upsert_paper(db, item) for item in _demo_papers()]
    db.flush()
    for index, paper in enumerate(papers, start=1):
        _upsert_authorship(db, paper=paper, author=author, institution=institution, index=index)
    db.commit()
    db.refresh(author)
    db.refresh(institution)
    for paper in papers:
        db.refresh(paper)
    return {
        "author": {
            "id": author.id,
            "entity_type": "author",
            "display_name": author.display_name,
            "openalex_id": author.openalex_id,
        },
        "institution": {
            "id": institution.id,
            "entity_type": "institution",
            "display_name": institution.display_name,
            "openalex_id": institution.openalex_id,
        },
        "papers": [
            {
                "id": paper.id,
                "doi": paper.doi,
                "title": paper.title,
                "publication_year": paper.publication_year,
                "material_status": paper.material_status,
            }
            for paper in papers
        ],
        "primary_doi": DEMO_DOI,
        "conclusion_boundary": "Demo seed data is synthetic and exists only to verify local deployment workflows.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed deterministic demo data for local GengScope deployment checks.")
    parser.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL or sqlite:///./gengscope_api.db.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    init_db()
    with SessionLocal() as db:
        result = seed_demo_data(db)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _upsert_author(db: Session) -> Author:
    author = db.scalar(select(Author).where(Author.openalex_id == DEMO_AUTHOR_OPENALEX_ID))
    if author is None:
        author = Author(
            display_name="GengScope Demo Author",
            openalex_id=DEMO_AUTHOR_OPENALEX_ID,
            name_variants=["GengScope Demo Author"],
            disambiguation_status="demo_seed",
        )
        db.add(author)
        db.flush()
    else:
        author.display_name = "GengScope Demo Author"
        author.name_variants = ["GengScope Demo Author"]
        author.disambiguation_status = "demo_seed"
    return author


def _upsert_institution(db: Session) -> Institution:
    institution = db.scalar(select(Institution).where(Institution.openalex_id == DEMO_INSTITUTION_OPENALEX_ID))
    if institution is None:
        institution = Institution(
            display_name="GengScope Demo Institute",
            english_name="GengScope Demo Institute",
            openalex_id=DEMO_INSTITUTION_OPENALEX_ID,
            country_code="CN",
            city="Shanghai",
            aliases=["GengScope Demo Institute"],
        )
        db.add(institution)
        db.flush()
    else:
        institution.display_name = "GengScope Demo Institute"
        institution.english_name = "GengScope Demo Institute"
        institution.country_code = "CN"
        institution.city = "Shanghai"
        institution.aliases = ["GengScope Demo Institute"]
    return institution


def _upsert_paper(db: Session, payload: dict[str, Any]) -> Paper:
    paper = db.scalar(select(Paper).where(Paper.doi == payload["doi"]))
    if paper is None:
        paper = Paper(doi=payload["doi"], title=payload["title"])
        db.add(paper)
        db.flush()
    paper.title = payload["title"]
    paper.abstract = payload["abstract"]
    paper.journal_name = payload["journal_name"]
    paper.publisher = payload["publisher"]
    paper.publication_year = payload["publication_year"]
    paper.publication_date = payload["publication_date"]
    paper.type = "journal-article"
    paper.openalex_id = payload["openalex_id"]
    paper.landing_page_url = payload["landing_page_url"]
    paper.open_access_url = payload["open_access_url"]
    paper.is_retracted = False
    paper.is_oa_pdf_available = bool(payload["open_access_url"])
    paper.material_status = "pdf_found" if payload["open_access_url"] else "landing_page_found"
    return paper


def _upsert_authorship(db: Session, *, paper: Paper, author: Author, institution: Institution, index: int) -> Authorship:
    authorship = db.scalar(
        select(Authorship).where(
            Authorship.paper_id == paper.id,
            Authorship.author_id == author.id,
            Authorship.institution_id == institution.id,
        )
    )
    if authorship is None:
        authorship = Authorship(paper=paper, author=author, institution=institution, author_name_raw=author.display_name)
        db.add(authorship)
    authorship.author_position = 1
    authorship.author_role = "corresponding" if index == 1 else "first"
    authorship.is_corresponding = index == 1
    authorship.affiliation_raw = "GengScope Demo Institute, Shanghai, China"
    authorship.affiliation_match_confidence = 1.0
    return authorship


def _demo_papers() -> list[dict[str, Any]]:
    return [
        {
            "doi": DEMO_DOI,
            "title": "Synthetic source-data audit fixture for GengScope deployment",
            "abstract": "Synthetic paper used to verify local deployment workflows.",
            "journal_name": "GengScope Demo Journal",
            "publisher": "GengScope Demo Publisher",
            "publication_year": 2026,
            "publication_date": date(2026, 5, 1),
            "openalex_id": "https://openalex.org/W-GENGSCOPE-DEMO-1",
            "landing_page_url": "https://example.org/gengscope/demo-1",
            "open_access_url": "https://example.org/gengscope/demo-1.pdf",
        },
        {
            "doi": "10.5555/gengscope.demo.2",
            "title": "Synthetic metadata-only fixture for GengScope entity profiling",
            "abstract": "Synthetic paper used to verify local entity coverage calculations.",
            "journal_name": "GengScope Demo Journal",
            "publisher": "GengScope Demo Publisher",
            "publication_year": 2025,
            "publication_date": date(2025, 8, 12),
            "openalex_id": "https://openalex.org/W-GENGSCOPE-DEMO-2",
            "landing_page_url": "https://example.org/gengscope/demo-2",
            "open_access_url": None,
        },
    ]


if __name__ == "__main__":
    raise SystemExit(main())
