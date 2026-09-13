from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sales_intelligence.api.audit_dependencies import audit_service
from sales_intelligence.api.auth import AuthUser, require_authenticated_queue_user, require_roles
from sales_intelligence.api.dependencies import queue_service
from sales_intelligence.pydantic import (
    CallActivityRequest,
    DispositionUpdate,
    QueueLead,
    QueueListResponse,
    QueueNextResponse,
    QueuePreferences,
    QueuePreferencesUpdate,
)
from sales_intelligence.services.audit import AuditService
from sales_intelligence.services.queue import QueueService

logger = logging.getLogger("sales_intelligence.queue")


class QueueController:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/me/preferences", self.get_my_preferences, methods=["GET"], response_model=QueuePreferences, tags=["queue"])
        self.router.add_api_route("/me/preferences", self.update_my_preferences, methods=["PATCH"], response_model=QueuePreferences, tags=["queue"])
        self.router.add_api_route("/me/queue/next", self.next_queue_lead, methods=["GET"], response_model=QueueNextResponse, tags=["queue"])
        self.router.add_api_route("/me/queue", self.list_my_queue, methods=["GET"], response_model=QueueListResponse, tags=["queue"])
        self.router.add_api_route("/me/queue/{company_id}/disposition", self.update_queue_disposition, methods=["POST"], response_model=QueueLead, tags=["queue"])
        self.router.add_api_route("/me/queue/{company_id}/calls", self.record_call_activity, methods=["POST"], response_model=QueueLead, tags=["queue"])

    def get_my_preferences(
        self,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
    ) -> QueuePreferences:
        require_authenticated_queue_user(user)
        try:
            return QueuePreferences.model_validate(service.get_queue_preferences(user.user_id))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def update_my_preferences(
        self,
        preferences: QueuePreferencesUpdate,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager")),
    ) -> QueuePreferences:
        require_authenticated_queue_user(user)
        try:
            return QueuePreferences.model_validate(
                service.update_queue_preferences(user.user_id, min_exposure_score=preferences.min_exposure_score)
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def next_queue_lead(
        self,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
        request: Request = Depends(lambda r: r),
    ) -> QueueNextResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        require_authenticated_queue_user(user)
        try:
            logger.info("next_queue_lead_start", extra={"request_id": request_id, "user_id": user.user_id})
            result = service.next_assigned_company(user.user_id)
            queue_status = service.queue_status(user.user_id)
        except RuntimeError as exc:
            logger.error("next_queue_lead_error", extra={"request_id": request_id, "user_id": user.user_id, "error": str(exc)}, exc_info=True)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if result is None:
            logger.info("next_queue_lead_empty", extra={"request_id": request_id, "user_id": user.user_id})
            return QueueNextResponse(**queue_status, message="No unassigned companies are available right now.")
        audit.record(user_id=user.user_id, role=user.role, action="claim_next_lead", resource_type="company", resource_id=result["company"]["company_id"])
        logger.info("next_queue_lead_success", extra={"request_id": request_id, "user_id": user.user_id, "company_id": result["company"]["company_id"]})
        return QueueNextResponse(lead=QueueLead.model_validate(result), **queue_status, message="Lead claimed")

    def list_my_queue(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
    ) -> QueueListResponse:
        require_authenticated_queue_user(user)
        try:
            items, total = service.list_assigned_companies(user.user_id, limit=page_size, offset=(page - 1) * page_size)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit.record(user_id=user.user_id, role=user.role, action="list_assigned_leads", resource_type="company")
        return QueueListResponse(
            items=[QueueLead.model_validate(item) for item in items],
            count=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

    def update_queue_disposition(
        self,
        company_id: str,
        update: DispositionUpdate,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
        request: Request = Depends(lambda r: r),
    ) -> QueueLead:
        request_id = getattr(request.state, "request_id", "unknown")
        require_authenticated_queue_user(user)
        try:
            logger.info("update_disposition_start", extra={"request_id": request_id, "company_id": company_id, "disposition": update.disposition})
            result = service.update_disposition(
                company_id,
                user.user_id,
                disposition=update.disposition,
                notes=update.notes,
                next_follow_up_at=update.next_follow_up_at,
            )
            audit.record(user_id=user.user_id, role=user.role, action="update_disposition", resource_type="company", resource_id=company_id, metadata={"disposition": update.disposition})
            logger.info("update_disposition_success", extra={"request_id": request_id, "company_id": company_id, "disposition": update.disposition})
            return QueueLead.model_validate(result)
        except PermissionError as exc:
            logger.warning("update_disposition_forbidden", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            logger.warning("update_disposition_not_found", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("update_disposition_error", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)}, exc_info=True)
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def record_call_activity(
        self,
        company_id: str,
        activity: CallActivityRequest,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin", "sales_manager", "sales_rep")),
        audit: AuditService = Depends(audit_service),
        request: Request = Depends(lambda r: r),
    ) -> QueueLead:
        request_id = getattr(request.state, "request_id", "unknown")
        require_authenticated_queue_user(user)
        try:
            logger.info("record_call_start", extra={"request_id": request_id, "company_id": company_id, "outcome": activity.outcome})
            result = service.record_call(
                company_id,
                user.user_id,
                outcome=activity.outcome,
                notes=activity.notes,
                next_follow_up_at=activity.next_follow_up_at,
            )
            audit.record(user_id=user.user_id, role=user.role, action="record_call", resource_type="company", resource_id=company_id, metadata={"outcome": activity.outcome})
            logger.info("record_call_success", extra={"request_id": request_id, "company_id": company_id, "outcome": activity.outcome})
            return QueueLead.model_validate(result)
        except PermissionError as exc:
            logger.warning("record_call_forbidden", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            logger.warning("record_call_not_found", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("record_call_error", extra={"request_id": request_id, "company_id": company_id, "error": str(exc)}, exc_info=True)
            raise HTTPException(status_code=503, detail=str(exc)) from exc


def build_queue_router() -> APIRouter:
    return QueueController().router