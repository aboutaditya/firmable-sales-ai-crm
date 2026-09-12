"""Vercel Python serverless entrypoint for FastAPI backend."""

from sales_intelligence.main import app

__all__ = ["app"]