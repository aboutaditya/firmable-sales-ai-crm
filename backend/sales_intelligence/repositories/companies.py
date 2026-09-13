from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sqlalchemy import and_, select
from sqlalchemy.orm import sessionmaker

from sales_intelligence.models import Company, CompanyAssignment, CompanySignal
from sales_intelligence.query import query_companies


class CompanyRepository(Protocol):
    def list_companies(self, *, country: str | None = None, min_score: int | None = None, limit: int = 100, offset: int = 0, user_id: str | None = None, role: str | None = None) -> list[dict]: ...
    def get_company(self, company_id: str, *, user_id: str | None = None, role: str | None = None) -> dict | None: ...


def _company_dict(company: Company, signal: CompanySignal) -> dict:
    return {
        "company_id": company.id,
        "domain": company.domain,
        "organization": company.organization,
        "country": company.country,
        "city": company.city,
        "industry": company.industry,
        "employee_count": company.employee_count,
        "security_score": company.security_score,
        "score_version": company.score_version,
        "asset_count": signal.asset_count,
        "unique_ip_count": signal.unique_ip_count,
        "unique_domain_count": signal.unique_domain_count,
        "vulnerability_count": signal.vulnerability_count,
        "critical_vulnerability_count": signal.critical_vulnerability_count,
        "eol_product_count": signal.eol_product_count,
        "exposed_rdp": signal.exposed_rdp,
        "exposed_database": signal.exposed_database,
        "exposed_exchange": signal.exposed_exchange,
        "security_tag_count": signal.security_tag_count,
    }


class ParquetCompanyRepository:
    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)

    def list_companies(self, **filters: object) -> list[dict]:
        user_id = filters.pop("user_id", None)
        role = filters.pop("role", None)
        if role == "sales_rep":
            return []
        return query_companies(self.dataset_path, **filters)

    def get_company(self, company_id: str, *, user_id: str | None = None, role: str | None = None) -> dict | None:
        if role == "sales_rep":
            return None
        matches = query_companies(self.dataset_path, company_id=company_id, limit=1)
        return matches[0] if matches else None


class PostgresCompanyRepository:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def list_companies(self, *, country: str | None = None, min_score: int | None = None, industry: str | None = None, min_employee_count: int | None = None, signals: list[str] | None = None, cursor: str | None = None, limit: int = 100, offset: int = 0, user_id: str | None = None, role: str | None = None) -> list[dict]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        conditions = [Company.is_active.is_(True)]
        if country:
            conditions.append(Company.country == country)
        if min_score is not None:
            conditions.append(Company.security_score >= min_score)
        if industry:
            conditions.append(Company.industry == industry)
        if min_employee_count is not None:
            conditions.append(Company.employee_count >= min_employee_count)
        if cursor:
            from sales_intelligence.query import decode_cursor
            cursor_score, cursor_id = decode_cursor(cursor)
            conditions.append((Company.security_score < cursor_score) | ((Company.security_score == cursor_score) & (Company.id > cursor_id)))
        signal_columns = {"rdp": CompanySignal.exposed_rdp, "database": CompanySignal.exposed_database, "exchange": CompanySignal.exposed_exchange}
        count_columns = {"vulnerability": CompanySignal.vulnerability_count, "critical": CompanySignal.critical_vulnerability_count, "eol": CompanySignal.eol_product_count}
        for signal in signals or []:
            if signal in signal_columns:
                conditions.append(signal_columns[signal].is_(True))
            elif signal in count_columns:
                conditions.append(count_columns[signal] > 0)
            else:
                raise ValueError(f"unsupported signal: {signal}")
        if role == "sales_rep":
            if not user_id:
                return []
            conditions.append(
                Company.id.in_(
                    select(CompanyAssignment.company_id).where(
                        CompanyAssignment.user_id == user_id,
                        CompanyAssignment.status != "reassigned",
                    )
                )
            )
        statement = (
            select(Company, CompanySignal)
            .join(CompanySignal, CompanySignal.company_id == Company.id)
            .where(and_(*conditions))
            .order_by(Company.security_score.desc(), Company.id.asc())
            .limit(limit)
            .offset(offset)
        )
        with self.session_factory() as session:
            rows = session.execute(statement).all()
            return [_company_dict(company, signal) for company, signal in rows]

    def get_company(self, company_id: str, *, user_id: str | None = None, role: str | None = None) -> dict | None:
        statement = (
            select(Company, CompanySignal)
            .join(CompanySignal, CompanySignal.company_id == Company.id)
            .where(Company.id == company_id, Company.is_active.is_(True))
        )
        if role == "sales_rep":
            if not user_id:
                return None
            statement = statement.where(
                Company.id.in_(
                    select(CompanyAssignment.company_id).where(
                        CompanyAssignment.user_id == user_id,
                        CompanyAssignment.status != "reassigned",
                    )
                )
            )
        with self.session_factory() as session:
            row = session.execute(statement).first()
            return _company_dict(*row) if row else None