from __future__ import annotations

from fastapi import Request

from sales_intelligence.services.audit import AuditService


def audit_service(request: Request) -> AuditService:
    return request.app.state.audit
