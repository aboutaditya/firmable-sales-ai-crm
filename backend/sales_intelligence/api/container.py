from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from sales_intelligence.ai.content_repository import SqlAlchemyAIOutputRepository
from sales_intelligence.ai.content_service import AIContentService
from sales_intelligence.ai.provider import OpenAICompatibleProvider
from sales_intelligence.ai.repository import SqlAlchemyAssessmentRepository
from sales_intelligence.ai.service import AIQualificationService
from sales_intelligence.ai.tracing import JsonlTraceSink, NullTraceSink, TraceSink
from sales_intelligence.api.rate_limit import InMemoryRateLimiter
from sales_intelligence.config import Settings
from sales_intelligence.db.session import create_session_factory
from sales_intelligence.services.audit import AuditService
from sales_intelligence.services.companies import CompanyService
from sales_intelligence.services.queue import QueueService
from sales_intelligence.repositories import PostgresCompanyRepository, PostgresQueueRepository
from sales_intelligence.services.user_directory import SupabaseUserDirectory

_BACKEND_ROOT = Path(__file__).resolve().parents[1]

_STATE_KEYS = (
    "session_factory",
    "audit",
    "ai_rate_limiter",
    "company_service",
    "queue_service",
    "user_directory",
    "ai_qualification",
    "ai_content",
    "settings",
)


@dataclass
class AppContainer:
    """Composes every application service from configuration."""

    session_factory: object | None
    audit: AuditService
    ai_rate_limiter: InMemoryRateLimiter
    company_service: CompanyService
    queue_service: QueueService
    user_directory: SupabaseUserDirectory
    ai_qualification: AIQualificationService | None
    ai_content: AIContentService | None
    settings: Settings

    def apply_to(self, app: FastAPI) -> None:
        for key in _STATE_KEYS:
            setattr(app.state, key, getattr(self, key))


def build_trace_sink(settings: Settings) -> TraceSink:
    """Compose trace sink from settings."""
    if settings.llm_trace_backend == "jsonl":
        return JsonlTraceSink(settings.llm_trace_path)
    return NullTraceSink()


def build_container(settings: Settings) -> AppContainer:
    session_factory = create_session_factory(settings.database_url) if settings.database_url else None
    repository = PostgresCompanyRepository(session_factory) if session_factory else None
    queue_repository = PostgresQueueRepository(session_factory) if session_factory else None
    ai_qualification = None
    ai_content = None
    if session_factory and settings.llm_api_key and settings.llm_base_url and settings.llm_model:
        provider = OpenAICompatibleProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            input_cost_per_1k=settings.llm_input_cost_per_1k,
            output_cost_per_1k=settings.llm_output_cost_per_1k,
            http_referer=settings.llm_http_referer,
            app_title=settings.llm_app_title,
            max_retries=settings.llm_max_retries,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        trace_sink = build_trace_sink(settings)
        prompt_root = _BACKEND_ROOT / "prompts"
        ai_qualification = AIQualificationService(
            company_repository=repository,
            assessment_repository=SqlAlchemyAssessmentRepository(session_factory),
            provider=provider,
            prompt_path=prompt_root / "account_scoring/v1.txt",
            min_deterministic_score=settings.ai_min_score,
            trace_sink=trace_sink,
        )
        ai_content = AIContentService(
            company_repository=repository,
            output_repository=SqlAlchemyAIOutputRepository(session_factory),
            provider=provider,
            prompt_root=prompt_root,
            min_deterministic_score=settings.ai_min_score,
            trace_sink=trace_sink,
        )
    return AppContainer(
        session_factory=session_factory,
        audit=AuditService(session_factory),
        ai_rate_limiter=InMemoryRateLimiter(settings.ai_rate_limit_per_minute),
        company_service=CompanyService(settings.analytical_dataset, repository=repository),
        queue_service=QueueService(queue_repository=queue_repository),
        user_directory=SupabaseUserDirectory(settings.supabase_url, settings.supabase_service_role_key),
        ai_qualification=ai_qualification,
        ai_content=ai_content,
        settings=settings,
    )