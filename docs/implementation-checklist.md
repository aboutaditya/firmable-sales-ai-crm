# Sales Intelligence Implementation Checklist

This checklist tracks implementation against the HLD. Work through the sections in order unless a dependency requires otherwise.

For the take-home submission status and remaining reviewer-facing work, see
[`docs/submission-hardening-plan.md`](submission-hardening-plan.md).

## Status legend

- `[x]` Complete
- `[ ]` Pending
- `[~]` Partially complete

## 1. Raw dataset and ingestion

- `[x]` Stream JSONL observations without loading the raw dataset into memory.
- `[x]` Support local files and HTTP(S) object URLs.
- `[x]` Support `.zst` and `.gz` input.
- `[x]` Support bounded runs with `--max-records`.
- `[x]` Normalize domains, organizations, countries, and cities.
- `[x]` Handle the actual Shodan-shaped source schema.
- `[x]` Add malformed JSON validation.
- `[ ]` Run the complete 11GB production dataset.
- `[ ]` Add progress reporting and throughput metrics.
- `[x]` Add checkpointing and retry support.
- `[x]` Add dataset manifests and checksums.
- `[ ]` Add partitioned intermediate aggregation for larger-than-memory company cardinality.
- `[x]` Add a persisted pipeline-run record for every ETL execution.

## 2. Company aggregation and scoring

- `[x]` Aggregate observations into company profiles.
- `[x]` Deduplicate IPs, domains, vulnerabilities, and EOL products.
- `[x]` Detect vulnerabilities, critical vulnerabilities, EOL products, RDP, databases, and Exchange.
- `[x]` Calculate deterministic security score v1.
- `[x]` Persist `score_version` in analytical output.
- `[ ]` Add formal score configuration instead of hardcoded weights.
- `[ ]` Add score-version comparison tooling.
- `[ ]` Add broader signal coverage and signal documentation.
- `[ ]` Add score calibration against labelled examples.

## 3. Parquet and DuckDB analytical layer

- `[x]` Export aggregated profiles to Parquet.
- `[x]` Query Parquet using DuckDB.
- `[x]` Support country filtering.
- `[x]` Support minimum-score filtering.
- `[x]` Support limit and offset pagination.
- `[x]` Support company-id lookup.
- `[x]` Add industry filtering.
- `[ ]` Add employee-count filtering.
- `[x]` Add individual signal filters.
- `[x]` Add cursor-based pagination.
- `[ ]` Add analytical query performance tests.
- `[ ]` Add configurable qualification thresholds.
- `[x]` Remove the current fixed 10,000-row sync/query ceiling through batching.

## 4. Supabase/PostgreSQL application database

- `[x]` Add migration for `companies`.
- `[x]` Add migration for `company_signals`.
- `[x]` Add migration for `ai_assessments`.
- `[x]` Add migration for `pipeline_runs`.
- `[x]` Add idempotent company upserts.
- `[x]` Add idempotent signal upserts.
- `[x]` Add configurable score-threshold sync command.
- `[x]` Track dataset and score versions on synced companies.
- `[x]` Populate and update `pipeline_runs` during ETL and sync.
- `[x]` Deactivate companies that no longer qualify for the synced dataset version.
- `[x]` Add batched sync for datasets larger than 10,000 qualified companies.
- `[x]` Add migration execution to deployment.
- `[ ]` Add database indexes based on production query patterns.
- `[x]` Add database repository interfaces and integration tests.
- `[x]` Use typed SQLAlchemy ORM models and sessions for application database access.

## 5. FastAPI backend

- `[x]` Add application factory.
- `[x]` Add configuration from environment variables.
- `[x]` Add health endpoint.
- `[x]` Add liveness and readiness checks.
- `[x]` Add company list endpoint.
- `[x]` Add company detail endpoint.
- `[x]` Add request validation and response schemas.
- `[x]` Add DuckDB-backed analytics service.
- `[x]` Add Supabase/PostgreSQL-backed repository.
- `[x]` Switch production company reads from Parquet to Supabase when `DATABASE_URL` is configured.
- `[x]` Add `POST /companies/{id}/assess`.
- `[x]` Add `POST /companies/{id}/outreach`.
- `[x]` Add cached AI assessment retrieval.
- `[x]` Add authentication and authorization. Supabase-compatible JWT, route roles, assignment-scoped reads, and AI ownership checks are implemented.
- `[x]` Add audit events for company access, AI outputs, ETL, and sync operations.
- `[x]` Add company assignment storage and sales-representative access filtering.
- `[x]` Add manager/admin company assignment endpoint.
- `[x]` Add one-lead queue claiming with row locking.
- `[x]` Add per-user minimum exposure preferences.
- `[x]` Add disposition, follow-up, and call-activity persistence.
- `[x]` Add readiness checks for dataset/database dependencies.
- `[x]` Add structured API error responses.
- `[x]` Add request correlation IDs.
- `[x]` Add environment validation and CORS configuration.
- `[x]` Add per-process AI rate limiting.
- `[x]` Add structured application logging.
- `[ ]` Add API integration and contract tests for all endpoints.

## 6. AI qualification and outreach

- `[x]` Add provider abstraction for LLM calls.
- `[x]` Add deterministic prequalification before LLM invocation.
- `[x]` Add account qualification workflow.
- `[x]` Add company summary generation.
- `[x]` Add personalized outreach generation.
- `[x]` Add timeout, retry, and failure handling.
- `[x]` Add cached assessment reuse.
- `[x]` Persist AI priority, score, reasoning, and confidence.
- `[x]` Persist model, prompt version, and input/output metadata.
- `[~]` Persist latency and cost metadata. Latency and usage-based cost are implemented when provider pricing is configured.
- `[x]` Add output schema validation.

## 7. Prompts, skills, and observability

- `[x]` Add `prompts/account_scoring/v1.txt`.
- `[x]` Add `prompts/company_summary/v1.txt`.
- `[x]` Add `prompts/outreach/v1.txt`.
- `[x]` Add reusable account-scoring skill documentation.
- `[x]` Add reusable outreach-draft skill documentation.
- `[x]` Add prompt version to every assessment record.
- `[x]` Add structured LLM traces. JSONL traces include request, response, model, prompt version, latency, usage, cost, decision, and errors.
- `[x]` Add token usage tracking.
- `[x]` Add configurable cost calculation using provider pricing.
- `[x]` Add latency tracking.
- `[ ]` Add decision and failure event tracking.

## 8. Evaluation system

- `[x]` Create a hand-labelled account-scoring dataset (25 cases).
- `[x]` Add evaluation harness.
- `[x]` Calculate precision, recall, and F1.
- `[x]` Compare prompt versions.
- `[x]` Store real model evaluation results as versioned artifacts. v1 is
  measured over all 25 cases; the v2 run is 18/25 and clearly labelled partial
  (`evals/results/README.md`), with a resumable runner to finish it.
- `[x]` Add regression tests for known qualification cases.
- `[x]` Document how prompt quality is measured (`evals/README.md`).

## 9. Frontend

- `[x]` Create the Next.js application shell.
- `[x]` Add one-lead personal queue dashboard.
- `[~]` Add ranked prospect dashboard. Managers/admins retain the API list; reps use the queue.
- `[x]` Add user-level exposure threshold control.
- `[x]` Add disposition, follow-up, and call logging controls.
- `[ ]` Add manager assignment screen after user-directory integration.
- `[ ]` Add filters.
- `[ ]` Add pagination and sorting.
- `[x]` Add company detail view.
- `[x]` Display security signals and deterministic score explanation.
- `[x]` Display AI qualification and reasoning output through the API.
- `[ ]` Add assessment action to the focused rep workflow.
- `[x]` Add clearly separated summary and outreach-generation actions.
- `[x]` Add loading, error, and empty states.
- `[x]` Add frontend API client and typed contracts.
- `[x]` Add Supabase browser client, login, logout, and persisted session handling.
- `[x]` Synchronize Supabase access tokens with the FastAPI API client.

## 10. Deployment and operations

- `[x]` Add runtime `requirements.txt`.
- `[x]` Add development `requirements-dev.txt`.
- `[x]` Add Dockerfile.
- `[x]` Add Uvicorn startup configuration.
- `[x]` Add Docker healthcheck.
- `[ ]` Add production environment-variable validation.
- `[x]` Add CI workflow for tests and linting.
- `[ ]` Add database migration deployment step.
- `[ ]` Add scheduled ETL and sync jobs.
- `[ ]` Add operational logs and metrics.
- `[ ]` Add alerting for failed pipeline runs.
- `[x]` Add Railway backend deployment configuration (`railway.toml`).
- `[x]` Add Vercel frontend deployment configuration (`frontend/vercel.json`).
- `[ ]` Deploy backend and frontend and share the hosted URL (`docs/deployment-plan.md`).
- `[ ]` Add object-storage configuration for Parquet artifacts.
- `[ ]` Add production backup and retention policies.

## Historical implementation sequence

1. Complete Supabase-backed repository and switch FastAPI reads to it.
2. Add pipeline-run tracking and batched sync.
3. Implement AI assessment persistence and the assessment endpoint.
4. Add prompts, skills, observability, and evals.
5. Build the Next.js dashboard.
6. Finish CI, deployment, scheduling, monitoring, and production hardening.
