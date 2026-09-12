from __future__ import annotations

from fastapi import Request

from sales_intelligence.backend.ai.service import AIQualificationService


def ai_service(request: Request) -> AIQualificationService | None:
    return request.app.state.ai_qualification
