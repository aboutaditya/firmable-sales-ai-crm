from __future__ import annotations

from fastapi import APIRouter

from sales_intelligence.config import Settings
from sales_intelligence.controllers.admin import build_admin_router
from sales_intelligence.controllers.ai import build_ai_router
from sales_intelligence.controllers.companies import build_companies_router
from sales_intelligence.controllers.queue import build_queue_router
from sales_intelligence.controllers.system import build_system_router


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(build_system_router(settings))
    router.include_router(build_queue_router())
    router.include_router(build_admin_router())
    router.include_router(build_companies_router())
    router.include_router(build_ai_router())
    return router