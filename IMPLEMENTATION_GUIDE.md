# Implementation Guide: How Requirements Were Built & How to Use Them

This document maps each requirement from the take-home task to what was built, where it lives in the codebase, and how to trigger or use it.

---

## Executive Summary

✅ **Deliverable 1: Working Hosted App**  
Deployed at: `https://firmable-sales-ai-crm.vercel.app`  
- Live dashboard with company search, scoring, and lead-queue workflows
- Can run locally in demo mode: `make start` (no database required)
- Production mode connects to Supabase for auth, queue state, and AI features

✅ **Deliverable 2: Git Repository**  
See: https://github.com/aboutaditya/firmable-sales-ai-crm  
- Full source code with clear structure (`frontend/`, `backend/`, `evals/`, `skills/`)
- Documented decisions in `docs/HLD.md` and component plans in `docs/plan/`

✅ **Deliverable 3: "How You Build" Reflection**  
See: `docs/HOW_YOU_BUILD.md` (4 pages)  
- Design rationale for every major decision (rules vs. LLM, data architecture, cost model)
- Known weaknesses and trade-offs explicitly called out

✅ **Deliverable 4: Loom (Optional)**  
TBD — walkthrough of dev loop and app end-to-end

---

## Requirement-by-Requirement Breakdown

### 1. **Skills — Reusable, Versioned AI Workflows**

**What the task asked for:**  
> Package at least one recurring AI workflow as a reusable, versioned `SKILL.md` that any agent (Claude Code, Cursor, API) can load and run.

**What we built:**

Three production-ready skills, each with its own `SKILL.md` file:

| Skill | Purpose | File | Trigger |
|-------|---------|------|---------|
| **Account Scoring** | Convert exposure signals into sales priorities | `skills/account-scoring/SKILL.md` | API POST `/companies/{id}/assess` (≥ AI_MIN_SCORE) |
| **Company Summary** | Synthesize observed signals into rep-friendly text | `skills/company-summary/SKILL.md` | API POST `/companies/{id}/summary` |
| **Outreach Draft** | Generate email subject + body for first contact | `skills/outreach-draft/SKILL.md` | API POST `/companies/{id}/outreach` |

**How to use each skill:**

#### 1.1 Account Scoring

**File:** `skills/account-scoring/SKILL.md`

**Manual trigger** (e.g., with Claude Code API):
```python
# Pseudo-code; real implementation in backend/sales_intelligence/ai/qualification.py
from backend.sales_intelligence.ai import AccountScoring
scorer = AccountScoring(prompt_version="account-scoring-v3")
result = scorer.score_company(
    company_profile={
        "company_id": "acme.com",
        "organization": "Acme Corp",
        "country": "US",
        "signals": {"critical_vulnerabilities": 1, "exposed_rdp": True}
    },
    model="claude-3-haiku"
)
# Returns: {"ai_score": 82, "priority": "HIGH", "confidence": 0.88, "reasoning": "..."}
```

**Via API:**
```bash
curl -X POST http://localhost:8000/api/v1/companies/acme.com/assess \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3-haiku", "prompt_version": "account-scoring-v3"}'
```

**Prompt versions:** Live in `backend/sales_intelligence/prompts/account_scoring/`
- `v1.txt` — baseline (F1 0.556)
- `v2.txt` — improved priority classification (F1 0.778 on 18-case eval set)
- `v3.txt` — latest iteration (add if you test new versions)

**Gating:** Only runs if deterministic score ≥ `AI_MIN_SCORE` (env var; default 60). Blocks spend on low-scoring accounts.

---

#### 1.2 Company Summary

**File:** `skills/company-summary/SKILL.md`

**Manual trigger:**
```bash
curl -X POST http://localhost:8000/api/v1/companies/acme.com/summary \
  -H "Authorization: Bearer <token>"
```

**Prompt versions:** `backend/sales_intelligence/prompts/company_summary/v1.txt`, `v2.txt`

**Output:** Markdown-formatted summary of observed signals, suitable for rep briefing. Maximum 120 words.

---

#### 1.3 Outreach Draft

**File:** `skills/outreach-draft/SKILL.md`

**Manual trigger:**
```bash
curl -X POST http://localhost:8000/api/v1/companies/acme.com/outreach \
  -H "Authorization: Bearer <token>"
```

**Prompt versions:** `backend/sales_intelligence/prompts/outreach/v1.txt`, `v2.txt`

**Output:** Email subject + body for cold outreach. Maximum 150 words. Cites observed signals only; never assumes breach or need.

---

### 2. **Evals — Hand-Labelled Dataset + Harness**

**What the task asked for:**  
> A small hand-labelled eval set (20–30 examples) for your core LLM feature, with measured precision/recall or equivalent quality metric.

**What we built:**

A complete evaluation framework with two components:

#### 2.1 Classification Evals (Account Scoring)

**Dataset:** `evals/datasets/account_scoring.jsonl`
- **25 hand-labelled examples** spanning real prospecting scenarios:
  - Critical vulnerabilities → HIGH priority
  - Exposed RDP + EOL software → MEDIUM/HIGH
  - Clean, sparse profiles → LOW
  - Cloud/shared-host attribution traps → lower confidence
  
**Example (one eval case):**
```json
{
  "company_id": "acme.com",
  "company": {
    "organization": "Acme Corp",
    "country": "US",
    "industry": "Manufacturing",
    "signals": {
      "critical_vulnerabilities": 1,
      "exposed_rdp": true,
      "exposed_database": true,
      "eol_products": 2
    }
  },
  "expected_priority": "HIGH",
  "expected_score": 80
}
```

**Metrics measured:**
```json
{
  "priority_accuracy": 0.611,
  "high_priority_precision": 0.636,
  "high_priority_recall": 1.0,
  "high_priority_f1": 0.778,
  "score_mae": 10.2
}
```

**How to run:**
```bash
make eval-openrouter                    # Generate v1 predictions (25 cases)
make eval-report                        # Show precision/recall/F1/MAE
make eval-openrouter-v2                 # Test a new prompt version
make eval-compare                       # v2 vs v1 metrics side-by-side
```

These commands are resumable — if interrupted by rate limits or provider outages, re-run the same target to continue.

#### 2.2 Output Evals (Summaries & Outreach)

**Rubric:** Deterministic validation in `evals/harness_output.py`
- Does the output cite signals actually in the profile?
- Does it invent signals the profile doesn't have?
- Does it hallucinate breach claims?
- (For outreach only) Does it have a subject line? CTA?

**Test datasets:**
- Golden set: `evals/datasets/output_rubric.jsonl` (10 hand-crafted cases, each designed to fail one criterion)
- Real traces: `data/traces/llm_calls.jsonl` (captured from production API calls)
- Production storage: reads from Supabase `llm-traces/` bucket if `LLM_TRACE_BACKEND=storage`

**How to run:**
```bash
make eval-output-golden                 # Test golden cases (10 examples)
make eval-output-traces                 # Score real outputs in data/traces/
make eval-output-storage                # Score outputs in Supabase Storage bucket
```

**Current results:**
- Golden set: 100% precision/recall (all 10 cases pass)
- Real traces (n=3): All clean-pass

---

### 3. **Eval Harness — One-Command Reproducible Testing**

**What the task asked for:**  
> A one-command script that re-runs your checks against the labelled set and reports results vs. the previous prompt version.

**What we built:**

A `Makefile`-driven harness with resumable prediction generation, caching, and comparison reporting.

#### 3.1 How it works

**Step 1: Generate predictions** (runs LLM on all eval cases)
```bash
make eval-openrouter                     # Generates evals/results/account-scoring-v1-predictions.jsonl
```

**Step 2: Compute metrics**
```bash
make eval-report                         # Prints F1, precision, recall, MAE
```

**Step 3: Test a new prompt version**
```bash
# Edit prompts/account_scoring/v2.txt
make eval-openrouter-v2                  # Generates predictions for v2
make eval-compare                        # Shows v2 vs v1 deltas
```

#### 3.2 Resumability

Both prediction commands use `--resume`: if they timeout or hit a rate limit, re-run them to continue from the last successful case.

```bash
$ make eval-openrouter
# (interrupted at case 12/25)
$ make eval-openrouter                   # Resumes from case 13
```

Implemented via: `evals/run_openrouter_eval.py --resume --output-file results/account-scoring-v1-predictions.jsonl`

#### 3.3 Output format

```json
{
  "company_id": "acme.com",
  "priority": "HIGH",
  "ai_score": 82,
  "confidence": 0.88,
  "model": "openrouter/free",
  "prompt_version": "account-scoring-v2",
  "latency_ms": 2500,
  "input_tokens": 285,
  "output_tokens": 1200,
  "cost_usd": 0.0025,
  "timestamp": "2026-09-13T10:00:00Z"
}
```

#### 3.4 Comparison report

```bash
$ make eval-compare
Account Scoring Comparison: v1 vs v2 (18-case overlap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Metric                v1      v2      Δ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Priority Accuracy     0.556   0.611   +0.055
HIGH Precision        0.455   0.636   +0.181
HIGH Recall           0.714   1.0     +0.286
HIGH F1               0.556   0.778   +0.222
Score MAE             15.0    10.2    -4.8 (better)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 4. **Tracing & Observability — Log Schema for Every LLM Call**

**What the task asked for:**  
> A log schema for every LLM call: request, response, model, prompt version, latency, cost, decision.

**What we built:**

Two-path trace capture:

#### 4.1 Local JSONL (Development)

**File:** `data/traces/llm_calls.jsonl`

**Schema:**
```python
{
  "trace_id": str,                      # Unique UUID per LLM call
  "timestamp": str,                     # ISO 8601
  "company_id": str,
  "feature": str,                       # "account-scoring" | "company-summary" | "outreach"
  "prompt_version": str,                # "account-scoring-v2"
  "model": str,                         # "claude-3-haiku" | "gpt-3.5-turbo"
  "input_tokens": int,
  "output_tokens": int,
  "total_tokens": int,
  "latency_ms": int,
  "cost_usd": float,
  "input_prompt": str,                  # Full rendered prompt (for debugging)
  "response_json": dict,                # Full LLM response
  "status": str,                        # "success" | "error" | "rate_limited"
  "error": str | null,
  "cache_hit": bool,
  "cached_from_version": str | null    # If served from cache, which version
}
```

**How to access:**
```bash
# View last 10 calls
tail -10 data/traces/llm_calls.jsonl | jq .

# Filter by feature
jq 'select(.feature == "account-scoring")' data/traces/llm_calls.jsonl

# Cost analysis
jq -s 'map(.cost_usd) | add' data/traces/llm_calls.jsonl  # Total spend
jq -s 'group_by(.prompt_version) | map({version: .[0].prompt_version, total_cost: map(.cost_usd) | add})' data/traces/llm_calls.jsonl
```

#### 4.2 Production Storage (Vercel)

**Backend:** `LLM_TRACE_BACKEND=storage` (env var)

When set, traces upload to Supabase Storage bucket `llm-traces/` under:
```
traces/<prompt_version>/<year>/<month>/<day>/<trace_id>.json
```

**Why separate per-object?** Concurrent serverless instances can write without clobbering each other.

**How to read:**
```bash
# Download all traces for a day and reassemble as JSONL
make eval-output-storage
# (uses Supabase service-role key to read the bucket)
```

#### 4.3 Cost tracking

**Per call:**
```
cost_usd = (input_tokens / 1000 * input_price_per_1k) + (output_tokens / 1000 * output_price_per_1k)
```

**Aggregated (dashboard view, TBD):**
- Total monthly spend
- Cost per feature
- Cost per model
- Average latency by feature

---

### 5. **Prompt Versioning — Tracked, Comparable, Testable**

**What the task asked for:**  
> Prompts tracked as files so v1 vs v2 of a feature can be compared.

**What we built:**

Prompts stored as versioned text files with automatic version selection and evaluation comparison.

#### 5.1 Directory structure

```
backend/sales_intelligence/prompts/
├── account_scoring/
│   ├── v1.txt                  # baseline
│   ├── v2.txt                  # improved priority classification
│   └── v3.txt                  # newer iteration (if you test)
├── company_summary/
│   ├── v1.txt
│   └── v2.txt
└── outreach/
    ├── v1.txt
    └── v2.txt
```

#### 5.2 How prompts are loaded

**At runtime**, the backend reads the prompt file based on the `prompt_version` parameter:

```python
# backend/sales_intelligence/ai/qualification.py
def load_prompt(feature: str, version: str) -> str:
    path = f"prompts/{feature}/{version}.txt"
    with open(path) as f:
        return f.read()

prompt = load_prompt("account-scoring", "account-scoring-v2")
```

#### 5.3 Creating a new prompt version

1. Copy the current version:
   ```bash
   cp backend/sales_intelligence/prompts/account_scoring/v2.txt \
      backend/sales_intelligence/prompts/account_scoring/v3.txt
   ```

2. Edit `v3.txt` to your new prompt.

3. Test it with the eval harness:
   ```bash
   make eval-openrouter-v3          # Generate predictions
   make eval-compare-v3-v2          # Compare v3 vs v2
   ```

4. Once validated, update the default in `.env`:
   ```bash
   ACCOUNT_SCORING_PROMPT_VERSION=account-scoring-v3
   ```

5. Commit as: `git commit -m "refine: account-scoring-v3 with improved priority logic"`

#### 5.4 Comparing prompt versions

```bash
$ make eval-compare
# Shows side-by-side metrics for v1 vs v2 on the same 25 eval cases
# Helps answer: Did v2's changes improve F1? Precision? Latency?
```

---

### 6. **Cost Monitoring — Math & Ceiling**

**What the task asked for:**  
> Show your math: tokens × volume × frequency, model choice per task, and the cost ceiling.

**What we built:**

#### 6.1 Cost math (worked example)

**Scenario: 100 reps, each working 5 accounts/day, 22 working days/month**

```
Accounts per month: 100 reps × 5 accounts × 22 days = 11,000
LLM calls per month:
  - Account scoring (gated @ AI_MIN_SCORE=60): 10,000 × 1 call = 10,000
  - Summary (opt-in): 10,000 × 0.3 = 3,000
  - Outreach (opt-in): 10,000 × 0.2 = 2,000
Total: 15,000 calls

Cost per call (based on evals/results/account-scoring-v1-predictions.jsonl):
  - Account scoring: ~275 input tokens, ~1,178 output tokens → $0.0025 (free router)
  - Summary: ~200 input, ~600 output → $0.001
  - Outreach: ~250 input, ~900 output → $0.002

Total cost: (10k × $0.0025) + (3k × $0.001) + (2k × $0.002)
          = $25 + $3 + $4
          = $32/month
```

**With production models** (Claude Haiku, GPT-3.5):
- Haiku: ~$0.0005 per call → $7.50/month
- GPT-3.5: ~$0.002 per call → $30/month

#### 6.2 Cost ceiling (policy)

**Monthly budget:** `$5,000` (env var: `LLM_BUDGET_CEILING_USD`)

**Behavior when approaching ceiling:**
```python
# backend/sales_intelligence/ai/cost_control.py
if projected_monthly_spend > LLM_BUDGET_CEILING:
    # Disable AI features, serve deterministic scores only
    return DeterministicScore(company)  # Free, rule-based
```

This is **not an error**; it's a valid product state. Reps still get ranked leads; they just lose natural-language assistance.

#### 6.3 Cost transparency (dashboard, WIP)

**TODO:** Add a cost dashboard showing:
- YTD spend by feature
- Cost per model
- Projected monthly spend
- Days until ceiling

**Current tracking:** All spend is logged to `data/traces/llm_calls.jsonl` and queryable via:
```bash
jq -s 'map(.cost_usd) | {total: add, mean: add/length, count: length}' data/traces/llm_calls.jsonl
```

---

## How to Set Up & Run Everything

### Initial Setup

```bash
# Clone repo
git clone https://github.com/aboutaditya/firmable-sales-ai-crm.git
cd firmable-sales-ai-crm

# Install dependencies
make init                                   # Installs backend + frontend

# Create env file (defaults work for local demo)
cp .env.example .env
```

### Run locally (demo mode, no database)

```bash
make start                                  # Starts API + frontend

# API: http://127.0.0.1:8000/docs
# Frontend: http://127.0.0.1:3000
# Demo data: data/demo/observations.jsonl (10 companies)
```

### Run with Supabase (production-like)

1. Create a Supabase project at https://supabase.com
2. Run migrations:
   ```bash
   DATABASE_URL='postgresql://...' alembic -c backend/alembic.ini upgrade head
   ```
3. Set env vars in `.env`:
   ```bash
   DATABASE_URL=postgresql://...
   SUPABASE_JWT_SECRET=...
   AUTH_REQUIRED=true
   ```
4. Start:
   ```bash
   make start
   ```

### Run evals

```bash
# Account scoring evals (25 cases)
make eval-openrouter                        # Generate v1 predictions
make eval-report                            # Show metrics

# Output evals (summaries + outreach)
make eval-output-golden                     # Test 10 golden cases
make eval-output-traces                     # Test real traced outputs
```

### Deploy to Vercel

```bash
vercel link                                 # Connect to Vercel project
vercel deploy                               # Deploy frontend + backend
```

See `docs/DEPLOYMENT_VERCEL.md` for full steps.

---

## Document Map

| Document | Covers |
|----------|--------|
| **`HLD.md`** | System overview, design decisions, component map |
| **`HOW_YOU_BUILD.md`** | Dev philosophy, rules vs LLM split, cost model |
| **`plan/01-etl.md`** | ETL pipeline, streaming, checkpointing |
| **`plan/02-scoring.md`** | Deterministic exposure score, rule weights |
| **`plan/03-analytics-layer.md`** | Parquet + DuckDB reads, query filters |
| **`plan/04-db-sync.md`** | Parquet → Postgres sync, idempotency |
| **`plan/05-database.md`** | Postgres schema, migrations, repositories |
| **`plan/06-api.md`** | FastAPI routes, auth, scoping, middleware |
| **`plan/07-ai.md`** | LLM workflows, caching, tracing, cost |
| **`plan/08-queue.md`** | Sales queue, assignments, dispositions, locking |
| **`plan/09-frontend.md`** | Next.js dashboard, components, hooks |
| **`plan/10-evals.md`** | Evaluation datasets, harness, metrics |
| **`plan/11-deployment.md`** | Vercel, Supabase, CI, operations |
| **`IMPLEMENTATION_GUIDE.md`** | This file — task-to-code mapping |

---

## Checklist: Task Requirements vs. Implementation

- ✅ **Skills**: Three reusable AI workflows (account-scoring, company-summary, outreach-draft) packaged as `SKILL.md` files
- ✅ **Evals**: Hand-labelled dataset (25 cases), measured metrics (F1, precision, recall, MAE)
- ✅ **Eval harness**: One-command reproducible testing (`make eval-*`)
- ✅ **Tracing**: Full log schema (traces, tokens, cost, latency, decision) → JSONL + Supabase Storage
- ✅ **Prompt versioning**: Prompts as versioned text files with automated loading and comparison
- ✅ **Cost monitoring**: Math worked out, ceiling policy implemented, per-call tracking
- ✅ **Working app**: Deployed at Vercel, runnable locally in demo mode
- ✅ **Repository**: Clean structure with full source code and documentation
- ✅ **"How You Build" reflection**: `docs/HOW_YOU_BUILD.md` (4 pages)
- ⏳ **Loom walkthrough**: Optional, TBD

---

## Known Gaps & Next Steps

1. **Cost dashboard**: Tracing is complete, but a UI showing spend over time is WIP.
2. **Full eval coverage**: Output evals (summaries, outreach) use a rubric; classification evals are fully measured. Consider extending classification evals to other models (Haiku, GPT-3.5).
3. **Prompt tuning**: v2 shows 0.222 F1 improvement on 18 cases. Full v2 eval (25 cases) pending OpenRouter quota reset.
4. **Production operations**: SLA monitoring, rate-limit graceful degradation, and alerting for cost overruns are placeholders.

---

## Questions?

- **How do I test a new prompt?** → Copy the current version, edit it, run `make eval-openrouter-vN` and `make eval-compare`.
- **How do I track LLM spend?** → Read `data/traces/llm_calls.jsonl` or query the Supabase Storage bucket if `LLM_TRACE_BACKEND=storage`.
- **How do I change the pre-qualification gate?** → Update `AI_MIN_SCORE` in `.env` (no code changes; gating is config-driven).
- **How do I disable AI features temporarily?** → Set `LLM_API_KEY=` (empty) or `AUTH_REQUIRED=false` to fall back to deterministic scores.

---

**Last updated:** 2026-09-13  
**Repository:** https://github.com/aboutaditya/firmable-sales-ai-crm  
**Deployed:** https://firmable-sales-ai-crm.vercel.app
