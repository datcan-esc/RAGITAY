from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DecisionChatRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Question about the selected decision.")

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise ValueError("Question must contain at least 3 characters.")
        return cleaned


class DecisionChatResponse(BaseModel):
    decision_id: int
    reference: str
    answer: str
    key_points: list[str]
    provider: str
    model: str
    fallback_used: bool = False
