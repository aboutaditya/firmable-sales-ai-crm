# Sales Intelligence

This repository contains the first implementation slice of the AI Sales Intelligence platform described in [HLD Sales Intelligence.md](HLD%20Sales%20Intelligence.md).

Track implementation progress in the [implementation checklist](docs/implementation-checklist.md).

## Quick start

The easiest local workflow is through the root `Makefile`:

```bash
make init
make etl
make test
make start
```

This starts the API at `http://127.0.0.1:8000` and the frontend at
`http://127.0.0.1:3000`. Both `localhost:3000` and `127.0.0.1:3000` are allowed
origins for local development. Use `make help` to see all available targets. Database
migrations and AI features remain opt-in through `make migrate` and the relevant
environment variables.

```bash
python3 -m pip install -r requirements-dev.txt
cp .env.example .env
python3 -m unittest discover -s tests -v
sales-intelligence etl data/demo/observations.jsonl --output data/processed/demo-companies.parquet --dataset-version demo-v1
```

For a bounded remote smoke test, add `--max-records 1000`; the stream closes after that many observations. The default local/demo path uses the reproducible fixture in `data/demo/` so the dashboard is populated immediately.

The Makefile also enables resumable ETL checkpoints. If an ETL run is interrupted,
rerun `make etl` with the same source and dataset version to resume from the last
checkpoint. Change `MAX_RECORDS` to increase the total target, for example
`make etl MAX_RECORDS=2000`.

The ETL command writes Parquet by default. Remote dataset URLs and service credentials are loaded from `.env`; use [`.env.example`](.env.example) as the template. Local paths may still be passed for fixtures and tests.

```bash
python3 -m pip install -r requirements.txt
sales-intelligence etl data/demo/observations.jsonl --output data/processed/demo-companies.parquet --dataset-version demo-v1
```

For the real dataset, set `RAW_DATASET_URL` in `.env`. The reader accepts JSONL and `.zst`-compressed JSONL.

Apply the SQLAlchemy/Alembic migrations to Supabase/PostgreSQL, then sync only qualified companies:

```bash
DATABASE_URL='postgresql://...' ./scripts/apply_migrations.sh

sales-intelligence sync \
  data/processed/demo-companies.parquet \
  --min-score 60 \
  --dataset-version 2026-09-07
```

The sync reads `DATABASE_URL` from `.env` and is idempotent. Install the runtime dependencies when enabling this command:

```bash
python3 -m pip install -r requirements.txt
```

Application database access uses typed SQLAlchemy ORM models and sessions. DuckDB remains the SQL query engine for analytical Parquet data.

After changing an ORM model, create and apply a migration with:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Migrations live in `sales_intelligence/backend/migrations`; the old root-level SQL migration files are no longer used.

## Backend service

Run the API against the generated analytical dataset:

```bash
ANALYTICAL_DATASET=data/processed/demo-companies.parquet uvicorn sales_intelligence.backend.main:app --reload
```

When `DATABASE_URL` is set, the API automatically reads companies and signals from PostgreSQL/Supabase instead of Parquet:

```bash
DATABASE_URL='postgresql://...' uvicorn sales_intelligence.backend.main:app --host 0.0.0.0 --port 8000
```

Available endpoints:

- `GET /api/v1/health`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/companies?country=US&min_score=40&limit=100`
- `GET /api/v1/companies/{company_id}`
- `POST /api/v1/companies/{company_id}/assess`
- `POST /api/v1/companies/{company_id}/summary`
- `POST /api/v1/companies/{company_id}/outreach`
- `GET /api/v1/me/preferences`
- `PATCH /api/v1/me/preferences`
- `PATCH /api/v1/users/{user_id}/queue-preferences` (admin only)
- `GET /api/v1/me/queue/next`
- `POST /api/v1/me/queue/{company_id}/disposition`
- `POST /api/v1/me/queue/{company_id}/calls`
- `GET /docs`

The AI endpoints require `DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in `.env`. Account assessments use `prompts/account_scoring/v1.txt`; summaries and outreach use their corresponding versioned prompts and cache results in the application database.

Every response includes an `X-Request-ID` header. API validation and server errors use a consistent JSON error shape. Configure `CORS_ORIGINS` and `AI_RATE_LIMIT_PER_MINUTE` in `.env`.

Set `AUTH_REQUIRED=true` with `SUPABASE_JWT_SECRET` to protect business and AI routes with Supabase-compatible bearer JWTs. Health and readiness endpoints remain public. Set the backend-only `SUPABASE_SERVICE_ROLE_KEY` to let the admin panel list all Supabase Auth users; without it, the panel lists users known through queue assignments and preferences.

In the authenticated product flow, `/me/queue/next` claims the highest-scoring
company that is not yet assigned to anyone, assigns it to the caller, and
returns it for follow-up work. The per-user minimum exposure score is set by
admins (`PATCH /users/{user_id}/queue-preferences`) and surfaces in queue
status responses, but it does not gate which unassigned company is claimed
next. Representatives cannot browse `/companies`, and company detail/AI
access is checked against their assignment. Managers and admins can still use
the assignment endpoint to distribute accounts explicitly. With
`NEXT_PUBLIC_LOCAL_DEMO=true` the frontend intentionally falls back to the
small Parquet fixture and marks workflow writes as unavailable.

Measure the account-scoring quality against the 25-case hand-labelled set:

```bash
make eval-openrouter     # v1 predictions over all 25 cases (resumable)
make eval-report         # precision / recall / F1 / MAE vs the labels
make eval-openrouter-v2  # v2 predictions (resumable)
make eval-compare        # v2 metrics vs the v1 baseline
```

Recorded results and known weaknesses are described in
[`evals/README.md`](evals/README.md); the v2 run is currently measured on the
18-case overlap because the free-model daily quota interrupted the rest.

The `scripts/` files are compatibility wrappers. New automation should use the `sales-intelligence` command or import the application services directly.

The frontend is under [frontend/](frontend/). It uses Supabase browser authentication and expects `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

## Deployment

The runtime dependency manifest is [requirements.txt](requirements.txt). The included [Dockerfile](Dockerfile) installs it during the image build and starts the FastAPI service:

```bash
docker build -t sales-intelligence .
docker run --rm -p 8000:8000 \
  -e ANALYTICAL_DATASET=/app/data/processed/demo-companies.parquet \
  -v "$PWD/data/processed:/app/data/processed:ro" \
  sales-intelligence
```

For a non-container deployment, install dependencies before starting the service:

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install .
uvicorn sales_intelligence.backend.main:app --host 0.0.0.0 --port 8000
```

## Current scope

The current slice implements streaming ingestion, normalization, company
aggregation, deterministic exposure scoring, DuckDB queries,
Supabase/PostgreSQL synchronization, the FastAPI service, versioned AI
assessment/outreach workflows, and the Next.js sales interface. The local demo
uses `data/demo/observations.jsonl`; the provided remote dataset remains the
production source configured through `RAW_DATASET_URL`. The account-scoring
model is measured against a 25-case labelled set (`evals/README.md`).
Deployment instructions and configuration for Railway + Vercel are in
[`docs/deployment-plan.md`](docs/deployment-plan.md).

Do not commit the raw 11GB dataset. `data/raw/` is ignored; commit only small fixtures under `data/sample/`.
