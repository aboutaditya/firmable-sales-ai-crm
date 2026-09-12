# Deploying to Vercel: Step-by-Step Guide

## Prerequisites

- GitHub account (repo already pushed)
- Vercel account (free tier is sufficient)
- Supabase project (free tier is sufficient)
- OpenRouter API key (for LLM calls)

---

## Phase 1: Supabase Setup (5 minutes)

### 1.1 Create Supabase Project
1. Go to https://supabase.com → Sign up or log in
2. Click **"New Project"**
3. Enter:
   - Project name: `firmable-sales-ai`
   - Database password: (strong, save it)
   - Region: Closest to your users
4. Wait 2–3 minutes for provisioning

### 1.2 Get Supabase Credentials
After project is live, go to **Settings → API**:
- Copy `Project URL` → save as `SUPABASE_URL`
- Copy `anon public` key → save as `SUPABASE_ANON_KEY`
- Copy `service_role` key → save as `SUPABASE_SERVICE_ROLE_KEY`

Also get JWT secret:
- Go to **Settings → API → JWT Settings**
- Copy `your-super-secret-jwt-token` → save as `SUPABASE_JWT_SECRET`

### 1.3 Run Database Migrations
```bash
# Locally, with DATABASE_URL set to your Supabase connection string
export DATABASE_URL="postgresql://postgres:[PASSWORD]@[PROJECT-ID].supabase.co:5432/postgres"
cd backend
alembic -c alembic.ini upgrade head
```

This creates all tables (companies, assignments, queue, audit, etc.)

### 1.4 Create Storage Bucket (for LLM traces)
In Supabase dashboard:
- Go to **Storage**
- Click **"New bucket"**
- Name: `llm-traces`
- Uncheck "Private" → make it public (or secure with RLS later)

---

## Phase 2: Backend Deployment (10 minutes)

### 2.1 Update `.env.example` with Supabase details
```bash
# backend/.env (or .env.example for reference)
DATABASE_URL=postgresql://postgres:[PASSWORD]@[PROJECT-ID].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT-ID].supabase.co
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
LLM_API_KEY=sk-or-v1-[YOUR-OPENROUTER-KEY]
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=mistralai/mixtral-8x7b-instruct
OPENROUTER_MODEL=mistralai/mixtral-8x7b-instruct
OPENROUTER_INPUT_COST_PER_1K=0
OPENROUTER_OUTPUT_COST_PER_1K=0
AUTH_REQUIRED=true
AI_MIN_SCORE=50
AI_RATE_LIMIT_PER_MINUTE=10
ANALYTICAL_DATASET=data/processed/companies.parquet
```

### 2.2 Create Vercel Project (Backend)
```bash
# From your local repo
cd /Users/adityathakur/Desktop/Firmable
vercel login
vercel --prod
```

Or via web:
1. Go to https://vercel.com → Dashboard
2. Click **"Add New → Project"**
3. Select your GitHub repo `aboutaditya/firmable-sales-ai-crm`
4. Configure:
   - **Framework Preset:** Python
   - **Root Directory:** `./` (default)
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Output Directory:** (leave empty)

### 2.3 Add Environment Variables
In Vercel dashboard → Project Settings → **Environment Variables**:

Add all variables from your `.env`:
```
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_JWT_SECRET=...
SUPABASE_SERVICE_ROLE_KEY=...
LLM_API_KEY=sk-or-v1-...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=mistralai/mixtral-8x7b-instruct
OPENROUTER_MODEL=mistralai/mixtral-8x7b-instruct
OPENROUTER_INPUT_COST_PER_1K=0
OPENROUTER_OUTPUT_COST_PER_1K=0
AUTH_REQUIRED=true
AI_MIN_SCORE=50
AI_RATE_LIMIT_PER_MINUTE=10
ANALYTICAL_DATASET=data/processed/companies.parquet
LLM_TRACE_BACKEND=storage
SUPABASE_STORAGE_BUCKET=llm-traces
```

### 2.4 Deploy
Vercel auto-deploys on git push to `main`. Check:
- Vercel dashboard → Deployments
- Wait for "Build successful" (5–10 min)
- Backend URL: `https://[PROJECT].vercel.app/api/v1`

**Test:**
```bash
curl https://[PROJECT].vercel.app/api/v1/health
# Should return: {"status": "ok", "timestamp": "..."}
```

---

## Phase 3: Frontend Deployment (10 minutes)

### 3.1 Create Frontend Project
In Vercel dashboard → **"Add New → Project"**:
1. Select the **same GitHub repo**
2. Configure:
   - **Framework Preset:** Next.js
   - **Root Directory:** `./frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`

### 3.2 Add Frontend Environment Variables
In Vercel → Project Settings → **Environment Variables** (for `frontend/`):
```
NEXT_PUBLIC_API_URL=https://[BACKEND-PROJECT].vercel.app/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://[PROJECT-ID].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=[ANON-KEY]
```

### 3.3 Deploy
```bash
# Or just push to GitHub; Vercel auto-deploys
git add . && git commit -m "Production env vars" && git push origin main
```

Vercel deploys automatically. Check:
- Frontend URL: `https://[PROJECT].vercel.app`

**Test:**
- Open the dashboard
- Log in with Supabase JWT (or use local demo mode: `NEXT_PUBLIC_LOCAL_DEMO=true`)

---

## Phase 4: ETL & Data Pipeline (15 minutes)

### 4.1 Build Dataset Locally
```bash
cd /Users/adityathakur/Desktop/Firmable

# Download raw data and build Parquet
make etl

# Output: data/processed/companies.parquet
```

### 4.2 Sync to Vercel PostgreSQL
```bash
export DATABASE_URL="postgresql://postgres:[PASSWORD]@[PROJECT-ID].supabase.co:5432/postgres"
cd backend
sales-intelligence sync data/processed/companies.parquet --min-score 40 --dataset-version 2026-09-13 --batch-size 1000
```

This upserts companies into PostgreSQL. Check:
```bash
curl -H "Authorization: Bearer [SUPABASE-JWT]" \
  https://[BACKEND].vercel.app/api/v1/companies?limit=5
```

---

## Phase 5: Configure Production Settings

### 5.1 Enable Auth
- Supabase → Auth → Providers → Enable Email/Password (or OAuth)
- Backend `.env`: `AUTH_REQUIRED=true`

### 5.2 Set Rate Limits & Cost Ceilings
```bash
# In Vercel env vars
AI_MIN_SCORE=50                    # Only qualify accounts scoring 50+
AI_RATE_LIMIT_PER_MINUTE=10        # Max 10 LLM calls/min per user
LLM_TRACE_BACKEND=storage          # Store traces in Supabase Storage
```

### 5.3 Configure LLM Caching
```bash
# Auto-cache by (company_id, feature, prompt_version)
# Disabled: 0, Enabled: 1
AI_CACHE_ENABLED=1
```

---

## Phase 6: Verify End-to-End

### 6.1 Health Checks
```bash
# Backend health
curl https://[BACKEND].vercel.app/api/v1/health

# Frontend loads (should see login page)
curl https://[FRONTEND].vercel.app
```

### 6.2 Test API
```bash
# Get companies (requires auth token)
BEARER_TOKEN="[SUPABASE-JWT]"
curl -H "Authorization: Bearer $BEARER_TOKEN" \
  https://[BACKEND].vercel.app/api/v1/companies?limit=3 | jq .

# Trigger account-scoring (requires DATABASE_URL)
curl -H "Authorization: Bearer $BEARER_TOKEN" \
  -X POST https://[BACKEND].vercel.app/api/v1/companies/acme.com/assess \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

### 6.3 Test Frontend
1. Open `https://[FRONTEND].vercel.app`
2. Log in (create account via Supabase Auth)
3. Search for a company
4. Click "Assess" → should trigger LLM qualification
5. Check `data/traces/llm_calls.jsonl` (or Supabase Storage `llm-traces/`) for traces

---

## Troubleshooting

### Backend won't deploy
- Check build logs: Vercel Dashboard → Deployments → [Failed] → Logs
- Common: missing `backend/requirements.txt` or Python version mismatch
- Fix: `cd backend && pip freeze > requirements.txt`

### Database connection fails
- Verify `DATABASE_URL` is correct (test locally first)
- Supabase → Settings → Database → Connection string
- Check firewall: Supabase → Settings → Network → add Vercel IPs

### Frontend can't reach backend
- Verify `NEXT_PUBLIC_API_URL` in frontend env vars
- Check CORS: Backend should allow frontend origin
- Test: `curl -H "Origin: https://[FRONTEND].vercel.app" [BACKEND]/api/v1/health`

### LLM calls fail
- Verify `LLM_API_KEY` is set and valid
- Check rate limits: OpenRouter logs / Vercel logs
- Check cost: if quota hit, app falls back to deterministic scores only

### Auth fails (401 errors)
- Verify `SUPABASE_JWT_SECRET` matches frontend's key
- Check token: `curl -H "Authorization: Bearer [TOKEN]" [BACKEND]/api/v1/me`
- If token invalid, re-authenticate in frontend (log out, log in)

---

## Monitoring & Ops

### View Logs
```bash
# Vercel logs (real-time)
vercel logs [PROJECT-URL]

# Or via Vercel dashboard → Logs
```

### Monitor LLM Traces
```bash
# Download traces from Supabase Storage
aws s3 cp s3://[SUPABASE-PROJECT]-llm-traces/ ./traces/ --recursive

# Or query database directly
DATABASE_URL=... psql -c "SELECT * FROM ai_output LIMIT 10;"
```

### Cost Tracking
```bash
# Calculate spend from traces
python evals/harness.py ./traces/llm_calls.jsonl --cost-summary
```

---

## Summary: URLs After Deployment

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | `https://[FRONTEND].vercel.app` | Dashboard, queue, company search |
| Backend API | `https://[BACKEND].vercel.app/api/v1` | REST API |
| Database | Supabase project (private) | Companies, queue, audit logs |
| LLM Traces | Supabase Storage `llm-traces/` | Cost tracking & evals |

---

## Next Steps

1. **Verify data:** Search for companies in the frontend
2. **Test AI features:** Click "Assess" on a company
3. **Monitor costs:** Check traces and LLM spend
4. **Configure auth:** Set up Supabase sign-up flow
5. **Run evals:** Test prompt versions against production queries
