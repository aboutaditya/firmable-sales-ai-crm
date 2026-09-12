from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from sales_intelligence.backend.models import AIOutput


class SqlAlchemyAIOutputRepository:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def get_latest(self, company_id: str, feature: str, prompt_version: str) -> AIOutput | None:
        statement = (
            select(AIOutput)
            .where(
                AIOutput.company_id == company_id,
                AIOutput.feature == feature,
                AIOutput.prompt_version == prompt_version,
            )
            .order_by(AIOutput.created_at.desc(), AIOutput.id.desc())
            .limit(1)
        )
        with self.session_factory() as session:
            return session.execute(statement).scalar_one_or_none()

    def save(self, **values: object) -> AIOutput:
        output = AIOutput(**values)
        with self.session_factory.begin() as session:
            session.add(output)
            session.flush()
        return output
