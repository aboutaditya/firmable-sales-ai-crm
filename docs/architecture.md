# Backend Architecture

## Product decision boundary

The product has two different concepts that should not be conflated:

- **Exposure score** is deterministic and measures observed external security
  signals in the source data.
- **Sales qualification** is a reviewable AI interpretation of those signals. It
  must not claim buying intent, a breach, or facts absent from the profile.

The application uses rules for parsing, normalization, aggregation, signal
detection, scoring, filtering, and ranking. It uses the LLM only for language
and judgement: qualification reasoning, account summaries, and outreach drafts.
This keeps the expensive and less predictable step behind deterministic
prequalification.

```text
FastAPI routes
      |
      v
Application services  <── CLI commands
      |
      +── Analytics service ── DuckDB ── Parquet
      |
      +── Pipeline service ── streaming reader ── raw JSONL/.zst/HTTP
      |
      +── Sync service ── SQLAlchemy ORM ── PostgreSQL/Supabase
      +── Queue service ── assignments/preferences/activities ── PostgreSQL/Supabase
```

## Boundaries

- `backend/api`: HTTP transport, validation, and response codes.
- `backend/services`: use cases and orchestration; no command-line parsing.
- `backend/schemas.py`: public API contracts.
- `pipeline.py`: low-level streaming parser, normalization, aggregation, and scoring.
- `query.py`: analytical DuckDB access.
- `backend/commands/`: one module per operational command, with `__init__.py` as the CLI dispatcher.
- `scripts/`: backwards-compatible wrappers only.

The API does not process the raw dataset on request. ETL is an operational command that creates the Parquet analytical dataset; API requests query that dataset through DuckDB.

The `sync` command promotes only companies above the deterministic score threshold into the application database. The migration excludes raw observations and preserves dataset/score versions for reproducibility.

PostgreSQL access is centralized in `backend/db`: typed SQLAlchemy models, an engine/session factory, and repository classes. Raw cursors are not used by application services. DuckDB remains SQL-based because it is the analytical query engine over Parquet.

Database schema migrations are managed by Alembic in
`sales_intelligence/backend/migrations`. Alembic uses
`backend.db.models.Base.metadata` for autogeneration, keeping schema changes
alongside the backend while preserving the ORM as the source of truth.

`dataset_runs` is the durable dataset control plane. It stores the source URL,
source checksum, dataset version, artifact URIs, checkpoint URI, row progress,
status, and one `is_current` pointer per dataset name. Local JSON manifests are
diagnostic artifacts; production orchestration should read the database row and
object-storage URIs as the source of truth.

## Multi-user sales queue

The analytical Parquet repository is a local/demo read path. Authenticated
production users use PostgreSQL/Supabase for access-controlled workflow state:

- `companies` and `company_signals` remain the central dataset projection.
- `company_assignments(company_id, user_id)` maps a company to its current
  representative, with assignment status, disposition, notes, and follow-up
  state.
- `user_preferences` stores each representative’s `min_exposure_score`; the
  representative can edit their own threshold and an admin can override it.
  The queue page size is deliberately fixed at one.
- `call_activities` is an append-only history of call outcomes.

`GET /me/queue/next` filters by the authenticated user, assignment status, and
the admin-set threshold, then claims one row in a transaction using a row lock.
When no row is available it returns queue counts and a reason instead of an
ambiguous empty response. `PATCH /me/preferences` is available to the
authenticated user and `PATCH /users/{user_id}/queue-preferences` is admin-only.
The admin panel uses `GET /admin/users`; it reads Supabase Auth users through
the backend-only `SUPABASE_SERVICE_ROLE_KEY` and merges queue state. Without
that key, it lists users already known to the application tables.
Sales representatives cannot use the global `/companies` list. Direct company
detail and AI endpoints apply the same assignment scope. Admins and sales
managers retain the broader list and assignment API.

Local demo mode is explicitly not a multi-user simulation: it shows the ranked
Parquet data and disables workflow writes. This avoids implying that local
anonymous data has assignment guarantees.

## LLM trace schema

Every non-cached LLM attempt writes one JSON object to the configured
`LLM_TRACE_PATH` (default `data/traces/llm_calls.jsonl`), including failures:

```json
{
  "trace_id": "uuid",
  "timestamp": "ISO-8601",
  "feature": "account_scoring | company_summary | outreach",
  "model": "provider/model",
  "prompt_version": "account-scoring-v1",
  "request": {"company": "...", "prompt_version": "..."},
  "response": {"priority": "HIGH"},
  "latency_ms": 1200,
  "input_tokens": 800,
  "output_tokens": 150,
  "cost_usd": 0.0021,
  "decision": "HIGH",
  "status": "success | error",
  "error": null
}
```

The trace sink is separate from sales audit events. Audit events answer who
accessed an account; LLM traces answer what an AI call cost and returned.

## Cost model

LLM calls are made only after deterministic prequalification and are cached by
company, feature, and prompt version. For a chosen provider:

```text
cost per call = input_tokens / 1,000 * input_price_per_1k
             + output_tokens / 1,000 * output_price_per_1k
monthly cost = qualified_accounts * calls_per_account_per_refresh
             * refreshes_per_month * cost per call
```

Actual prices live in environment configuration (`LLM_INPUT_COST_PER_1K`,
`LLM_OUTPUT_COST_PER_1K`) and in the eval artifact, not in code.

### Measured numbers (2026-09-12, `openrouter/free` over the 25-case eval set)

| Metric | v1 qualification |
| --- | --- |
| input tokens, mean / median | 275 / 190 |
| output tokens, mean / median | 1,178 / 1,063 |
| latency, mean / median | 18.6s / 9.7s |

The median ~1,330 tokens per classification is the *verbose* upper bound: the
free model adds preambles and reasoning. A production classifier should either
cap `max_tokens` or use a model tier that answers in ~150 output tokens, cutting
the per-call cost by roughly 5–10x before volume is even considered.

### Model tiering (cheap model for classification, stronger model for judgement)

| Step | Model tier | Why |
| --- | --- | --- |
| Exposure scoring | None (rules) | Deterministic, $0, auditable |
| Qualification classification | Cheapest model that passes the eval gate | Binary-ish decision; high volume |
| Company summary | Same cheap tier, on demand | Short structured prose |
| Outreach draft | Stronger tier, only on rep request | Customer-facing language; low volume |
| Eval runs | Paid mid-tier model | Measurement must not run on the free router |

### Worked monthly example (100-rep team)

```text
qualified accounts synced            = 4,000
refreshes per month                  = 4          (weekly re-scoring of the hot list)
qualifications / account / refresh  = 1
calls per month                      = 4,000 * 4 * 1 = 16,000

Cheap classifier tier, estimated ~700 tokens/call (measured median is 1.3k on
the verbose free router; a constrained model fits ~700):
cost/call = 400 in * $0.00015/k + 300 out * $0.00060/k
          = $0.00006 + $0.00018 = $0.00024
qualification cost/month = 16,000 * $0.00024 ≈ $3.84

Outreach drafts, ~200/mo requested by reps (stronger tier, ~1,500 tokens/call):
cost/call = 1,000 in * $0.0005/k + 500 out * $0.0015/k
          = $0.0005 + $0.00075 = $0.00125
outreach cost/month = 200 * $0.00125 = $0.25

total ≈ $4.09/month; with output-token caps the classifier leg drops to ≈ $1.30
```

Substitute real prices from the provider dashboard into the env vars; the
formula and the eval trace give the actual token counts to plug in.

### Production cost ceiling

Set a monthly budget ceiling per environment (e.g. `$50` QA, `$500` prod) and
compare projected spend before each scoring refresh:

```text
projected = cached_cost_this_month + qualified_candidates * cost_per_call
if projected > ceiling: skip LLM refresh; serve deterministic scores only
```

The app already serves deterministic scores without the LLM, so the degraded
mode is a valid product state, not an outage. Cache keys are company + feature +
prompt version, so re-scoring a candidate that already has a cached result costs
nothing until the score version or prompt version changes.
