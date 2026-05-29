from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language legal query.")
    source_names: list[str] = Field(default_factory=list, description="Optional source filters like yargitay or uyap_emsal.")
    daire: str = Field(default="", description="Exact chamber filter.")
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    top_k_chunks: int = Field(default=40, ge=5, le=200)
    top_k_lexical: int = Field(default=40, ge=5, le=200)
    top_decisions: int = Field(default=5, ge=1, le=20)
    max_passages_per_decision: int = Field(default=2, ge=1, le=5)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Query must contain at least 2 characters.")
        return cleaned

    @field_validator("source_names")
    @classmethod
    def normalize_sources(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @field_validator("daire")
    @classmethod
    def normalize_daire(cls, value: str) -> str:
        return " ".join(value.split()).strip()


class SummaryItem(BaseModel):
    summary: str
    reference: str


class PassageResult(BaseModel):
    chunk_id: int
    chunk_index: int
    section_name: str
    semantic_score: float
    lexical_score: float
    adjusted_score: float
    chunk_text: str


class DecisionResult(BaseModel):
    decision_id: int
    source_name: str
    external_id: str
    title: str
    daire: str
    esas_no: str
    karar_no: str
    karar_tarihi: Optional[date] = None
    mahkeme: str
    outcome: str
    source_url: str
    score: float
    passages: list[PassageResult]


class SearchResponse(BaseModel):
    query: str
    query_model: str
    search_mode: str = "hybrid"
    top_k_chunks: int
    top_k_lexical: int
    top_decisions: int
    summary: list[SummaryItem]
    results: list[DecisionResult]
