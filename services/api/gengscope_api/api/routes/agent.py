from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from gengscope_api.db.session import get_db
from gengscope_api.services.risk_card import agent_summary_for_doi, risk_card_for_doi

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/doi/{doi:path}")
def agent_doi_summary(doi: str, db: Session = Depends(get_db)) -> dict:
    try:
        return agent_summary_for_doi(db, doi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/batch-risk-cards")
def batch_risk_cards(payload: dict, db: Session = Depends(get_db)) -> dict:
    items = []
    for doi in payload.get("dois") or []:
        try:
            items.append(risk_card_for_doi(db, doi))
        except LookupError:
            items.append({"doi": doi, "error": "paper_not_found"})
        except ValueError as exc:
            items.append({"doi": doi, "error": "invalid_doi", "message": str(exc)})
    return {"items": items}
