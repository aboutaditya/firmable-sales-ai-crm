# Plan — FastAPI Backend (API Layer)

Component: HTTP transport, validation, authentication/authorization, scoping, and error shaping for the product.

Source of truth files:
- `sales_intelligence/main.py`
- `sales_intelligence/config.py`
- `sales_intelligence/api/*` (routes, auth, middleware, errors, rate_limit, container, dependencies)
- `sales_intelligence/controllers/*`
- `sales_intelligence/pydantic/*`

## App factory and config

`create_app(settings)` builds the FastAPI application from a frozen `Settings` dataclass loaded from `.env` (`Settings.from_env()` + `validate()`). Key settings:

- `API_PREFIX` (default `/api/v1`), `APP_NAME`.
- `ANALYTICAL_DATASET` (default `data/processed/companies.parquet`), `DATABASE_URL`, `RAW_DATASET_URL`.
- `CORS_ORIGINS`, `AUTH_REQUIRED`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`/`SUPABASE_JWKS_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- `LLM_*` / fallback `OPENROUTER_*` (see [`07-ai.md`](07-ai.md)), `AI_MIN_SCORE`, `AI_RATE_LIMIT_PER_MINUTE` (default 30).

`validate()` fails fast on: partial LLM config, `auth_required` without a JWT secret or JWKS URL, or an invalid rate limit.

## Middleware and error handling

- `RequestIdMiddleware` — accepts or generates `X-Request-ID`, times the request, logs `request_completed` with method/path/status/duration, echoes the header on the response.
- CORS — configured from `CORS_ORIGINS`; credentials only when explicit origins are set.
- Exception handlers — consistent JSON shapes for HTTP errors (404/422/403/401…), validation errors, and unhandled 500s.

## Routes and controllers

Routes are registered with `add_api_route` per controller, included by `build_router` in order: system, queue, admin, companies, ai.

### System (`/health`, `/health/live`, `/health/ready`)
No auth. Readiness checks the DB (`select 1`) when configured, else the analytical dataset file; 503 with per-check detail on failure.

### Companies
- `GET /companies` — roles admin/sales_manager/sales_rep; **sales_rep → 403** ("use the assigned one-lead queue"). Filters mirror the analytical vocabulary: `country`, `min_score`, `industry`, `min_employee_count`, `signal` (repeatable), `limit` (1–10,000), `offset`, `cursor`. `CompanyListResponse` returns `items`, `limit`, `offset`, `count`, `next_cursor`.
- `GET /companies/{company_id}` — scoped to role; reps limited to their assignments.
- `POST /companies/{company_id}/assign` — admin/sales_manager only.

### Queue (all require authentication)
- `GET /me/preferences`, `PATCH /me/preferences` (admin/sales_manager only).
- `GET /me/queue/next`, `GET /me/queue`, `POST /me/queue/{company_id}/disposition`, `POST /me/queue/{company_id}/calls`. Detailed in [`08-queue.md`](08-queue.md).

### Admin (admin only)
- `GET /admin/users` — merges queue/preference state with the Supabase Auth user directory (via the backend-only service-role key when set).
- `PATCH /users/{user_id}/queue-preferences` — per-user exposure threshold.

### AI (rate-limited, roles admin/sales_manager/sales_rep)
- `POST /companies/{company_id}/assess` → `AssessmentResponse`.
- `POST /companies/{company_id}/summary` → `AIContentResponse` (`feature="company_summary"`).
- `POST /companies/{company_id}/outreach` → `AIContentResponse` (`feature="outreach"`).

Error mapping in the AI controller: `LookupError → 404`, `PermissionError → 422`, `LLMProviderError → 502`, missing AI wiring → 503.

## Authentication model

`api/auth.py::current_user`:

- Anonymous when `AUTH_REQUIRED=false` and no Bearer token.
- Otherwise requires a Supabase-compatible JWT: issuer check, then HS256 (`SUPABASE_JWT_SECRET`) or ES256/RS256 (`SUPABASE_JWKS_URL`), audience `authenticated`, `sub` required.
- Roles come from `roles`/`app_metadata.roles` claims (union with the `role` claim). `require_roles(...)` gates endpoints; anonymous passes role checks but the queue/API scoping still blocks unauthenticated interactions.
- `require_authenticated_queue_user` returns 401 for anonymous on queue endpoints.

## Scoping model

Authorization is layered:

1. **Role gates** on routes (`require_roles`).
2. **Repository-level scoping** — `sales_rep` rows are constrained to their own non-`reassigned` assignments in both the Postgres and Parquet repositories ([`05-database.md`](05-database.md)), so AI and detail access are assignment-scoped.
3. **AI permission** — qualification/summary/outreach reject accounts outside the caller's scope.

## Pydantic contracts

- `Company` — full profile shape including `security_score`, `score_version`, all signals.
- `AssessmentResponse` / `AIContentResponse` — AI result + trace metadata (`model`, `prompt_version`, tokens, `cost_usd`, `latency_ms`, `cached`).
- Queue: `QueuePreferences` (fixed `page_size=1`), `QueueLead`, `QueueNextResponse`, `AdminUserList`, `Disposition` (8 literals).
- System: `HealthResponse`, `ReadinessResponse`.

## Container / wiring

`api/container.py::build_container` wires repositories and services from settings; `apply_to(app)` attaches `app.state` services. AI services are built only when `DATABASE_URL` + LLM config are present; otherwise AI routes return 503 with a clear message.

## Integration points

- Read paths (Parquet vs Postgres): [`03-analytics-layer.md`](03-analytics-layer.md), [`05-database.md`](05-database.md)
- AI wiring: [`07-ai.md`](07-ai.md)
- Queue behavior: [`08-queue.md`](08-queue.md)
- Frontend client: [`09-frontend.md`](09-frontend.md)