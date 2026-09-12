from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, str]