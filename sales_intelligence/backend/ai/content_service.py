from __future__ import annotations

import time
from pathlib import Path

from sales_intelligence.backend.ai.provider import LLMProvider, TextProviderResponse
from sales_intelligence.backend.ai.tracing import NullTraceSink, TraceSink
from sales_intelligence.backend.repositories import CompanyRepository


class AIContentService:
    def __init__(self, company_repository: CompanyRepository, output_repository, provider: LLMProvider, prompt_root: str | Path, min_deterministic_score: int = 60, trace_sink: TraceSink | None = None):
        self.company_repository = company_repository
        self.output_repository = output_repository
        self.provider = provider
        self.prompt_root = Path(prompt_root)
        self.min_deterministic_score = min_deterministic_score
        self.trace_sink = trace_sink or NullTraceSink()

    def generate(self, company_id: str, feature: str, *, user_id: str | None = None, role: str | None = None) -> dict:
        if feature not in {"company_summary", "outreach"}:
            raise ValueError("unsupported AI content feature")
        company = self.company_repository.get_company(company_id, user_id=user_id, role=role)
        if company is None:
            raise LookupError("Company not found")
        if company.get("security_score", 0) < self.min_deterministic_score:
            raise PermissionError("Company does not meet the deterministic content threshold")
        prompt_version = f"{feature}-v1"
        cached = self.output_repository.get_latest(company_id, feature, prompt_version)
        if cached:
            return self._response(company_id, feature, cached, cached=True)

        prompt = (self.prompt_root / feature / "v1.txt").read_text(encoding="utf-8")
        started = time.perf_counter()
        request_payload = {
            "company": company,
            "feature": feature,
            "prompt_version": prompt_version,
        }
        try:
            provider_response = self.provider.generate(company, prompt)
            if not isinstance(provider_response, TextProviderResponse):
                raise TypeError("LLM provider returned an invalid text response")
        except Exception as exc:
            self.trace_sink.record(
                feature=feature,
                model=self.provider.model,
                prompt_version=prompt_version,
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
            feature=feature,
            model=self.provider.model,
            prompt_version=prompt_version,
            request=request_payload,
            response={"content": provider_response.content},
            latency_ms=latency_ms,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            cost_usd=provider_response.cost_usd,
            decision="generated",
            status="success",
            error=None,
        )
        saved = self.output_repository.save(
            company_id=company_id,
            feature=feature,
            content=provider_response.content,
            model=self.provider.model,
            prompt_version=prompt_version,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            cost_usd=provider_response.cost_usd,
            latency_ms=latency_ms,
        )
        return self._response(company_id, feature, saved, cached=False)

    @staticmethod
    def _response(company_id: str, feature: str, output, *, cached: bool) -> dict:
        return {
            "company_id": company_id,
            "feature": feature,
            "content": output.content,
            "model": output.model,
            "prompt_version": output.prompt_version,
            "cached": cached,
            "input_tokens": output.input_tokens,
            "output_tokens": output.output_tokens,
            "cost_usd": float(output.cost_usd) if output.cost_usd is not None else None,
            "latency_ms": output.latency_ms,
        }
