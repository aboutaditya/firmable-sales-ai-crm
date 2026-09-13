from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_id: str
    domain: str
    organization: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    asset_count: int = Field(ge=0)
    unique_ip_count: int = Field(ge=0)
    unique_domain_count: int = Field(ge=0)
    vulnerability_count: int = Field(ge=0)
    critical_vulnerability_count: int = Field(ge=0)
    eol_product_count: int = Field(ge=0)
    exposed_rdp: bool = False
    exposed_database: bool = False
    exposed_exchange: bool = False
    security_tag_count: int = Field(ge=0)
    security_score: int = Field(ge=0, le=100)
    score_version: str


class CompanyListResponse(BaseModel):
    items: list[Company]
    limit: int
    offset: int
    count: int
    next_cursor: str | None = None


class AssignmentRequest(BaseModel):
    user_id: str
    team_id: str | None = None