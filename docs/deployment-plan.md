# Git and Hosting Plan

Status: plan + config committed; deployment itself requires two service accounts
(Railway for the API, Vercel for the frontend) that are out of scope of the
read-only grant for this session.

## 1. Git plan

The working tree stays `main`-based, small commits, and secret-hygiene via
`.gitignore` (verified before the first commit):

| Concern | Decision |
| --- | --- |
| Default branch | `main` (empty-git-hook aware, no author assumptions) |
| Commit trigger | Only on explicit request; one logical change per commit |
| Secrets | `.env`, `frontend/.env.local`, `data/raw/`, `data/traces/` are ignored; verify with `git status --porcelain` before `git add` |
| Large data | `data/processed/*` is ignored except the small reproducible `demo-companies.parquet` fixtures; the 11GB raw dataset is never committed |
| CI | `.github/workflows/ci.yml` runs Python tests + compileall on push/PR |

### Creating the remote

`gh` is not installed in this environment, so the remote is created by you
(one-time, ~2 minutes):

```bash
# after installing gh (brew install gh && gh auth login)
gh repo create sales-intelligence --private --source . --push
```

If you prefer a public repo or a different name, pass `--public` or
`--repo org/name`. The commit history is already in place, so this is purely a
push.

## 2. Hosting plan

The monorepo has two deployable units: the FastAPI backend (Dockerfile +
`railway.toml`) and the Next.js frontend (auto-detected by Vercel). Both are
cheap to run at demo scale, but each needs a few environment variables only the
deployer can provide (Supabase project, OpenRouter key), so the plan documents
exactly what to paste.

### 2.1 Backend — Railway

The included `railway.toml` deploys the existing `Dockerfile`. Steps:

1. Create a Railway project and a New Service > Deploy from GitHub repo
   (select the repo pushed in step 1).
2. Add a PostgreSQL plugin (or reuse the existing Supabase project and set
   `DATABASE_URL`). For the demo, either works; Supabase keeps one less tab open.
3. Set service variables:
   - `DATABASE_URL` (plugin-generated, auto-injected by Railway Postgres)
   - `ANALYTICAL_DATASET=/app/data/processed/demo-companies.parquet` (demo; the
     real ETL artifact would be read from object storage instead)
   - `LLM_API_KEY`, `LLM_BASE_URL=https://openrouter.ai/api/v1` (or another
     provider), `LLM_MODEL`
   - `LLM_INPUT_COST_PER_1K`, `LLM_OUTPUT_COST_PER_1K` for truthful cost traces
   - `CORS_ORIGINS=https://<your-frontend>.vercel.app`
   - `AUTH_REQUIRED=false` for an open demo, or `true` + `SUPABASE_JWT_SECRET`
     + `SUPABASE_URL` + `SUPABASE_JWKS_URL` for the full auth/queue flow
4. **Migrations as a release step.** Railway pre-deploy hook in `railway.toml`
   runs `alembic upgrade head` before the service starts. (The Dockerfile/CMD
   only starts uvicorn; the schema change happens in predeploy.)
5. `POST /health/ready` and `GET /health/live` are used as the Railway health
   check (`/health/live`).

### 2.2 Frontend — Vercel

Next.js is auto-detected (`frontend/` is the app root). Steps:

1. Vercel > Add New Project > import the GitHub repo; framework preset Next.js,
   root directory `frontend`.
2. Environment variables:
   - `NEXT_PUBLIC_API_URL=https://<your-backend>.up.railway.app/api/v1`
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (browser-safe
     public keys; the service-role key stays server-side)
   - `NEXT_PUBLIC_LOCAL_DEMO=true` only if you skip Supabase; otherwise unset
     for the real login + queue flow.
3. Deploy; the `vercel.json` (included) is a no-op guard that just pins the
   framework and keeps rewrites off.

### 2.3 Data: real (bounded) ETL + sync

The demo runs on the committed fixture. To make the *provided* dataset visible
in the hosted app:

```bash
# local or a one-shot Railway job; --max-records keeps the run honest and small
make etl RAW_SOURCE="$RAW_DATASET_URL" DATASET=data/processed/companies.parquet \
  DATASET_VERSION=2026-09-07 MAX_RECORDS=5000
make sync DATASET=data/processed/companies.parquet DATASET_VERSION=2026-09-07 \
  MIN_SCORE=50
```

Then repoint `ANALYTICAL_DATASET`/reads at PostgreSQL. For a recurring refresh,
schedule the ETL+sync as a Railway cron service (daily) so the queue stays
fresh; keep raw observations out of the repo.

### 2.4 Operating cost (hosting)

| Provider | Demo footprint | Approx. monthly |
| --- | --- | --- |
| Railway | 1 service + 1 Postgres (hobby/trial) | $0 trial, then ~$5 |
| Vercel | Hobby frontend, demo traffic | $0 |
| Supabase | Free tier (if reused for auth) | $0 |
| OpenRouter | Demo eval + drag-and-drop usage; stay under the ceiling | $0–2 |

LLM spend itself is budgeted by the cost model in `architecture.md`; the app
degrades to deterministic scores if the ceiling is hit.

## 3. Order of operations

1. Push the repo (`gh repo create ... --push`).
2. Deploy backend on Railway; set env vars; verify `GET /health/ready`.
3. Run migrations via the predeploy hook (or `railway run alembic upgrade head`).
4. Deploy frontend on Vercel; set env vars; verify login + queue end-to-end.
5. Bounded real ETL + sync; repoint dataset; confirm scores change.
6. Re-run `make eval-openrouter-v2` to complete the eval, then `make eval-compare`.

Each step is independently revertible (repo re-push, redeploy previous image,
env-var revert), so the plan is safe for a teammate to execute without the
original author.