from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QualificationResult(BaseModel):
    ai_score: int = Field(ge=0, le=100)
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1, max_length=4000)


class AssessmentResponse(QualificationResult):
    company_id: str
    model: str
    prompt_version: str
    cached: bool
    latency_ms: int | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIContentResponse(BaseModel):
    company_id: str
    feature: Literal["company_summary", "outreach"]
    content: str
    model: str
    prompt_version: str
    cached: bool
    latency_ms: int | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None