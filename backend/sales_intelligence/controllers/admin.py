from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from sales_intelligence.api.audit_dependencies import audit_service
from sales_intelligence.api.auth import AuthUser, require_authenticated_queue_user, require_roles
from sales_intelligence.api.dependencies import queue_service, user_directory
from sales_intelligence.pydantic import AdminUser, AdminUserListResponse, QueuePreferences, QueuePreferencesUpdate
from sales_intelligence.services.audit import AuditService
from sales_intelligence.services.queue import QueueService
from sales_intelligence.services.user_directory import SupabaseUserDirectory


class AdminController:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/admin/users", self.list_admin_users, methods=["GET"], response_model=AdminUserListResponse, tags=["admin"])
        self.router.add_api_route("/users/{user_id}/queue-preferences", self.update_user_preferences, methods=["PATCH"], response_model=QueuePreferences, tags=["queue"])

    def list_admin_users(
        self,
        service: QueueService = Depends(queue_service),
        directory: SupabaseUserDirectory = Depends(user_directory),
        user: AuthUser = Depends(require_roles("admin")),
    ) -> AdminUserListResponse:
        require_authenticated_queue_user(user)
        import sys
        try:
            print(f"DEBUG: Using pooler connection", file=sys.stderr)
            print(f"DEBUG: Calling list_queue_users()", file=sys.stderr)
            queue_users = {item["user_id"]: item for item in service.list_queue_users()}
            print(f"DEBUG: Got {len(queue_users)} queue users", file=sys.stderr)
            print(f"DEBUG: Calling directory.list_users()", file=sys.stderr)
            auth_users = directory.list_users()
            print(f"DEBUG: Got {len(auth_users)} auth users", file=sys.stderr)
        except RuntimeError as exc:
            print(f"ERROR RuntimeError: {exc}", file=sys.stderr)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            print(f"ERROR httpx.HTTPError: {exc}", file=sys.stderr)
            raise HTTPException(status_code=503, detail="Unable to list Supabase users") from exc
        except Exception as exc:
            print(f"ERROR Unexpected: {type(exc).__name__}: {exc}", file=sys.stderr)
            raise

        identities = {item["user_id"]: item for item in auth_users}
        for user_id, item in queue_users.items():
            identities.setdefault(user_id, {}).update(item)
        result: list[AdminUser] = []
        for user_id in sorted(identities):
            item = {
                "user_id": user_id,
                "email": None,
                "display_name": None,
                "role": "authenticated",
                "min_exposure_score": 60,
                "page_size": 1,
                "assigned_count": 0,
            }
            item.update(queue_users.get(user_id, {}))
            item.update(identities[user_id])
            result.append(AdminUser.model_validate(item))
        return AdminUserListResponse(items=result, count=len(result))

    def update_user_preferences(
        self,
        user_id: str,
        preferences: QueuePreferencesUpdate,
        service: QueueService = Depends(queue_service),
        user: AuthUser = Depends(require_roles("admin")),
        audit: AuditService = Depends(audit_service),
    ) -> QueuePreferences:
        require_authenticated_queue_user(user)
        try:
            result = service.update_queue_preferences(user_id, min_exposure_score=preferences.min_exposure_score)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit.record(
            user_id=user.user_id,
            role=user.role,
            action="update_queue_preferences",
            resource_type="user",
            resource_id=user_id,
            metadata={"min_exposure_score": preferences.min_exposure_score},
        )
        return QueuePreferences.model_validate(result)


def build_admin_router() -> APIRouter:
    return AdminController().router