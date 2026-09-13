from __future__ import annotations

from pathlib import Path

from sales_intelligence.repositories import CompanyRepository, ParquetCompanyRepository
from sales_intelligence.query import encode_cursor


class CompanyService:
    """Business operations over the company catalog (list, detail, pagination)."""

    def __init__(
        self,
        dataset_path: str | Path | None = None,
        repository: CompanyRepository | None = None,
    ):
        if repository is None and dataset_path is None:
            raise ValueError("dataset_path or repository is required")
        self.repository = repository or ParquetCompanyRepository(Path(dataset_path))

    def list_companies(
        self,
        *,
        country: str | None = None,
        min_score: int | None = None,
        industry: str | None = None,
        min_employee_count: int | None = None,
        signals: list[str] | None = None,
        cursor: str | None = None,
        limit: int = 100,
        offset: int = 0,
        user_id: str | None = None,
        role: str | None = None,
    ) -> list[dict]:
        return self.repository.list_companies(
            country=country,
            min_score=min_score,
            industry=industry,
            min_employee_count=min_employee_count,
            signals=signals,
            cursor=cursor,
            limit=limit,
            offset=offset,
            user_id=user_id,
            role=role,
        )

    @staticmethod
    def cursor_for(items: list[dict], limit: int) -> str | None:
        return encode_cursor(items[-1]) if len(items) == limit and items else None

    def get_company(self, company_id: str, *, user_id: str | None = None, role: str | None = None) -> dict | None:
        return self.repository.get_company(company_id, user_id=user_id, role=role)