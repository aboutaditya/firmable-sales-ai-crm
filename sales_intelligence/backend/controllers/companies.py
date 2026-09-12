from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from sales_intelligence.backend.api.audit_dependencies import audit_service
from sales_intelligence.backend.api.auth import AuthUser, require_roles
from sales_intelligence.backend.api.dependencies import company_service, queue_service
from sales_intelligence.backend.pydantic import AssignmentRequest, Company, CompanyListResponse
from sales_intelligence.backend.services.audit import AuditService
from sales_intelligence.backend.services.companies import CompanyService
from sales_intelligence.backend.services.queue import QueueService


class CompanyController:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/companies", self.list_companies, methods=["GET"], response_model=CompanyListResponse, tags=["companies"])
        self.router.add_api_route("/companies/{company_id}", self.get_company, methods=["GET"], response_model=Company, tags=["companies"])
        self.router.add_api_route("/companies/{company_id}/assign", self.assign_company, methods=["POST"], tags=["companies"])

    def list_companies(
        self,
        country: str | None = Query(default=None),
        min_score: int | None = Query(default=None, ge=0, le=100),
        industry: str | None = Query(default=None),
        min_employee_count: int | None = Query(default=None, ge=0),
        signal: list[str] | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=10_000),
        offset: int = Query(default=0, ge=0),
        cursor: str | None = Query(default=None),
        service: CompanyService = Depends(company_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> CompanyListResponse:
        if user.access_role == "sales_rep":
            raise HTTPException(status_code=403, detail="Sales representatives use the assigned one-lead queue")
        items = service.list_companies(
            country=country, min_score=min_score, industry=industry,
            min_employee_count=min_employee_count, signals=signal, cursor=cursor, limit=limit, offset=offset,
            user_id=user.user_id, role=user.access_role,
        )
        audit.record(user_id=user.user_id, role=user.role, action="list_companies", resource_type="company", metadata={"country": country, "min_score": min_score, "limit": limit})
        return CompanyListResponse(
            items=items, limit=limit, offset=offset, count=len(items),
            next_cursor=service.cursor_for(items, limit),
        )

    def get_company(
        self,
        company_id: str,
        service: CompanyService = Depends(company_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> Company:
        company = service.get_company(company_id, user_id=user.user_id, role=user.access_role)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        audit.record(user_id=user.user_id, role=user.role, action="view_company", resource_type="company", resource_id=company_id)
        return Company.model_validate(company)

    def assign_company(
        self,
        company_id: str,
        assignment: AssignmentRequest,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager")),
        audit: AuditService = Depends(audit_service),
    ) -> dict:
        try:
            service.assign_company(company_id, assignment.user_id, user.user_id, assignment.team_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit.record(
            user_id=user.user_id, role=user.role, action="assign_company",
            resource_type="company", resource_id=company_id,
            metadata={"assigned_user_id": assignment.user_id, "team_id": assignment.team_id},
        )
        return {"status": "assigned", "company_id": company_id, "user_id": assignment.user_id}


def build_companies_router() -> APIRouter:
    return CompanyController().router