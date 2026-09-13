# Postman collection

Import `Sales Intelligence.postman_collection.json` into Postman.

## Local demo mode

1. Start the API with `make start-backend`.
2. Leave `accessToken` empty while `AUTH_REQUIRED=false`.
3. Run `System → Readiness`.
4. Run `Companies → List companies`.
5. Set `companyId` to a returned company ID.
6. Run the company detail and AI requests as configured.

The collection automatically stores `next_cursor` from list responses in the
`cursor` variable.

## Queue and Admin

Queue and Admin requests require a valid Supabase-compatible JWT. Set the
collection variable `accessToken` to one, then:

- `Queue` — a sales rep's assigned leads: preferences, next lead, list queue,
  update disposition, and record call activity.
- `Admin` — user management: list users and update another user's queue
  preferences (`targetUserId`).

The `assignedUserId`/`teamId` variables configure `Companies → Assign company`.