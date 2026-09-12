from __future__ import annotations

from typing import Any

from sqlalchemy.orm import sessionmaker

from sales_intelligence.backend.models import AuditEvent


class AuditService:
    def __init__(self, session_factory: sessionmaker | None):
        self.session_factory = session_factory

    def record(
        self,
        *,
        user_id: str,
        role: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.session_factory is None:
            return
        event = AuditEvent(
            actor_user_id=user_id,
            actor_role=role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=metadata or {},
        )
        with self.session_factory.begin() as session:
            session.add(event)
