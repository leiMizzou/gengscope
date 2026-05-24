from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(confirmed_signal|false_positive|not_actionable|needs_more_evidence)$")
    reviewer_note: str | None = Field(default=None, max_length=1000)
    assigned_to: str | None = None

