# Plan — Sales Queue & Workflow

Component: the one-lead personal queue, company assignments, per-user preferences, dispositions, and call activity.

Source of truth files:
- `sales_intelligence/repositories/queue.py`
- `sales_intelligence/services/queue.py`
- `sales_intelligence/pydantic/queue.py`
- Frontend wiring: `frontend/hooks/useQueueLead.ts`, `useAssignedLeads.ts`

## Purpose

Give each sales rep a single actionable company at a time, record what happened, and keep account data and AI access scoped to that rep. Values deliberately fixed: queue page size is always one.

## Data model

- `company_assignments` — composite PK `(company_id, user_id)`; `status` ∈ `assigned`/`in_progress`/`nurture`/`completed`/`reassigned`; `disposition`, `notes`, `claimed_at`, `last_contacted_at`, `next_follow_up_at`.
- `user_preferences` — `min_exposure_score` (default 60), `page_size` locked to 1.
- `call_activities` — append-only history of calls (`outcome`, `notes`, `next_follow_up_at`).

Disposition literals: `not_contacted`, `call_attempted`, `connected`, `qualified`, `disqualified`, `nurture`, `bad_data`, `do_not_contact`.

## Core operations (`PostgresQueueRepository`)

### Claim next lead

`next_assigned_company` — inside a transaction:

1. Selects the highest-scoring active company with **no non-`reassigned` assignment** (`~exists(...)`), ordered `security_score DESC, id ASC`, limit 1.
2. Locks the row `FOR UPDATE SKIP LOCKED` for concurrency-safe claiming.
3. Creates/reopens the assignment for the caller with `status="in_progress"`, `disposition="not_contacted"`, `claimed_at=now`.

`GET /me/queue/next` returns the lead, or a structured empty response (`min_exposure_score`, `assigned_count`, `eligible_count`, `message`) instead of an ambiguous empty body.

### Assignment admin

`assign_company` — validates the company exists, marks that company's other active assignments `reassigned`, and upserts the `(company_id, user_id)` assignment as `assigned` (disposition/follow-up/notes reset).

### Preferences

- `get_preferences` defaults to `min_exposure_score=60, page_size=1`.
- `update_preferences` forces `page_size=1`; the rep edits their own threshold; `PATCH /users/{user_id}/queue-preferences` (admin) overrides it.
- The threshold is stored and surfaced but the claim query is the admin-set gate; reps cannot bypass.

### List my leads

`list_assigned_companies` — the rep's non-`reassigned` assignments joined to company + signal, ordered by status priority (`in_progress`, `assigned`, `nurture`, then other) then `security_score DESC`. Supports limit/offset. (`GET /me/queue` returns `items`, `count`, `page`, `page_size`, `has_more`.)

### Dispositions

`update_disposition` — requires an existing non-`reassigned` assignment (`PermissionError` otherwise). Maps:

| Disposition | Assignment status |
| --- | --- |
| `nurture` | `nurture` |
| `not_contacted` | `assigned` |
| `call_attempted` / `connected` | `in_progress` (+ `last_contacted_at`) |
| `qualified` / `disqualified` / `bad_data` / `do_not_contact` | `completed` (+ `last_contacted_at`) |

### Call activity

`record_call` — requires a valid assignment; inserts a `CallActivity`, mirrors outcome/notes/follow-up onto the assignment, sets `last_contacted_at`, and derives status: `nurture` → `nurture`; terminal outcomes → `completed`; else `in_progress`.

## Wrappers and frontend

`QueueService` is a thin wrapper around the repository (raises `RuntimeError` when a method is missing). The frontend uses `useQueueLead` (dashboard: next lead, threshold control, dispositions, log call, skip = `nurture` + tomorrow follow-up) and `useAssignedLeads` (leads page: paginated list, workflow/detail modals).

## Security and scoping

- Queue endpoints require an authenticated user (`require_authenticated_queue_user` → 401).
- `sales_rep` cannot call `GET /companies` (403) and company detail/AI endpoints are scoped to their assignments ([`06-api.md`](06-api.md), [`05-database.md`](05-database.md)).
- Audited actions: `claim_next_lead`, `list_assigned_leads`, `update_disposition`, `record_call`, `update_queue_preferences`, `assign_company`.

## Integration points

- API surface: [`06-api.md`](06-api.md)
- Schema: [`05-database.md`](05-database.md)
- UI: [`09-frontend.md`](09-frontend.md)

## Notes / current behavior

- The claim query does not apply the worker's `min_exposure_score` as a hard gate on which unassigned company is next — the threshold is surfaced for the rep/admin and set by the admin. The eligible count status reflects the unassigned pool.
- Local demo mode disables workflow writes; it is not a multi-user simulation.