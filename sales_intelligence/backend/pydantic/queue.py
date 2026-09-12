from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from sales_intelligence.backend.pydantic.company import Company


Disposition = Literal[
    "not_contacted",
    "call_attempted",
    "connected",
    "qualified",
    "disqualified",
    "nurture",
    "bad_data",
    "do_not_contact",
]


class QueuePreferences(BaseModel):
    min_exposure_score: int = Field(ge=0, le=100)
    page_size: Literal[1] = 1


class QueuePreferencesUpdate(BaseModel):
    min_exposure_score: int = Field(ge=0, le=100)


class AdminUser(BaseModel):
    user_id: str
    email: str | None = None
    display_name: str | None = None
    role: str = "authenticated"
    min_exposure_score: int = Field(ge=0, le=100)
    page_size: Literal[1] = 1
    assigned_count: int = Field(ge=0)


class AdminUserListResponse(BaseModel):
    items: list[AdminUser]
    count: int


class QueueLead(BaseModel):
    company: Company
    status: str
    disposition: Disposition | None = None
    notes: str | None = None
    claimed_at: datetime | None = None
    next_follow_up_at: datetime | None = None


class QueueNextResponse(BaseModel):
    lead: QueueLead | None = None
    min_exposure_score: int = Field(ge=0, le=100)
    assigned_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    message: str


class QueueListResponse(BaseModel):
    items: list[QueueLead]
    count: int
    page: int
    page_size: int
    has_more: bool


class DispositionUpdate(BaseModel):
    disposition: Disposition
    notes: str | None = Field(default=None, max_length=4000)
    next_follow_up_at: datetime | None = None


class CallActivityRequest(BaseModel):
    outcome: Disposition
    notes: str | None = Field(default=None, max_length=4000)
    next_follow_up_at: datetime | None = None