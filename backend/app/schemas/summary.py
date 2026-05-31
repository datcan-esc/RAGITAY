from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryPassageInput(BaseModel):
    section_name: str
    chunk_text: str


class SummaryDecisionInput(BaseModel):
    decision_id: int
    title: str
    daire: str
    esas_no: str
    karar_no: str
    karar_tarihi: str = ""
    outcome: str = ""
    passages: list[SummaryPassageInput] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    results: list[SummaryDecisionInput] = Field(default_factory=list)


class DecisionMiniSummary(BaseModel):
    decision_id: int
    reference: str
    short_summary: str
    why_relevant: str


class SummaryResponse(BaseModel):
    query: str
    general_summary: str
    key_points: list[str]
    decision_summaries: list[DecisionMiniSummary]
    provider: str
    model: str
    fallback_used: bool = False
