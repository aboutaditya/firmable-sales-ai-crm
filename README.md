# Sales Intelligence

An AI-assisted sales intelligence platform that ingests large volumes of
internet-exposure observations (Shodan-style JSONL), aggregates them into
company profiles, scores each company by its security-exposure risk, and lets
sales teams find, qualify, and work their best leads.

**Start here:** [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) maps each task requirement to what was built, where it lives, and how to use it.  
**System overview:** See [docs/HLD.md](docs/HLD.md) for architecture and [docs/HOW_YOU_BUILD.md](docs/HOW_YOU_BUILD.md) for design rationale.  
**Component details:** Per-component plans live in [docs/plan/](docs/plan/).

## What it offers

- **Streaming ETL pipeline** (`sales-intelligence etl`) — streams JSONL (plain,
  gzip, or zstd-compressed) from local files or remote object URLs, normalizes
  observations, folds them into company profiles, and exports Parquet or JSONL.
  Resumable via checkpoints and tracked through dataset run manifests.
- **Deterministic exposure scoring** — a versioned, fully configurable model
  (`backend/sales_intelligence/scoring.py`) that ranks companies by exposed
  RDP/databases/Exchange, vulnerabilities, EOL products, and security tags.
  Override weights with a JSON config, no code changes.
- **Ad-hoc query CLI** (`sales-intelligence query`) — filter a built dataset by
  country, minimum score, or company ID and print ranked JSON rows.
- **FastAPI backend** — analytics over Parquet (DuckDB) or PostgreSQL/Supabase
  (SQLAlchemy), with structured errors and `X-Request-ID` tracing.
- **AI workflows** — per-company account assessments, summaries, and outreach
  drafts through an LLM provider (OpenAI-compatible or OpenRouter), with
  caching and optional LLM-call tracing.
- **Sales queue** — reps claim and work assigned leads; dispositions and call
  activity are recorded and audited.
- **Admin + auth** — Supabase-compatible JWT authentication with role-based
  access (`admin`, `sales_manager`, `sales_rep`) and admin user management.
- **Next.js frontend** — searchable, ranked company dashboard with lead-queue
  workflows; a local-demo mode runs against the small bundled fixture.
- **Evaluations** — measurable account-scoring quality against a hand-labelled
  case set (`make eval-*`, see [evals/README.md](evals/README.md)).

## Repository layout

- `backend/sales_intelligence/` — ETL, scoring, API, services, models
- `frontend/` — Next.js sales interface
- `data/demo/` and `data/sample/` — small committed fixtures
- `docs/` — high-level design, component plans, deployment guide
- `evals/` — evaluation datasets, harnesses, and results
- `postman/` — ready-to-import API collection

## Prerequisites

- Python 3.10+
- Node.js (only if you use the frontend)
- A PostgreSQL/Supabase project (only for queue, admin, and AI features)

## Quick start (local demo)

The demo runs entirely offline: it builds a dataset from
`data/demo/observations.jsonl`, starts the API in Parquet-only mode, and skips
authentication.

```bash
cp .env.example .env    # defaults already work for the demo
make init               # install backend + frontend dependencies
make etl                # build data/processed/companies.parquet from demo data
make start              # API at http://127.0.0.1:8000, frontend at http://127.0.0.1:3000
```

Verify health and browse companies:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl "http://127.0.0.1:8000/api/v1/companies?min_score=60&limit=10"
```

Search `http://127.0.0.1:3000` for companies in the dashboard. An importable
Postman collection with every endpoint is in `postman/`.

## Configuration

Backend settings load from `.env` (see [`.env.example`](.env.example)):

| Variable | Purpose |
| --- | --- |
| `RAW_DATASET_URL` | Remote production source for `make etl` (JSONL / `.zst`) |
| `ANALYTICAL_DATASET` | Output Parquet path served by the API |
| `DATABASE_URL` | PostgreSQL/Supabase connection (enables queue, admin, audit) |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | LLM provider for assess/summary/outreach |
| `AUTH_REQUIRED` | `false` = open demo mode, `true` = JWT-protected routes |
| `SUPABASE_JWT_SECRET` / `SUPABASE_JWKS_URL` | Verify Supabase bearer tokens |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only key for the admin user list |
| `AI_RATE_LIMIT_PER_MINUTE` | Rate limit for AI endpoints |
| `SCORING_CONFIG_PATH` | JSON file overriding exposure-scoring weights |

Frontend variables live in `frontend/.env.local`
(see `frontend/.env.example`): `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and
`NEXT_PUBLIC_LOCAL_DEMO=true` for the offline demo.

## CLI reference

The `sales-intelligence` CLI (installed via `make init-backend`) has three commands:

```bash
# Build a dataset. Omit the source to use RAW_DATASET_URL; rerun to resume.
sales-intelligence etl data/demo/observations.jsonl \
  --output data/processed/demo-companies.parquet \
  --dataset-version demo-v1 --max-records 1000 \
  --checkpoint data/processed/demo-companies.parquet.checkpoint.json

# Query a built dataset.
sales-intelligence query data/processed/companies.parquet \
  --min-score 60 --country US --limit 20

# Sync qualified companies into PostgreSQL/Supabase (idempotent).
DATABASE_URL='postgresql://...' sales-intelligence sync \
  data/processed/companies.parquet --min-score 60 --dataset-version 2026-09-07 \
  --batch-size 1000
```

Apply database migrations first: `DATABASE_URL='postgresql://...' alembic -c backend/alembic.ini upgrade head`.

## API

The service is FastAPI; interactive docs at `http://127.0.0.1:8000/docs`.
All routes are under `/api/v1` (system routes are always public).

| Method | Route | Access |
| --- | --- | --- |
| GET | `/health`, `/health/live`, `/health/ready` | public |
| GET | `/companies` | manager/admin (reps use the queue) |
| GET | `/companies/{company_id}` | manager/admin/rep |
| POST | `/companies/{company_id}/assign` | manager/admin |
| POST | `/companies/{company_id}/assess` | manager/admin/rep |
| POST | `/companies/{company_id}/summary` | manager/admin/rep |
| POST | `/companies/{company_id}/outreach` | manager/admin/rep |
| GET/PATCH | `/me/preferences` | any authenticated user |
| GET | `/me/queue/next` | authenticated (claims the next lead) |
| GET | `/me/queue` | authenticated |
| POST | `/me/queue/{company_id}/disposition` | authenticated |
| POST | `/me/queue/{company_id}/calls` | authenticated |
| GET | `/admin/users` | admin |
| PATCH | `/users/{user_id}/queue-preferences` | admin |

List-company filters: `country`, `min_score`, `industry`,
`min_employee_count`, repeated `signal` (`vulnerability`, `critical`, `rdp`,
`database`, `exchange`, `eol`), `limit`, `offset`, and `cursor` for
pagination — a
`next_cursor` is returned and the frontend uses it to page.

### Authentication and roles

With `AUTH_REQUIRED=true`, requests must carry a Supabase-compatible JWT
(`Authorization: Bearer ...`); queue and admin endpoints always require a real
token. Health checks stay public. Company details and AI access respect the
caller's role and, for reps, their company assignment. Reps cannot browse
`/companies` — they work their assigned one-lead queue, and admins set each
rep's minimum exposure score via `/users/{user_id}/queue-preferences`.

### AI features

`/assess`, `/summary`, and `/outreach` need `DATABASE_URL` plus
`LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` configured together. The LLM
must produce strict JSON; results are cached in the database, and every call
can be traced to `data/traces/llm_calls.jsonl` or a Supabase Storage bucket.
Prompts live in `backend/sales_intelligence/prompts/`.

## Testing and evaluation

```bash
make test                # Python tests + frontend build
python -m pytest         # backend + eval test suites
make eval-openrouter     # v1 account-scoring predictions (resumable)
make eval-report         # precision/recall/F1 vs hand-labelled cases
make eval-compare        # v2 metrics vs the v1 baseline
```

## Deployment

Backend and frontend deploy to Vercel (the backend runs as a Python function
via `api/index.py` + `vercel.json`; the frontend is a separate project under
`frontend/`). PostgreSQL, authentication, and LLM-trace storage come from
Supabase. Full deployment instructions and environment references are in
[docs/plan/11-deployment.md](docs/plan/11-deployment.md).

Do not commit production datasets: `data/raw/` is ignored — commit only small
fixtures under `data/sample/`.