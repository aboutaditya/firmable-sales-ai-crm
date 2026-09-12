from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from sales_intelligence.config import Settings
from sales_intelligence.pydantic import HealthResponse, ReadinessResponse


class SystemController:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = APIRouter()
        self.router.add_api_route("/health", self.health, methods=["GET"], response_model=HealthResponse, tags=["system"])
        self.router.add_api_route("/health/live", self.live, methods=["GET"], response_model=HealthResponse, tags=["system"])
        self.router.add_api_route("/health/ready", self.ready, methods=["GET"], response_model=ReadinessResponse, tags=["system"])

    def health(self) -> HealthResponse:
        return HealthResponse(service=self.settings.app_name)

    def live(self) -> HealthResponse:
        return HealthResponse(service=self.settings.app_name)

    def ready(self, request: Request) -> ReadinessResponse:
        checks: dict[str, str] = {}
        session_factory = request.app.state.session_factory
        if session_factory:
            try:
                with session_factory() as session:
                    session.execute(text("select 1"))
                checks["database"] = "ok"
            except Exception:
                checks["database"] = "error"
        else:
            checks["dataset"] = "ok" if self.settings.analytical_dataset.exists() else "error"
        if "error" in checks.values():
            raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
        return ReadinessResponse(status="ready", service=self.settings.app_name, checks=checks)


def build_system_router(settings: Settings) -> APIRouter:
    return SystemController(settings).router