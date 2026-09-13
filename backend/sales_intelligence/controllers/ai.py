from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request

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

logger = logging.getLogger("sales_intelligence.ai")


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
        request: Request = None,
    ) -> AssessmentResponse:
        request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"

        if service is None:
            logger.error("assess_company_not_configured", extra={"request_id": request_id, "company_id": company_id})
            raise HTTPException(
                status_code=503,
                detail="AI assessment is not configured; set DATABASE_URL, LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL",
            )
        try:
            logger.info("assess_company_start", extra={"request_id": request_id, "company_id": company_id, "user_id": user.user_id})
            result = service.assess(company_id, user_id=user.user_id, role=user.access_role)
            audit.record(user_id=user.user_id, role=user.role, action="assess_company", resource_type="company", resource_id=company_id, metadata={"cached": result.cached})
            logger.info("assess_company_success", extra={"request_id": request_id, "company_id": company_id, "cached": result.cached})
            return result
        except LookupError as exc:
            logger.warning("assess_company_not_found", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            logger.warning("assess_company_permission_denied", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LLMProviderError as exc:
            logger.error("assess_company_llm_error", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)}, exc_info=True)
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("assess_company_unexpected_error", extra={"request_id": request_id, "company_id": company_id, "error_type": type(exc).__name__, "error": str(exc)}, exc_info=True)
            raise

    def generate_content(
        self,
        feature: str,
        company_id: str,
        service: AIContentService | None,
        user: AuthUser,
        audit: AuditService,
        request: Request | None = None,
    ) -> dict:
        request_id = getattr(request.state, "request_id", "unknown") if request else "unknown"

        if service is None:
            logger.error("generate_content_not_configured", extra={"request_id": request_id, "feature": feature, "company_id": company_id})
            raise HTTPException(
                status_code=503,
                detail="AI content generation is not configured; set DATABASE_URL and LLM settings",
            )
        try:
            logger.info("generate_content_start", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "user_id": user.user_id})
            result = service.generate(company_id, feature, user_id=user.user_id, role=user.access_role)
            audit.record(user_id=user.user_id, role=user.role, action=f"generate_{feature}", resource_type="company", resource_id=company_id, metadata={"cached": result["cached"]})
            logger.info("generate_content_success", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "cached": result.get("cached", False)})
            return result
        except LookupError as exc:
            logger.warning("generate_content_not_found", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            logger.warning("generate_content_permission_denied", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LLMProviderError as exc:
            logger.error("generate_content_llm_error", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "error": str(exc)}, exc_info=True)
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("generate_content_unexpected_error", extra={"request_id": request_id, "feature": feature, "company_id": company_id, "error_type": type(exc).__name__, "error": str(exc)}, exc_info=True)
            raise

    def company_summary(
        self,
        company_id: str,
        service: AIContentService | None = Depends(content_service),
        _: None = Depends(ai_rate_limit),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
        request: Request = Depends(lambda r: r),
    ) -> AIContentResponse:
        return self.generate_content("company_summary", company_id, service, user, audit, request)

    def outreach_draft(
        self,
        company_id: str,
        service: AIContentService | None = Depends(content_service),
        _: None = Depends(ai_rate_limit),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
        request: Request = Depends(lambda r: r),
    ) -> AIContentResponse:
        return self.generate_content("outreach", company_id, service, user, audit, request)


def build_ai_router() -> APIRouter:
    return AIController().router