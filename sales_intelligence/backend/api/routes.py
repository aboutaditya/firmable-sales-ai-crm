from __future__ import annotations

from fastapi import APIRouter

from sales_intelligence.backend.config import Settings
from sales_intelligence.backend.controllers.admin import build_admin_router
from sales_intelligence.backend.controllers.ai import build_ai_router
from sales_intelligence.backend.controllers.companies import build_companies_router
from sales_intelligence.backend.controllers.queue import build_queue_router
from sales_intelligence.backend.controllers.system import build_system_router


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(build_system_router(settings))
    router.include_router(build_queue_router())
    router.include_router(build_admin_router())
    router.include_router(build_companies_router())
    router.include_router(build_ai_router())
    return router