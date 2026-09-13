from __future__ import annotations

from fastapi import Request

from sales_intelligence.ai.content_service import AIContentService


def content_service(request: Request) -> AIContentService | None:
    return request.app.state.ai_content
