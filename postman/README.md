# Postman collection

Import `Sales Intelligence.postman_collection.json` into Postman.

For local testing:

1. Start the API with `make start-backend`.
2. Leave `accessToken` empty while `AUTH_REQUIRED=false`.
3. Run `System → Readiness`.
4. Run `Companies → List companies`.
5. Set `companyId` to a returned company ID.
6. Run the company detail and AI requests as configured.

When authentication is enabled, set the collection variable `accessToken` to a
valid Supabase-compatible JWT. The collection automatically stores `next_cursor`
from list responses in the `cursor` variable.
