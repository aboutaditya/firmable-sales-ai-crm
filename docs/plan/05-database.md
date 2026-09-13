# Plan — Application Database (PostgreSQL / Supabase)

Component: the typed SQLAlchemy persistence layer, Alembic migrations, and repositories that back the product (not the raw data warehouse).

Source of truth files:
- `sales_intelligence/models/*`
- `sales_intelligence/migrations/`
- `sales_intelligence/migrations/env.py`
- `sales_intelligence/db/session.py`
- `sales_intelligence/repositories/companies.py`
- `sales_intelligence/repositories/queue.py`

## Connection layer

`db/session.py`:
- `create_engine_from_url` rewrites `postgres://` / `postgresql://` to `postgresql+psycopg://`, with `pool_pre_ping=True`, `future=True`.
- `create_session_factory` returns a `sessionmaker` with `autoflush=False`, `expire_on_commit=False`.

Application services use typed ORM sessions only; raw cursors are not used.

## Schema (models)

All models subclass `Base` (`DeclarativeBase`) in `models/base.py`. Exported: `AIAssessment, AIOutput, AuditEvent, Base, CallActivity, Company, CompanyAssignment, CompanySignal, DatasetRun, PipelineRun, UserPreference`.

| Table | Purpose | Key columns |
| --- | --- | --- |
| `companies` | Synced company projection | `id` PK, `domain`, `organization`, `country`, `city`, `industry`, `employee_count`, `security_score`, `score_version`, `dataset_version`, `is_active`, timestamps |
| `company_signals` | Exposure signals, 1:1 with company | `company_id` PK/FK, asset/surface counts, exposure booleans, `security_tag_count` |
| `company_assignments` | Rep ↔ company workflow state | composite PK `(company_id, user_id)`, `team_id`, `assigned_by`, `status`, `disposition`, `claimed_at`, `last_contacted_at`, `next_follow_up_at`, `notes` |
| `call_activities` | Append-only call history | `company_id`, `user_id`, `outcome`, `notes`, `next_follow_up_at` |
| `ai_assessments` | Qualification results | `company_id`, `ai_score`, `priority`, `confidence`, `reasoning`, `model`, `prompt_version`, tokens, `cost_usd`, `latency_ms` |
| `ai_outputs` | Summary/outreach content | `company_id`, `feature`, `content`, `model`, `prompt_version`, tokens, `cost_usd`, `latency_ms` |
| `audit_events` | Access/action log | `actor_user_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `metadata_json` |
| `dataset_runs` | Durable dataset control plane | `run_id` PK, `dataset_name`, `dataset_version`, source identity, artifact/checkpoint URIs, progress, `status`, `is_current` |
| `pipeline_runs` | ETL/sync execution log | `run_type`, `dataset_version`, `score_version`, `source`, `processed_count`, `qualified_count`, `status` |
| `user_preferences` | Per-user queue prefs | `user_id` PK, `min_exposure_score` (default 60), `page_size` (fixed 1) |

## Migrations (Alembic)

Versions under `migrations/versions/`, chain ordered:

1. `0001_initial_schema` — `companies`, `company_signals`, `ai_assessments`, `ai_outputs`, `pipeline_runs`, `audit_events`, `company_assignments` + indexes and score CHECK constraint.
2. `0002_dataset_runs` — `dataset_runs` with a partial unique index on `(dataset_name) WHERE is_current = true`.
3. `0003_sales_queue` — extends `company_assignments` (status, disposition, timestamps, notes), adds `user_preferences` and `call_activities`.

`env.py` reads `DATABASE_URL` (or `sqlalchemy.url`), rewrites to `postgresql+psycopg://`, and autogenerates against `Base.metadata` with `compare_type=True`. Migrations are applied manually: `alembic upgrade head`.

## Repositories

- `CompanyRepository` (Protocol) → `ParquetCompanyRepository` ([`03-analytics-layer.md`](03-analytics-layer.md)) or `PostgresCompanyRepository`.
  - `PostgresCompanyRepository` implements the same filter vocabulary as DuckDB (country, min_score, industry, min_employee_count, signals, keyset cursor), joined reads of `Company` + `CompanySignal`, and role scoping: `sales_rep` sees only their non-`reassigned` assignments.
  - `list_companies` for `sales_rep` is restricted; admins/managers get the full list.
- `PostgresQueueRepository` — assignment, preference, queue-claim, disposition, and call-activity operations (detailed in [`08-queue.md`](08-queue.md)).

## Design notes

- **Only the sales-relevant projection lives here**; the 11GB source does not.
- **Access gating is enforced in the repository layer**, on top of API auth, so a rep can never read or generate content for another rep's accounts.
- **`dataset_runs`/`pipeline_runs` are the reproducibility control plane** — each dataset run is `is_current`-pointed; the schema it produced is reconstructible.

## Integration points

- Populated by: [`04-db-sync.md`](04-db-sync.md)
- Written during ETL: [`01-etl.md`](01-etl.md)
- Read by: [`06-api.md`](06-api.md), [`07-ai.md`](07-ai.md), [`08-queue.md`](08-queue.md)
- Deployed via: [`11-deployment.md`](11-deployment.md)