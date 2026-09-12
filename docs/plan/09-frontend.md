# Plan — Frontend (Next.js Sales Interface)

Component: the Next.js application providing the one-lead queue dashboard, the assigned-leads list, AI assistance, and the admin console.

Source of truth files:
- `frontend/app/*` (layout, page, leads/page)
- `frontend/components/*` (AuthGate, LoginForm, dashboard/*, leads/*, shared/*)
- `frontend/hooks/*`
- `frontend/lib/*` (api client, supabase, dispositions)
- `frontend/package.json`

## Stack

Next.js 14 (App Router) + React 18 + TypeScript, `@supabase/supabase-js` for browser auth. Deps are intentionally minimal. Scripts: `dev` / `build` / `start` / `lint`.

## Pages and routing

- `app/layout.tsx` — root layout wrapping everything in `<AuthGate>`.
- `app/page.tsx` — the single-lead dashboard. Composes `Topbar`, `QueueBar`, `AICard`, `LeadDetail`, `WorkflowCard`, `AdminModal`. Drives state through `useNotices`, `useQueueLead`, `useAiAssist`, `useAdminPanel`. Detects the admin role from Supabase `app_metadata`; supports local demo mode (`NEXT_PUBLIC_LOCAL_DEMO=true`, no session).
- `app/leads/page.tsx` — "My assigned leads", paginated (10/page) table with call-workflow and detail modals.

## Auth flow

- `AuthGate` loads the Supabase session, keeps the bearer token synchronized into `localStorage` (`sales_intelligence_access_token`), renders `LoginForm` when signed out, and bypasses login in local demo mode.
- `LoginForm` signs in with email/password via `supabase.auth.signInWithPassword`.
- The API client attaches the stored token to every request.

## Components

### Dashboard
- `QueueBar` — personal-queue header; admin-only min-exposure threshold slider (0–100) with save.
- `AICard` — "Account summary" / "Draft outreach" actions; shows cached output and running state.
- `LeadDetail` — current-account evidence card: score, asset/vuln/critical/EOL counts, and `signals` ("WHY THIS ACCOUNT").
- `WorkflowCard` — wraps `WorkflowForm` for the current lead.
- `AdminModal` — admin console: user list with assigned counts, per-user min-exposure threshold save, and assign-company-by-id/domain.

### Leads list
- `LeadsTable` / `LeadRow` — paginated grid of assigned leads (org/domain, score, status, disposition, follow-up, notes) with "Call disposition" and "Details" actions.
- `CallWorkflowModal` / `LeadDetailModal` — workflow entry and detail view per lead.

### Shared
- `Topbar`, `Modal` (backdrop/Escape close), `DispositionSelect`, `WorkflowForm` (disposition + follow-up + notes '/ Save/Skip, and call-outcome + 'Log call').

## Hooks

| Hook | Responsibility |
| --- | --- |
| `useNotices` | error/notice state for in-UI messaging |
| `useQueueLead` | next-lead load, threshold prefs (default 60), disposition save (clears lead on terminal dispositions), call logging, skip (nurture + next-day follow-up), local-demo fallback |
| `useAiAssist` | `summarizeCompany` / `draftOutreach` with output + loading state, `resetAi` |
| `useAdminPanel` | admin user list, per-user threshold update, company assignment |
| `useAssignedLeads` | paginated assigned-lead list, workflow/detail modal state, disposition + call updates |

## API client

`lib/api/`: typed wrappers over `NEXT_PUBLIC_API_URL ?? http://localhost:8000/api/v1`.

- `client.ts` — fetch wrapper adding the Bearer token; raises with the API's structured message.
- `companies.ts` — list (with cursor/limit), get, assign.
- `queue.ts` — preferences, next lead, assigned leads, disposition, calls.
- `ai.ts` — assess / summarize / draft outreach.
- `users.ts` — admin user list.
- `types.ts` — shared contracts mirroring the backend Pydantic schemas.

## Domain helpers

`lib/dispositions.ts` — label map for the 8 dispositions, `CALL_OUTCOMES`, `TERMINAL_DISPOSITIONS` (qualified/disqualified/bad_data/do_not_contact/nurture), and `observedSignals(company)` producing human-readable evidence strings for the "WHY THIS ACCOUNT" view.

## Local demo vs authenticated flow

- Local demo: `NEXT_PUBLIC_LOCAL_DEMO=true`, backend `AUTH_REQUIRED=false` — dashboard reads the Parquet fixture via `listCompanies`, workflow writes are unavailable/bannered.
- Authenticated: real login + per-rep queue + workflow writes against Supabase.

## Integration points

- API contract: [`06-api.md`](06-api.md)
- Queue behavior driving the UI: [`08-queue.md`](08-queue.md)
- Build/deploy: [`11-deployment.md`](11-deployment.md)