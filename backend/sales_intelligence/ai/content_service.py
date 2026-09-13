from __future__ import annotations

import logging
import time
from pathlib import Path

from sales_intelligence.ai.provider import LLMProvider, TextProviderResponse
from sales_intelligence.ai.tracing import NullTraceSink, TraceSink
from sales_intelligence.repositories import CompanyRepository

logger = logging.getLogger(__name__)


class AIContentService:
    def __init__(self, company_repository: CompanyRepository, output_repository, provider: LLMProvider, prompt_root: str | Path, min_deterministic_score: int = 60, trace_sink: TraceSink | None = None):
        self.company_repository = company_repository
        self.output_repository = output_repository
        self.provider = provider
        self.prompt_root = Path(prompt_root)
        self.min_deterministic_score = min_deterministic_score
        self.trace_sink = trace_sink or NullTraceSink()

    def generate(self, company_id: str, feature: str, *, user_id: str | None = None, role: str | None = None) -> dict:
        logger.info(f"generate: feature={feature}, company_id={company_id}, user_id={user_id}")
        if feature not in {"company_summary", "outreach"}:
            logger.error(f"generate: unsupported feature={feature}")
            raise ValueError("unsupported AI content feature")
        logger.debug(f"generate: fetching company data for company_id={company_id}")
        company = self.company_repository.get_company(company_id, user_id=user_id, role=role)
        if company is None:
            logger.warning(f"generate: company not found for company_id={company_id}")
            raise LookupError("Company not found")
        if company.get("security_score", 0) < self.min_deterministic_score:
            logger.warning(f"generate: company security_score below threshold for company_id={company_id}")
            raise PermissionError("Company does not meet the deterministic content threshold")
        prompt_version = f"{feature}-v1"
        logger.debug(f"generate: checking cache for company_id={company_id}, feature={feature}, prompt_version={prompt_version}")
        cached = self.output_repository.get_latest(company_id, feature, prompt_version)
        if cached:
            logger.info(f"generate: cache hit for company_id={company_id}, feature={feature}")
            return self._response(company_id, feature, cached, cached=True)

        logger.debug(f"generate: reading prompt from {self.prompt_root / feature / 'v1.txt'}")
        prompt = (self.prompt_root / feature / "v1.txt").read_text(encoding="utf-8")
        started = time.perf_counter()
        request_payload = {
            "company": company,
            "feature": feature,
            "prompt_version": prompt_version,
        }
        try:
            logger.debug(f"generate: calling LLM provider for feature={feature}, model={self.provider.model}")
            provider_response = self.provider.generate(company, prompt)
            if not isinstance(provider_response, TextProviderResponse):
                logger.error(f"generate: invalid response type from provider: {type(provider_response)}")
                raise TypeError("LLM provider returned an invalid text response")
            logger.debug(f"generate: LLM call succeeded")
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000)
            logger.error(f"generate: LLM provider error for feature={feature}: {type(exc).__name__}: {exc}", exc_info=True)
            self.trace_sink.record(
                feature=feature,
                model=self.provider.model,
                prompt_version=prompt_version,
                request=request_payload,
                response=None,
                latency_ms=latency_ms,
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                decision=None,
                status="error",
                error=str(exc)[:2000],
            )
            raise
        latency_ms = round((time.perf_counter() - started) * 1000)
        logger.info(f"generate: LLM call completed in {latency_ms}ms for feature={feature}")
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
        logger.debug(f"generate: saving output to repository for company_id={company_id}, feature={feature}")
        try:
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
            logger.info(f"generate: output saved successfully for company_id={company_id}, feature={feature}")
        except Exception as exc:
            logger.error(f"generate: failed to save output for company_id={company_id}, feature={feature}: {type(exc).__name__}: {exc}", exc_info=True)
            raise
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
