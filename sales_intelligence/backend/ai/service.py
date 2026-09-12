from __future__ import annotations

import time
from pathlib import Path

from sales_intelligence.backend.ai.provider import LLMProvider, ProviderResponse
from sales_intelligence.backend.ai.repository import SqlAlchemyAssessmentRepository
from sales_intelligence.backend.pydantic import AssessmentResponse
from sales_intelligence.backend.ai.tracing import NullTraceSink, TraceSink
from sales_intelligence.backend.repositories import CompanyRepository


class AIQualificationService:
    def __init__(
        self,
        company_repository: CompanyRepository,
        assessment_repository: SqlAlchemyAssessmentRepository,
        provider: LLMProvider,
        prompt_path: str | Path,
        prompt_version: str = "account-scoring-v1",
        min_deterministic_score: int = 0,
        trace_sink: TraceSink | None = None,
    ):
        self.company_repository = company_repository
        self.assessment_repository = assessment_repository
        self.provider = provider
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        self.prompt_version = prompt_version
        self.min_deterministic_score = min_deterministic_score
        self.trace_sink = trace_sink or NullTraceSink()

    def assess(self, company_id: str, *, user_id: str | None = None, role: str | None = None) -> AssessmentResponse:
        company = self.company_repository.get_company(company_id, user_id=user_id, role=role)
        if company is None:
            raise LookupError("Company not found")
        if company.get("security_score", 0) < self.min_deterministic_score:
            raise PermissionError("Company does not meet the deterministic assessment threshold")

        cached = self.assessment_repository.get_latest(company_id, self.prompt_version)
        if cached:
            return AssessmentResponse(
                company_id=company_id,
                ai_score=cached.ai_score,
                priority=cached.priority,
                confidence=float(getattr(cached, "confidence", 0.0) or 0.0),
                reasoning=cached.reasoning or "",
                model=cached.model,
                prompt_version=cached.prompt_version,
                cached=True,
                latency_ms=cached.latency_ms,
                cost_usd=float(cached.cost_usd) if cached.cost_usd is not None else None,
                input_tokens=getattr(cached, "input_tokens", None),
                output_tokens=getattr(cached, "output_tokens", None),
            )

        started = time.perf_counter()
        request_payload = {
            "company": company,
            "prompt_version": self.prompt_version,
        }
        try:
            provider_response = self.provider.qualify(company, self.prompt)
            if isinstance(provider_response, ProviderResponse):
                result = provider_response.result
            else:
                # Compatibility for simple providers used by integrations/tests.
                result = provider_response
                provider_response = ProviderResponse(result)
        except Exception as exc:
            self.trace_sink.record(
                feature="account_scoring",
                model=self.provider.model,
                prompt_version=self.prompt_version,
                request=request_payload,
                response=None,
                latency_ms=round((time.perf_counter() - started) * 1000),
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                decision=None,
                status="error",
                error=str(exc)[:2000],
            )
            raise
        latency_ms = round((time.perf_counter() - started) * 1000)
        self.trace_sink.record(
            feature="account_scoring",
            model=self.provider.model,
            prompt_version=self.prompt_version,
            request=request_payload,
            response=result.model_dump(),
            latency_ms=latency_ms,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            cost_usd=provider_response.cost_usd,
            decision=result.priority,
            status="success",
            error=None,
        )
        saved = self.assessment_repository.save(
            company_id=company_id,
            result=result.model_dump(),
            model=self.provider.model,
            prompt_version=self.prompt_version,
            latency_ms=latency_ms,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            cost_usd=provider_response.cost_usd,
        )
        return AssessmentResponse(
            company_id=company_id,
            **result.model_dump(),
            model=saved.model,
            prompt_version=saved.prompt_version,
            cached=False,
            latency_ms=latency_ms,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            cost_usd=provider_response.cost_usd,
        )
