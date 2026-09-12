"""Vercel Python serverless entrypoint for FastAPI backend."""

try:
    from sales_intelligence.main import app
except Exception as e:
    # Create a fallback app if import fails
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"error": str(e), "type": type(e).__name__}

    @app.get("/")
    async def root():
        return {"error": str(e), "type": type(e).__name__}

__all__ = ["app"]