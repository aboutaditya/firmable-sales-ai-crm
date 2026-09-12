# Sales Intelligence Frontend

Next.js dashboard for ranked prospects and AI sales actions.

```bash
cp .env.example .env.local
npm install
npm run dev
```

The app expects the FastAPI service at `NEXT_PUBLIC_API_URL` and Supabase credentials at `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Users sign in through Supabase; session events keep the API bearer token synchronized automatically.

For local backend-only testing without Supabase, set `NEXT_PUBLIC_LOCAL_DEMO=true` in
`.env.local` and keep `AUTH_REQUIRED=false` in the backend environment. This bypasses
the login screen only for local development and does not create a user or password.
