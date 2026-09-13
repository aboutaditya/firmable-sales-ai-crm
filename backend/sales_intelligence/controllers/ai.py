from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sales_intelligence.ai.content_service import AIContentService
from sales_intelligence.ai.provider import LLMProviderError
from sales_intelligence.pydantic import AIContentResponse, AssessmentResponse
from sales_intelligence.ai.service import AIQualificationService
from sales_intelligence.api.ai_dependencies import ai_service
from sales_intelligence.api.audit_dependencies import audit_service
from sales_intelligence.api.auth import AuthUser, require_roles
from sales_intelligence.api.content_dependencies import content_service
from sales_intelligence.api.rate_limit import ai_rate_limit
from sales_intelligence.services.audit import AuditService


class AIController:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route(
            "/companies/{company_id}/assess",
            self.assess_company,
            methods=["POST"],
            response_model=AssessmentResponse,
            tags=["ai"],
        )
        self.router.add_api_route(
            "/companies/{company_id}/summary",
            self.company_summary,
            methods=["POST"],
            response_model=AIContentResponse,
            tags=["ai"],
        )
        self.router.add_api_route(
            "/companies/{company_id}/outreach",
            self.outreach_draft,
            methods=["POST"],
            response_model=AIContentResponse,
            tags=["ai"],
        )

    def assess_company(
        self,
        company_id: str,
        service: AIQualificationService | None = Depends(ai_service),
        _: None = Depends(ai_rate_limit),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> AssessmentResponse:
        if service is None:
            raise HTTPException(
                status_code=503,
                detail="AI assessment is not configured; set DATABASE_URL, LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL",
            )
        try:
            result = service.assess(company_id, user_id=user.user_id, role=user.access_role)
            audit.record(user_id=user.user_id, role=user.role, action="assess_company", resource_type="company", resource_id=company_id, metadata={"cached": result.cached})
            return result
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LLMProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def generate_content(
        self,
        feature: str,
        company_id: str,
        service: AIContentService | None,
        user: AuthUser,
        audit: AuditService,
    ) -> dict:
        if service is None:
            raise HTTPException(
                status_code=503,
                detail="AI content generation is not configured; set DATABASE_URL and LLM settings",
            )
        try:
            result = service.generate(company_id, feature, user_id=user.user_id, role=user.access_role)
            audit.record(user_id=user.user_id, role=user.role, action=f"generate_{feature}", resource_type="company", resource_id=company_id, metadata={"cached": result["cached"]})
            return result
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LLMProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def company_summary(
        self,
        company_id: str,
        service: AIContentService | None = Depends(content_service),
        _: None = Depends(ai_rate_limit),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> AIContentResponse:
        return self.generate_content("company_summary", company_id, service, user, audit)

    def outreach_draft(
        self,
        company_id: str,
        service: AIContentService | None = Depends(content_service),
        _: None = Depends(ai_rate_limit),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> AIContentResponse:
        return self.generate_content("outreach", company_id, service, user, audit)


def build_ai_router() -> APIRouter:
    return AIController().router