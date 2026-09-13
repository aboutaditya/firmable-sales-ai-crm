from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from sales_intelligence.pydantic import QualificationResult

logger = logging.getLogger(__name__)


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ProviderResponse:
    result: QualificationResult
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class TextProviderResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMProvider(Protocol):
    model: str

    def qualify(self, company: dict, prompt: str) -> ProviderResponse: ...

    def generate(self, company: dict, prompt: str) -> TextProviderResponse: ...


_QUALIFICATION_SCHEMA_HINT = (
    'Return only a JSON object with keys "ai_score" (integer 0-100), '
    '"priority" ("HIGH" | "MEDIUM" | "LOW"), "confidence" (number 0-1), '
    'and "reasoning" (non-empty string). Do not wrap it in prose or code fences.'
)

_MAX_CORRECTIVE_RETRIES = 1


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    max_retries: int = 2
    input_cost_per_1k: float | None = None
    output_cost_per_1k: float | None = None
    http_referer: str | None = None
    app_title: str | None = None

    def qualify(self, company: dict, prompt: str) -> ProviderResponse:
        content, input_tokens, output_tokens, cost_usd = self._complete(company, prompt)
        result = _parse_qualification(content)
        if result is not None:
            return ProviderResponse(result, input_tokens, output_tokens, cost_usd)
        for _ in range(_MAX_CORRECTIVE_RETRIES):
            followup = (
                "Your previous answer was not valid JSON: \n"
                f"{content[:2000]!r}\n\n{_QUALIFICATION_SCHEMA_HINT}"
            )
            content, more_input, more_output, more_cost = self._complete(company, prompt, followup=followup)
            result = _parse_qualification(content)
            if result is not None:
                return ProviderResponse(
                    result,
                    _sum_usage(input_tokens, more_input),
                    _sum_usage(output_tokens, more_output),
                    _sum_cost(cost_usd, more_cost),
                )
        raise ValueError("LLM provider did not return a valid qualification JSON response")

    def generate(self, company: dict, prompt: str) -> TextProviderResponse:
        content, input_tokens, output_tokens, cost_usd = self._complete(company, prompt)
        return TextProviderResponse(content, input_tokens, output_tokens, cost_usd)

    def _complete(
        self,
        company: dict,
        prompt: str,
        followup: str | None = None,
    ) -> tuple[str, int | None, int | None, float | None]:
        rendered_prompt = prompt.replace(
            "{{company_profile}}", json.dumps(company, sort_keys=True, default=str)
        )
        messages = [{"role": "user", "content": rendered_prompt}]
        if followup:
            messages.append({"role": "user", "content": followup})
        url = self.base_url.rstrip("/") + "/chat/completions"
        response = None
        for attempt in range(self.max_retries + 1):
            try:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                if self.http_referer:
                    headers["HTTP-Referer"] = self.http_referer
                if self.app_title:
                    headers["X-OpenRouter-Title"] = self.app_title
                response = httpx.post(
                    url,
                    headers=headers,
                    json={
                        "model": self.model,
                        "temperature": 0,
                        "messages": messages,
                    },
                    timeout=self.timeout_seconds,
                )
                if response.status_code not in {408, 429, 500, 502, 503, 504}:
                    if response.is_error:
                        raise _provider_error(response)
                    break
                if attempt == self.max_retries:
                    raise _provider_error(response)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.max_retries:
                    raise
            time.sleep(2**attempt)
        if response is None:
            raise RuntimeError("LLM provider returned no response")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            logger.error(f"LLM provider returned invalid JSON: {response.text[:500]}")
            raise
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as exc:
            logger.error(f"LLM provider response missing expected structure. Response: {json.dumps(payload, default=str)[:1000]}")
            raise KeyError(f"choices: {exc}") from exc
        usage = payload.get("usage") or {}
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        cost_usd = None
        if input_tokens is not None and output_tokens is not None:
            if self.input_cost_per_1k is not None and self.output_cost_per_1k is not None:
                cost_usd = round(
                    (input_tokens / 1000) * self.input_cost_per_1k
                    + (output_tokens / 1000) * self.output_cost_per_1k,
                    8,
                )
        return content, input_tokens, output_tokens, cost_usd


def _parse_qualification(content: str) -> QualificationResult | None:
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        return QualificationResult.model_validate(json.loads(content))
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def _sum_usage(first: int | None, second: int | None) -> int | None:
    if first is None and second is None:
        return None
    return (first or 0) + (second or 0)


def _sum_cost(first: float | None, second: float | None) -> float | None:
    if first is None and second is None:
        return None
    return round((first or 0.0) + (second or 0.0), 8)


def _provider_error(response: httpx.Response) -> LLMProviderError:
    """Convert provider errors into a safe, actionable application error."""
    message = response.text.strip()
    try:
        payload = response.json()
        provider_error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(provider_error, dict):
            message = str(provider_error.get("message") or provider_error.get("code") or message)
        elif isinstance(provider_error, str):
            message = provider_error
    except ValueError:
        pass
    if not message:
        message = "the provider returned no error details"
    return LLMProviderError(
        f"LLM provider returned HTTP {response.status_code}: {message[:500]}",
        status_code=response.status_code,
    )
