from __future__ import annotations

from fastapi import Request

from sales_intelligence.services.companies import CompanyService
from sales_intelligence.services.queue import QueueService
from sales_intelligence.services.user_directory import SupabaseUserDirectory


def company_service(request: Request) -> CompanyService:
    return request.app.state.company_service


def queue_service(request: Request) -> QueueService:
    return request.app.state.queue_service


def user_directory(request: Request) -> SupabaseUserDirectory:
    return request.app.state.user_directory