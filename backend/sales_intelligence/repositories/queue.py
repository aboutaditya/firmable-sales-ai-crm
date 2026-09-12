from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.orm import sessionmaker

from sales_intelligence.models import CallActivity, Company, CompanyAssignment, CompanySignal, UserPreference
from sales_intelligence.repositories.companies import _company_dict


def _queue_dict(company: Company, signal: CompanySignal, assignment: CompanyAssignment) -> dict:
    return {
        "company": _company_dict(company, signal),
        "status": assignment.status,
        "disposition": assignment.disposition,
        "notes": assignment.notes,
        "claimed_at": assignment.claimed_at,
        "next_follow_up_at": assignment.next_follow_up_at,
    }


class PostgresQueueRepository:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def assign_company(self, company_id: str, user_id: str, assigned_by: str, team_id: str | None = None) -> None:
        with self.session_factory.begin() as session:
            if session.get(Company, company_id) is None:
                raise LookupError("Company not found")
            active_assignments = session.execute(
                select(CompanyAssignment).where(
                    CompanyAssignment.company_id == company_id,
                    CompanyAssignment.user_id != user_id,
                    CompanyAssignment.status != "reassigned",
                )
            ).scalars().all()
            for active in active_assignments:
                active.status = "reassigned"
            assignment = session.get(CompanyAssignment, (company_id, user_id))
            if assignment is None:
                session.add(CompanyAssignment(company_id=company_id, user_id=user_id, assigned_by=assigned_by, team_id=team_id, status="assigned"))
            else:
                assignment.team_id = team_id
                assignment.assigned_by = assigned_by
                assignment.status = "assigned"
                assignment.disposition = "not_contacted"
                assignment.claimed_at = None
                assignment.next_follow_up_at = None
                assignment.notes = None

    def get_preferences(self, user_id: str) -> dict:
        with self.session_factory() as session:
            preference = session.get(UserPreference, user_id)
            if preference is None:
                return {"min_exposure_score": 60, "page_size": 1}
            return {"min_exposure_score": preference.min_exposure_score, "page_size": preference.page_size}

    def list_queue_users(self) -> list[dict]:
        with self.session_factory() as session:
            user_ids = set(session.scalars(select(UserPreference.user_id)).all())
            user_ids.update(session.scalars(select(CompanyAssignment.user_id)).all())
            result: list[dict] = []
            for user_id in sorted(user_ids):
                preference = session.get(UserPreference, user_id)
                assigned_count = session.scalar(
                    select(func.count()).select_from(CompanyAssignment).where(
                        CompanyAssignment.user_id == user_id,
                        CompanyAssignment.status != "reassigned",
                    )
                ) or 0
                result.append({
                    "user_id": user_id,
                    "email": None,
                    "display_name": None,
                    "role": "authenticated",
                    "min_exposure_score": preference.min_exposure_score if preference else 60,
                    "page_size": preference.page_size if preference else 1,
                    "assigned_count": assigned_count,
                })
            return result

    def queue_status(self, user_id: str) -> dict:
        preferences = self.get_preferences(user_id)
        threshold = preferences["min_exposure_score"]
        with self.session_factory() as session:
            assigned_count = session.scalar(
                select(func.count()).select_from(CompanyAssignment).where(
                    CompanyAssignment.user_id == user_id,
                    CompanyAssignment.status != "reassigned",
                )
            ) or 0
            unassigned = ~exists(
                select(CompanyAssignment.company_id).where(
                    CompanyAssignment.company_id == Company.id,
                    CompanyAssignment.status != "reassigned",
                )
            )
            eligible_count = session.scalar(
                select(func.count())
                .select_from(Company)
                .where(
                    Company.is_active.is_(True),
                    unassigned,
                )
            ) or 0
        return {
            "min_exposure_score": threshold,
            "assigned_count": assigned_count,
            "eligible_count": eligible_count,
        }

    def update_preferences(self, user_id: str, *, min_exposure_score: int) -> dict:
        with self.session_factory.begin() as session:
            preference = session.get(UserPreference, user_id)
            if preference is None:
                preference = UserPreference(user_id=user_id, min_exposure_score=min_exposure_score, page_size=1)
                session.add(preference)
            else:
                preference.min_exposure_score = min_exposure_score
                preference.page_size = 1
            return {"min_exposure_score": min_exposure_score, "page_size": 1}

    def next_assigned_company(self, user_id: str) -> dict | None:
        now = datetime.now(timezone.utc)
        with self.session_factory.begin() as session:
            unassigned = ~exists(
                select(CompanyAssignment.company_id).where(
                    CompanyAssignment.company_id == Company.id,
                    CompanyAssignment.status != "reassigned",
                )
            )
            statement = (
                select(Company, CompanySignal)
                .join(CompanySignal, CompanySignal.company_id == Company.id)
                .where(
                    Company.is_active.is_(True),
                    unassigned,
                )
                .order_by(Company.security_score.desc(), Company.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            row = session.execute(statement).first()
            if row is None:
                return None
            company, signal = row
            assignment = session.get(CompanyAssignment, (company.id, user_id))
            if assignment is None:
                assignment = CompanyAssignment(
                    company_id=company.id,
                    user_id=user_id,
                    assigned_by=user_id,
                    status="in_progress",
                    disposition="not_contacted",
                    claimed_at=now,
                )
                session.add(assignment)
            else:
                assignment.assigned_by = user_id
                assignment.status = "in_progress"
                assignment.disposition = "not_contacted"
                assignment.claimed_at = assignment.claimed_at or now
                assignment.next_follow_up_at = None
                assignment.notes = None
            return _queue_dict(company, signal, assignment)

    def list_assigned_companies(self, user_id: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        filters = (
            Company.is_active.is_(True),
            CompanyAssignment.user_id == user_id,
            CompanyAssignment.status != "reassigned",
        )
        with self.session_factory() as session:
            count_statement = (
                select(func.count())
                .select_from(Company)
                .join(CompanySignal, CompanySignal.company_id == Company.id)
                .join(CompanyAssignment, CompanyAssignment.company_id == Company.id)
                .where(*filters)
            )
            total = session.execute(count_statement).scalar_one()
            statement = (
                select(Company, CompanySignal, CompanyAssignment)
                .join(CompanySignal, CompanySignal.company_id == Company.id)
                .join(CompanyAssignment, CompanyAssignment.company_id == Company.id)
                .where(*filters)
                .order_by(
                    case(
                        (CompanyAssignment.status == "in_progress", 0),
                        (CompanyAssignment.status == "assigned", 1),
                        (CompanyAssignment.status == "nurture", 2),
                        else_=3,
                    ),
                    Company.security_score.desc(),
                    Company.id.asc(),
                )
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(statement).all()
            return [_queue_dict(company, signal, assignment) for company, signal, assignment in rows], total

    def update_disposition(self, company_id: str, user_id: str, *, disposition: str, notes: str | None, next_follow_up_at: datetime | None) -> dict:
        with self.session_factory.begin() as session:
            assignment = session.get(CompanyAssignment, (company_id, user_id))
            if assignment is None or assignment.status == "reassigned":
                raise PermissionError("Company is not assigned to this user")
            assignment.disposition = disposition
            assignment.notes = notes
            assignment.next_follow_up_at = next_follow_up_at
            if disposition == "nurture":
                assignment.status = "nurture"
            elif disposition == "not_contacted":
                assignment.status = "assigned"
            elif disposition in {"call_attempted", "connected"}:
                assignment.status = "in_progress"
                assignment.last_contacted_at = datetime.now(timezone.utc)
            else:
                assignment.status = "completed"
                assignment.last_contacted_at = datetime.now(timezone.utc)
            row = session.execute(
                select(Company, CompanySignal).join(CompanySignal, CompanySignal.company_id == Company.id).where(Company.id == company_id)
            ).first()
            if row is None:
                raise LookupError("Company not found")
            return _queue_dict(row[0], row[1], assignment)

    def record_call(self, company_id: str, user_id: str, *, outcome: str, notes: str | None, next_follow_up_at: datetime | None) -> dict:
        with self.session_factory.begin() as session:
            assignment = session.get(CompanyAssignment, (company_id, user_id))
            if assignment is None or assignment.status == "reassigned":
                raise PermissionError("Company is not assigned to this user")
            session.add(CallActivity(company_id=company_id, user_id=user_id, outcome=outcome, notes=notes, next_follow_up_at=next_follow_up_at))
            assignment.disposition = outcome
            assignment.notes = notes
            assignment.next_follow_up_at = next_follow_up_at
            assignment.last_contacted_at = datetime.now(timezone.utc)
            assignment.status = "nurture" if outcome == "nurture" else "completed" if outcome in {"qualified", "disqualified", "bad_data", "do_not_contact"} else "in_progress"
            row = session.execute(
                select(Company, CompanySignal).join(CompanySignal, CompanySignal.company_id == Company.id).where(Company.id == company_id)
            ).first()
            if row is None:
                raise LookupError("Company not found")
            return _queue_dict(row[0], row[1], assignment)