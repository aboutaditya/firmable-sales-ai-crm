# Structural Thinking: Sales Intelligence Platform Design Rationale

## Problem Statement

A cybersecurity sales team has thousands of companies in the market. **The core challenge:** Which companies actually need our help *right now*, and how do we reach them first?

This is not a general market database problem. It's a **signal interpretation problem**: 
- Raw observations (exposed services, vulnerabilities) are everywhere
- But what matters is *why now* and *why this company*
- Sales reps have finite time; they need the best leads ranked

## Core Insight: Two Systems, Not One

Most sales platforms conflate **what we know** with **what we recommend**. We deliberately separated them:

1. **Observation system** (deterministic, rule-based)
   - What signals do we see? (exposed RDP, critical CVE, EOL software)
   - Can we measure these exactly? Yes → encode as rules
   - Do we need a model? No → keep it fast, cheap, auditable

2. **Qualification system** (AI-assisted, judgement-based)
   - Given these observations, how urgent is this account?
   - Does exposure = need to buy? No → that's a judgement call
   - Does an account have buying intent? Unknown → be honest about confidence

**Why this split?**
- Sales teams trust explainability. "We found RDP exposed" is explainable. "The model says HIGH" is not.
- One system fails independently. If the LLM is down, deterministic scores still work.
- Cost control is clear: LLM only runs on pre-qualified accounts.

## Data Architecture Decision: Analytical ≠ Application

We chose to **never load raw data into the application database**. Instead:

```
Raw observations → Parquet (analytical) → filtered copy → PostgreSQL (app)
```

**Why not just PostgreSQL everywhere?**

| Approach | Strength | Weakness |
|----------|----------|----------|
| **Parquet only** | Fast reads, cost-free for large volumes | No workflow state, no auth |
| **PostgreSQL only** | Auth, transactions, workflow state | Expensive for 1M+ rows, slow analytical queries |
| **Both (our choice)** | Analytics fast, workflow possible | Sync complexity, double storage |

**The tradeoff:** Parquet scales to millions of observations cheaply (DuckDB reads, no indexes). PostgreSQL holds only the "hot" sales-relevant subset (1K–10K companies) with full ACID, auth, queue logic.

**Why we chose this:** 
- Raw observations double every quarter (more data sources, more coverage)
- PostgreSQL would become a bottleneck (index bloat, backup size, query latency)
- Sync is simple (idempotent upsert by score_version + company_id)
- Separation of concerns: analytics team can reload Parquet, sales team's queue is unaffected

## Scoring Model: Rule-Based, Not ML

We scored companies deterministically: 0–100 based on observed signals with configurable weights.

**Could we use ML?** Yes. Should we?

| Approach | Strength | Weakness |
|----------|----------|----------|
| **Rules (our choice)** | Explainable, fast, no retraining | Brittle to new signal types, can't learn from reps' feedback |
| **ML classifier** | Learns from feedback, adapts | Black-box, needs labeled data, operational burden |

**The insight:** Sales reps give us *implicit* feedback (they ignore some leads, engage with others), but not *explicit* labels. ML without labeled data is just overfitting to noise.

**Why rules:** 
- We can defend "why is this account HIGH" (has critical vuln + exposed DB + EOL software)
- Rules degrade gracefully (add a new signal type, tweak the weight)
- Reps can override via the queue (they claim what they want; rules are just ranking)

## LLM Strategy: Judgement, Not Facts

Three LLM tasks in the app:
1. **Account-scoring** — "Is this worth pursuing?" (Judgement)
2. **Company summary** — "What should a rep know?" (Synthesis)
3. **Outreach draft** — "What should we say?" (Communication)

Notice: **None of these are fact-finding.**

**Why?** LLMs hallucinate. A rep reading "we detected a breach" in an email from our system, only to find out we guessed, damages trust forever.

**So instead:**
- Scoring: "Here's the evidence. I'm 85% confident this is HIGH priority." (Transparent confidence)
- Summary: "We observed RDP, database, and EOL software. This is worth a conversation." (Cite observed signals only)
- Outreach: "We noticed your RDP is exposed. Would a review be useful?" (Fact-based, not assumptive)

**The discipline:** Every LLM output must be traceable to supplied data. If we don't have it in the company profile, we don't claim it.

## Trigger Design: Gate Before Spend

LLM calls happen only after deterministic pre-qualification. This is not an optimization; it's a **cost containment rule**.

```
Score < AI_MIN_SCORE  →  skip LLM, serve deterministic score
Score ≥ AI_MIN_SCORE  →  run LLM qualification
```

**Why gate?**
- Not all accounts deserve LLM time (why spend $0.005 on a LOW-score account?)
- Ops team can adjust the gate without code changes (config value)
- Failure mode is graceful (low-score accounts still get ranked, just faster)

**The math:**
- 100K companies → 10K qualify (≥ threshold)
- 10K × $0.005 per qualification = $50 per sweep
- Daily sweeps → $1,500/month
- With a $5K monthly LLM budget: 3× coverage, A/B test prompts, retries

## Caching Strategy: By (Company, Feature, Prompt)

We cache LLM results to avoid recomputation:

```
cache_key = (company_id, feature, prompt_version)
Example: ("acme.com", "account-scoring", "account-scoring-v2")
```

**Why this granularity?**
- Same company, different prompt → recompute (we want to test v2 vs v1)
- Same prompt, different company → no cache (independent results)
- Cache survives code restarts (persistent in database)

**Trade-off:** Cache hit rate is ~70% (reps revisit the same accounts). But if we change the prompt, old cached results are stale. We accept that; prompt version in the cache key makes staleness explicit.

## Role-Based Access: Defense in Depth

Three roles: `admin`, `sales_manager`, `sales_rep`

| Role | Can do | Cannot do |
|------|--------|-----------|
| Admin | Manage users, override thresholds, bulk assign | N/A |
| Manager | Browse all companies, assign to reps, see queue status | Directly work a lead; change own preferences |
| Rep | Work their assigned queue, call activity, see own insights | Browse all companies; assign themselves |

**Why this split?**
- Reps focus on their leads (one-lead queue); no distraction
- Managers allocate work (territory, industry); see team throughput
- Admins control cost gates (AI_MIN_SCORE) and user access

**The insight:** A rep with access to all 10K companies would waste time browsing. Better: "Here's your top 5 for today; work them in order."

## Prompt Versioning: Version Everything

Prompts live in files (`v1.txt`, `v2.txt`, `v3.txt`). Every LLM call logs which version ran.

**Why?**
- Trace sink asks: "v1 gave F1 0.556, v2 gives 0.778—which explains the change?"
- Historical queries: "All v1 decisions from Sept 1–10" (if something broke, we can rerun)
- A/B testing: Gradual rollout (50% v1, 50% v2; compare quality)

**The discipline:** Never change a prompt in-place. Always create v{n+1}.

## Evaluation Framework: Measure What You Care About

We built evals around **two dimensions:**

1. **Classification accuracy** (account-scoring)
   - Metric: precision, recall, F1 on priority prediction
   - Why: A false HIGH wastes rep time; a false LOW misses revenue

2. **Claim accuracy** (summary, outreach)
   - Metric: evidence-rubric (does the output match the profile?)
   - Why: We don't care if the summary is beautifully written if it hallucinates signals

**Not measured:**
- Model latency (acceptable up to 5s)
- User satisfaction (not enough data)
- ROI (too early; no real outreach yet)

**Why this focus?** Because we can measure it, it's deterministic, and it drives deployment decisions.

## Multi-User Queue: Simple Locking

Sales reps claim one lead at a time from the queue:

```sql
SELECT company_id FROM companies 
WHERE assigned_rep_id IS NULL AND score >= rep.min_score
ORDER BY score DESC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

**Why `SKIP LOCKED`?**
- Two reps hit simultaneously → one gets the lock, the other skips to the next row
- No race condition; no thundering herd
- Reps always get a result (even if it's the 100th-best, it's theirs)

**Alternative:** Distributed queue (Redis, RabbitMQ) → overkill for this volume; Postgres row locks are simpler.

## Cost Model: Three Tiers, One Budget

We sized LLM spend for three scenarios:

| Rep count | Monthly calls | Total cost | Model |
|-----------|---------------|-----------|-------|
| 10 reps | ~5K (account-scoring + summary) | ~$25 | Cheap classifier (Haiku) |
| 50 reps | ~25K | ~$125 | Haiku for scoring, Sonnet for outreach |
| 100+ reps | ~50K+ | >$250 | Upgrade or implement output caching |

**The ceiling:** $5K/month. If projected spend exceeds it, the app serves deterministic scores only (not an error; a valid product state).

**Why this thinking?** 
- Sales teams need predictable budgets
- LLM is a utility, not a core feature (rules + humans still work)
- Transparency: reps see "AI features unavailable; using rule-based scores" if we hit the cap

## Known Structural Weakness: Attribution

**The problem:** A shared hosting provider like AWS has millions of customers. We observe an exposed service at `12.34.56.78`. Is it *your company's* exposure, or a thousand others?

**Our approach:** Tag signal sources (Shodan, SecurityTrails, etc.) and surface uncertainty in confidence scores. But we don't solve it.

**Why not?** 
- True solution requires WHOIS + SSL certificates + DNS records (expensive, slow)
- Better solution: Let reps verify ("Is that actually your IP?")
- Our job: surface the signal with confidence, not validate it

**Structural insight:** Some problems are better solved by humans at point-of-action, not by the system upfront.

---

## Design Principles Summary

1. **Separate observation from qualification.** What we see ≠ what we recommend.
2. **Determinism first.** Rules are the default; LLM is for judgement.
3. **Transparency over cleverness.** Traceable decisions > black-box optimization.
4. **Graceful degradation.** If LLM fails, the system still works (deterministic scores + human queue).
5. **Version everything.** Prompts, scores, datasets — make the history auditable.
6. **Gate before spend.** Only invoke expensive operations on qualified inputs.
7. **Simple > sophisticated.** Row locks > distributed queues; rules > ML (for now).

These principles guided every decision: architecture, LLM use, eval strategy, and role design.
