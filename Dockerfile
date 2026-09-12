FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md alembic.ini ./
COPY sales_intelligence ./sales_intelligence
COPY prompts ./prompts

RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '8000') + '/api/v1/health/live', timeout=3)"

CMD ["sh", "-c", "uvicorn sales_intelligence.backend.main:app --host 0.0.0.0 --port ${PORT}"]
