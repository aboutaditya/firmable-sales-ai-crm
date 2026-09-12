# High-Level Design — Sales Intelligence Platform

This document describes the system **as it is implemented today**. It is reverse-engineered from the current repository structure so the design, the code, and the per-component plans in [`plan/`](plan/) stay in sync. Per-component detail lives in `docs/plan/*.md`; each section below links to its plan.

## 1. Purpose

The product turns large, observation-oriented infrastructure datasets into a defensible sales workflow: a single next-best-account queue, the evidence that supports prioritization, and grounded AI assistance for research and outreach.

Two concepts are deliberately kept apart:

- **Exposure score** — a deterministic, rule-based score over observed external security signals. It is versioned, explainable, and free.
- **Sales qualification** — a reviewable AI interpretation of those signals. The LLM never claims a breach, buying intent, or facts absent from the source data.

## 2. Data flow at a glance

```text
Raw dataset (JSONL / .gz / .zst, local or HTTP)
        |
        |  streaming ETL  (once, offline, resumable)
        v
Company profiles -> Parquet (analytical dataset)      [plan/01-etl.md]
        |
        |  deterministic scoring (v1, rule-based)      [plan/02-scoring.md]
        v
Parquet + DuckDB analytical read path                  [plan/03-analytics-layer.md]
        |
        |  sync (score >= threshold, batched)          [plan/04-db-sync.md]
        v
PostgreSQL / Supabase (sales-relevant projection)      [plan/05-database.md]
        |
        +-- FastAPI backend  (auth, scoping, AI)       [plan/06-api.md]
        |       |
        |       +-- AI qualification / summary / outreach  [plan/07-ai.md]
        |       +-- Sales queue (assignments, workflow)    [plan/08-queue.md]
        v
Next.js sales dashboard / leads UI                     [plan/09-frontend.md]

Cross-cutting: evaluation harness                      [plan/10-evals.md]
               deployment + operations                 [plan/11-deployment.md]
```

The raw dataset is treated as an immutable analytical source, never loaded into the application database. All downstream data carries `dataset_version`, `score_version`, and `prompt_version` for reproducibility.

## 3. Component map

| Component | Role | Key modules | Plan |
| --- | --- | --- | --- |
| ETL pipeline | Stream, normalize, aggregate observations into company profiles; checkpoint and resume; write Parquet | `sales_intelligence/pipeline.py`, `sales_intelligence/services/pipeline/*` | [`plan/01-etl.md`](plan/01-etl.md) |
| Scoring engine | Deterministic v1 exposure score (0–100), config-driven weights | `sales_intelligence/scoring.py` (`score`, `ScoringConfig`), `SCORE_VERSION` | [`plan/02-scoring.md`](plan/02-scoring.md) |
| Analytical layer | DuckDB reads over Parquet; filters, ranking, cursor pagination | `sales_intelligence/query.py`, `sales_intelligence/repositories/companies.py` | [`plan/03-analytics-layer.md`](plan/03-analytics-layer.md) |
| Schema sync | Promote qualified companies into Postgres; idempotent, batched, deactivation | `sales_intelligence/services/sync.py` | [`plan/04-db-sync.md`](plan/04-db-sync.md) |
| Application database | Postgres/Supabase: companies, signals, assignments, audit, runs, preferences | `sales_intelligence/models/*`, `sales_intelligence/migrations/*`, `sales_intelligence/repositories/*` | [`plan/05-database.md`](plan/05-database.md) |
| API layer | FastAPI transport, validation, auth, scoping, middleware | `sales_intelligence/main.py`, `sales_intelligence/api/*`, `sales_intelligence/controllers/*` | [`plan/06-api.md`](plan/06-api.md) |
| AI layer | Provider abstraction, qualification, summary, outreach, caching, tracing | `sales_intelligence/ai/*`, `sales_intelligence/prompts/*` | [`plan/07-ai.md`](plan/07-ai.md) |
| Sales queue | One-lead claim, assignments, prefs, dispositions, call activity | `sales_intelligence/services/queue.py`, `sales_intelligence/repositories/queue.py` | [`plan/08-queue.md`](plan/08-queue.md) |
| Frontend | Next.js dashboard, leads table, admin console | `frontend/app`, `frontend/components`, `frontend/hooks`, `frontend/lib` | [`plan/09-frontend.md`](plan/09-frontend.md) |
| Evaluation | Classification + output-rubric harnesses, versioned results | `evals/*` | [`plan/10-evals.md`](plan/10-evals.md) |
| Deployment & ops | Vercel + Supabase hosting, Makefile targets, CI | `api/index.py`, `vercel.json`, `Makefile`, `.github/workflows/ci.yml` | [`plan/11-deployment.md`](plan/11-deployment.md) |

## 4. Rules vs LLM

Determinism is the default; the LLM is reserved for language and judgement.

| Task | Approach | Reason |
| --- | --- | --- |
| Parse, normalize, aggregate records | Rules | Deterministic, auditable |
| Signal detection (RDP, DB, EOL, CVEs, surface) | Rules | Exact observed signals |
| Exposure score, ranking, filtering | Rules | Explainable, cheap, reproducible |
| Pre-qualification gate | Rules (`AI_MIN_SCORE`) | Blocks LLM spend below threshold |
| Account qualification | LLM | Reasoned interpretation |
| Company summary | LLM | Natural language |
| Outreach draft | LLM | Customer-facing language; never auto-sent |

The cheapest model that passes the eval gate is used for classification; a stronger tier is reserved for outreach (see [`plan/07-ai.md`](plan/07-ai.md) and cost model below).

## 5. Core flows

### 5.1 Ingestion → analytics

`sales-intelligence etl` streams records one at a time, aggregates them into `CompanyProfile` objects, scores each profile, and writes `companies.parquet` plus a sidecar manifest. Runs are resumable via checkpoints and tracked in `dataset_runs`/`pipeline_runs`.

### 5.2 Analytical reads

Both the CLI query path and the Parquet-backed repository issue the same parameterized DuckDB queries: `company_id`, `country`, `min_score`, `industry`, `min_employee_count`, `signals`, limit/offset, and keyset `cursor`. The filter vocabulary is identical to the Postgres read path.

### 5.3 Sync to the application database

`sales-intelligence sync` pulls companies at or above `--min-score` from Parquet and upserts them (plus their signals) into Postgres in transactions, deactivating rows that fell below the threshold for the current dataset version.

### 5.4 Multi-user queue

Authenticated reps get a one-lead queue: `GET /me/queue/next` claims the highest-scoring unassigned company with a row lock (`FOR UPDATE SKIP LOCKED`) and records dispositions, notes, follow-ups, and call activity against the assignment. Admissions gate reps from the global `/companies` list and scope company detail/AI to their own assignments. Admins assign companies and override per-user thresholds.

### 5.5 AI-assisted workflow

AI endpoints run only after deterministic pre-qualification, cache by (company, feature, prompt version), and write one JSON trace per LLM attempt (success or failure) to JSONL and/or Supabase Storage. Every response carries `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `model`, and `prompt_version`.

## 6. Cross-cutting design decisions

- **Analytical vs application storage separated.** Large data never enters the app DB; Supabase holds only the sales-relevant projection plus workflow state.
- **Everything versioned.** `dataset_version`, `score_version` (`v1`), `prompt_version` (`account-scoring-v1`, `company-summary-v1`, `outreach-v1`) travel with the data.
- **Every LLM call traced.** Traces are the single source for spend and also the input to the generated-output eval.
- **Auth always scopes data.** Even with `AUTH_REQUIRED=false`, role/assignment scoping logic remains in place for the password-protected flow.
- **Local demo is not a multi-user simulation.** Without Supabase, the app serves the ranked Parquet fixture and disables workflow writes.

## 7. Cost model

LLM calls happen only after deterministic pre-qualification and are cached by company, feature, and prompt version.

```text
cost per call = input_tokens / 1000 * input_price_per_1k
             + output_tokens / 1000 * output_price_per_1k
```

Measured on `openrouter/free` over the 25-case eval set (2026-09-12): mean/median input 275/190 tokens, output 1,178/1,063 tokens, latency 18.6s/9.7s. The verbose free router is an upper bound; a constrained classifier (~150 output tokens) cuts per-call cost 5–10x.

A stated monthly ceiling applies: when projected spend would exceed it, the app serves deterministic scores only (a valid product state, not an outage). Details and the worked 100-rep example are in [`plan/07-ai.md`](plan/07-ai.md).

## 8. Hosting and operation

- Backend: Vercel Python function (`api/index.py`, root `vercel.json`, `maxDuration: 60`).
- Frontend: Vercel Next.js project (`frontend/`).
- Database/auth/storage: one Supabase project (Postgres, JWT auth, `llm-traces` Storage bucket).
- Migrations run manually with Alembic; ETL + sync are scheduled jobs.

See [`plan/11-deployment.md`](plan/11-deployment.md).

## 9. Doc index

| Doc | Covers |
| --- | --- |
| [`HLD.md`](HLD.md) | This file: system overview, decisions, flows |
| [`plan/01-etl.md`](plan/01-etl.md) | Ingestion, normalization, aggregation, checkpointing |
| [`plan/02-scoring.md`](plan/02-scoring.md) | Deterministic exposure score v1 |
| [`plan/03-analytics-layer.md`](plan/03-analytics-layer.md) | Parquet + DuckDB read path |
| [`plan/04-db-sync.md`](plan/04-db-sync.md) | Parquet-to-Postgres schema sync |
| [`plan/05-database.md`](plan/05-database.md) | Postgres schema, migrations, repositories |
| [`plan/06-api.md`](plan/06-api.md) | FastAPI routes, auth, scoping, middleware |
| [`plan/07-ai.md`](plan/07-ai.md) | AI qualification/summary/outreach, caching, tracing, cost |
| [`plan/08-queue.md`](plan/08-queue.md) | Sales queue, assignments, dispositions, call activity |
| [`plan/09-frontend.md`](plan/09-frontend.md) | Next.js dashboard and leads UI |
| [`plan/10-evals.md`](plan/10-evals.md) | Evaluation harnesses and results |
| [`plan/11-deployment.md`](plan/11-deployment.md) | Deployment, Makefile, CI, operations |