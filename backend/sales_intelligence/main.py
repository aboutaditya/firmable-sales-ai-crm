from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from sales_intelligence.api.container import build_container
from sales_intelligence.api.errors import http_exception_handler, unhandled_exception_handler, validation_exception_handler
from sales_intelligence.api.middleware import RequestIdMiddleware
from sales_intelligence.api.routes import build_router
from sales_intelligence.config import Settings
from sales_intelligence.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    try:
        settings = settings or Settings.from_env()
        settings.validate()
        configure_logging(settings.log_level)
        container = build_container(settings)
    except Exception as e:
        import sys
        print(f"ERROR during app setup: {e}", file=sys.stderr)
        raise
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins) or ["*"],
        allow_credentials=bool(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    container.apply_to(app)
    app.include_router(build_router(settings), prefix=settings.api_prefix)
    return app


app = create_app()