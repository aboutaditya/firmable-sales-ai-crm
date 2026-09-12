from __future__ import annotations

from typing import Any

import httpx


class SupabaseUserDirectory:
    """Small adapter around the Supabase Auth Admin user listing endpoint."""

    def __init__(self, supabase_url: str | None, service_role_key: str | None):
        self.base_url = (supabase_url or "").rstrip("/")
        self.service_role_key = service_role_key

    def list_users(self) -> list[dict[str, Any]]:
        if not self.base_url or not self.service_role_key:
            return []
        response = httpx.get(
            f"{self.base_url}/auth/v1/admin/users",
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
            },
            params={"page": 1, "per_page": 1000},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        raw_users = payload.get("users", []) if isinstance(payload, dict) else payload
        users: list[dict[str, Any]] = []
        for item in raw_users or []:
            metadata = item.get("user_metadata") or {}
            app_metadata = item.get("app_metadata") or {}
            roles = app_metadata.get("roles") or []
            role = app_metadata.get("role") or (roles[0] if roles else item.get("role", "authenticated"))
            users.append({
                "user_id": str(item.get("id")),
                "email": item.get("email"),
                "display_name": metadata.get("full_name") or metadata.get("name"),
                "role": str(role),
            })
        return users
