from __future__ import annotations

from datetime import datetime

from sales_intelligence.backend.repositories import PostgresQueueRepository


class QueueService:
    """Business operations over the personal sales queue (assignments, call flow)."""

    def __init__(self, queue_repository: PostgresQueueRepository | None = None):
        self.queue_repository = queue_repository

    def assign_company(self, company_id: str, user_id: str, assigned_by: str, team_id: str | None = None) -> None:
        assign = getattr(self.queue_repository, "assign_company", None)
        if assign is None:
            raise RuntimeError("Company assignment requires PostgreSQL/Supabase")
        assign(company_id, user_id, assigned_by, team_id)

    def get_queue_preferences(self, user_id: str) -> dict:
        getter = getattr(self.queue_repository, "get_preferences", None)
        if getter is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return getter(user_id)

    def list_queue_users(self) -> list[dict]:
        getter = getattr(self.queue_repository, "list_queue_users", None)
        if getter is None:
            raise RuntimeError("Admin user management requires PostgreSQL/Supabase")
        return getter()

    def update_queue_preferences(self, user_id: str, *, min_exposure_score: int) -> dict:
        updater = getattr(self.queue_repository, "update_preferences", None)
        if updater is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return updater(user_id, min_exposure_score=min_exposure_score)

    def queue_status(self, user_id: str) -> dict:
        getter = getattr(self.queue_repository, "queue_status", None)
        if getter is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return getter(user_id)

    def next_assigned_company(self, user_id: str) -> dict | None:
        getter = getattr(self.queue_repository, "next_assigned_company", None)
        if getter is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return getter(user_id)

    def list_assigned_companies(self, user_id: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        getter = getattr(self.queue_repository, "list_assigned_companies", None)
        if getter is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return getter(user_id, limit, offset)

    def update_disposition(self, company_id: str, user_id: str, *, disposition: str, notes: str | None, next_follow_up_at: datetime | None) -> dict:
        updater = getattr(self.queue_repository, "update_disposition", None)
        if updater is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return updater(company_id, user_id, disposition=disposition, notes=notes, next_follow_up_at=next_follow_up_at)

    def record_call(self, company_id: str, user_id: str, *, outcome: str, notes: str | None, next_follow_up_at: datetime | None) -> dict:
        recorder = getattr(self.queue_repository, "record_call", None)
        if recorder is None:
            raise RuntimeError("Sales queue requires PostgreSQL/Supabase")
        return recorder(company_id, user_id, outcome=outcome, notes=notes, next_follow_up_at=next_follow_up_at)