from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "Sales Intelligence API"
    api_prefix: str = "/api/v1"
    analytical_dataset: Path = Path("data/processed/companies.parquet")
    raw_dataset_url: str | None = None
    database_url: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_input_cost_per_1k: float | None = None
    llm_output_cost_per_1k: float | None = None
    llm_http_referer: str | None = None
    llm_app_title: str | None = None
    llm_max_retries: int = 2
    llm_timeout_seconds: float = 60.0
    llm_trace_path: Path = Path("data/traces/llm_calls.jsonl")
    llm_trace_backend: str = "jsonl"
    llm_trace_bucket: str = "llm-traces"
    ai_min_score: int = 0
    cors_origins: tuple[str, ...] = ()
    ai_rate_limit_per_minute: int = 30
    auth_required: bool = False
    supabase_jwt_secret: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str | None = None
    supabase_jwks_url: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            api_prefix=os.getenv("API_PREFIX", cls.api_prefix),
            analytical_dataset=Path(
                os.getenv("ANALYTICAL_DATASET", str(cls.analytical_dataset))
            ),
            raw_dataset_url=os.getenv("RAW_DATASET_URL"),
            database_url=os.getenv("DATABASE_URL"),
            llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
            llm_base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENROUTER_BASE_URL"),
            llm_model=os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL"),
            llm_input_cost_per_1k=_optional_float(os.getenv("LLM_INPUT_COST_PER_1K") or os.getenv("OPENROUTER_INPUT_COST_PER_1K")),
            llm_output_cost_per_1k=_optional_float(os.getenv("LLM_OUTPUT_COST_PER_1K") or os.getenv("OPENROUTER_OUTPUT_COST_PER_1K")),
            llm_http_referer=os.getenv("LLM_HTTP_REFERER") or os.getenv("OPENROUTER_HTTP_REFERER"),
            llm_app_title=os.getenv("LLM_APP_TITLE") or os.getenv("OPENROUTER_APP_TITLE", "Sales Intelligence"),
            llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
            llm_trace_path=Path(os.getenv("LLM_TRACE_PATH", "data/traces/llm_calls.jsonl")),
            llm_trace_backend=os.getenv("LLM_TRACE_BACKEND", "jsonl"),
            llm_trace_bucket=os.getenv("LLM_TRACE_BUCKET", "llm-traces"),
            ai_min_score=int(os.getenv("AI_MIN_SCORE", "0")),
            cors_origins=tuple(
                origin.strip()
                for origin in os.getenv("CORS_ORIGINS", "").split(",")
                if origin.strip()
            ),
            ai_rate_limit_per_minute=int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "30")),
            auth_required=os.getenv("AUTH_REQUIRED", "false").lower() == "true",
            supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET"),
            supabase_url=os.getenv("SUPABASE_URL") or _supabase_url_from_issuer(os.getenv("SUPABASE_JWT_ISSUER")),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated"),
            supabase_jwt_issuer=os.getenv("SUPABASE_JWT_ISSUER"),
            supabase_jwks_url=os.getenv("SUPABASE_JWKS_URL"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> None:
        if self.ai_rate_limit_per_minute < 1:
            raise ValueError("AI_RATE_LIMIT_PER_MINUTE must be greater than zero")
        llm_values = (self.llm_api_key, self.llm_base_url, self.llm_model)
        if any(llm_values) and not all(llm_values):
            raise ValueError("LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL must be configured together")
        if self.auth_required and not (self.supabase_jwt_secret or self.supabase_jwks_url):
            raise ValueError("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL is required when AUTH_REQUIRED=true")


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _supabase_url_from_issuer(issuer: str | None) -> str | None:
    if issuer and issuer.endswith("/auth/v1"):
        return issuer[:-8]
    return None
