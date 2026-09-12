from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from sales_intelligence.backend.models import AIAssessment


class SqlAlchemyAssessmentRepository:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def get_latest(self, company_id: str, prompt_version: str) -> AIAssessment | None:
        statement = (
            select(AIAssessment)
            .where(
                AIAssessment.company_id == company_id,
                AIAssessment.prompt_version == prompt_version,
            )
            .order_by(AIAssessment.created_at.desc(), AIAssessment.id.desc())
            .limit(1)
        )
        with self.session_factory() as session:
            return session.execute(statement).scalar_one_or_none()

    def save(
        self,
        *,
        company_id: str,
        result: dict,
        model: str,
        prompt_version: str,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> AIAssessment:
        assessment = AIAssessment(
            company_id=company_id,
            ai_score=result["ai_score"],
            priority=result["priority"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
        with self.session_factory.begin() as session:
            session.add(assessment)
            session.flush()
        return assessment
