from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    service_role_key_loaded: bool = False


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, str]