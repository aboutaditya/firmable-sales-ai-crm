# Plan — Deployment, Operations & Tooling

Component: hosting topology, local tooling (Makefile), CI, and operating procedures.

Source of truth files:
- `api/index.py`, root `vercel.json`, `frontend/vercel.json`
- `Makefile`
- `.github/workflows/ci.yml`
- `backend/pyproject.toml`, `backend/requirements*.txt`
- `frontend/package.json`

## Hosting topology

| Unit | Host |
| --- | --- |
| Backend (FastAPI) | Vercel Python function — `api/index.py` exports the ASGI app; root `vercel.json` rewrites all traffic to it, `maxDuration: 60` (measured ~20s OpenRouter latency must not time out) |
| Frontend (Next.js) | Vercel project, root directory `frontend` |
| Database | Supabase Postgres (Alembic-managed schema) |
| Auth | Supabase Auth (JWT verified by the backend) |
| LLM traces | Supabase Storage bucket `llm-traces` |

The monorepo maps to two Vercel projects: backend root `.`, frontend root `frontend`.

## Backend environment

- `DATABASE_URL` (Supabase Postgres), `ANALYTICAL_DATASET` (bundled demo fixture, or object-storage artifact).
- `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` (OpenRouter; `LLM_*` fall back to `OPENROUTER_*`), `LLM_INPUT_COST_PER_1K`/`LLM_OUTPUT_COST_PER_1K`.
- `CORS_ORIGINS`, `AUTH_REQUIRED=true`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (backend only; the browser uses the anon key).
- `LLM_TRACE_BACKEND=both` (JSONL mirror + durable object storage), `LLM_TRACE_BUCKET=llm-traces`.

## Frontend environment

- `NEXT_PUBLIC_API_URL=https://<backend>/api/v1`.
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (browser-safe).
- `NEXT_PUBLIC_LOCAL_DEMO` unset for the real login + queue flow.

## Supabase setup

1. Create a project; run `alembic upgrade head` against its Postgres so all tables exist.
2. Enable email/password auth; seed demo users.
3. Create the private `llm-traces` bucket; the backend writes one object per call at `traces/<prompt>/<year>/<month>/<day>/`.

## Data refresh loop

```bash
make etl RAW_SOURCE="$RAW_DATASET_URL" DATASET=data/processed/companies.parquet \
  DATASET_VERSION=<date> MAX_RECORDS=<N>     # bounded, resumable
make sync DATASET=... DATASET_VERSION=<date> MIN_SCORE=50
```

Schedule ETL → sync on a cron (GitHub Actions cron or Vercel cron hitting a protected admin endpoint). Migrations are manual because Vercel has no deploy hook; they are idempotent.

## Makefile targets (local tooling)

| Target | Purpose |
| --- | --- |
| `make init` / `init-backend` / `init-frontend` | Install backend (requirements-dev + `-e backend`) and frontend (`npm install` + env from example) |
| `make etl` | Build the analytical Parquet dataset (checkpointed, tracked in dataset_runs) |
| `make migrate` | `alembic upgrade head` |
| `make sync` | Sync qualified companies to Postgres |
| `make eval-openrouter` / `-v2` | v1/v2 predictions (resumable) |
| `make eval-report` / `eval-compare` | Classification metrics + prompt comparison |
| `make eval-output-traces` / `-storage` / `-golden` | Grade generated content from traces/storage/golden set |
| `make start-backend` / `start-frontend` / `start` / `dev` | Run API (uvicorn :8000) and/or Next.js (:3000) |
| `make test` / `test-python` / `test-frontend` / `build-frontend` | Unit tests + compileall + frontend build |
| `make clean-cache` | Remove `__pycache__` / `.pytest_cache` |

Variables: `DATASET`, `RAW_SOURCE` (env URL or `data/demo/observations.jsonl`), `DATASET_VERSION`, `MAX_RECORDS`, `MIN_SCORE`, `BATCH_SIZE`, `CHECKPOINT`, `DATASET_RUNS_DIR`, `LLM_TRACE_BUCKET`, `AUTH_REQUIRED=false`, `NEXT_PUBLIC_LOCAL_DEMO=true` for the default local demo.

## CI (`.github/workflows/ci.yml`)

Single `test` job on `push`/`pull_request`:
1. Python 3.11: install `requirements-dev.txt` + `-e backend`.
2. `python -m pytest -q` (testpaths = backend tests + evals tests) then `compileall`.
3. Node 20: `npm ci` + `npm run build` in `frontend/`.

## Operating procedures

Per-component operations docs live in `docs/plan/`:

- **Checkpointing/resume, manifests, control plane:** [`01-etl.md`](01-etl.md)
- **Analytical reads:** [`03-analytics-layer.md`](03-analytics-layer.md)
- **Sync:** [`04-db-sync.md`](04-db-sync.md)
- **Migrations & schema:** [`05-database.md`](05-database.md)
- **Cost ceiling & AI spend:** [`07-ai.md`](07-ai.md)
- **Eval runs:** [`10-evals.md`](10-evals.md)

Secrets are never committed: `.env`, `frontend/.env.local`, `data/raw/`, `data/traces/` are git-ignored. The 11GB raw dataset is never committed; only small fixtures.

## Costs (demo footprint)

| Provider | Approx. monthly |
| --- | --- |
| Vercel Hobby (2 projects) | $0 |
| Supabase Free (Postgres + Auth + Storage) | $0 |
| OpenRouter (demo eval + usage under ceiling) | $0–2 |

Function duration is the hard limit to watch (hobby ~60s); keep `LLM_TIMEOUT_SECONDS` below it so slow providers do not time the function out.