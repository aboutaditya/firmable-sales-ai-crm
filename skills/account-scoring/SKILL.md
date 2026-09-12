# Account Scoring Skill

## Purpose

Turn a deterministic company exposure profile into a sales-ready qualification decision. This skill explains observed evidence; it must not invent a breach, contact, business initiative, purchase intent, or company fact.

## Trigger

Run **after** deterministic prequalification, normally when exposure score ≥ `AI_MIN_SCORE` threshold. Do not call for every raw observation or accounts that fail the gate.

## Inputs

- **Company profile**: `company_id`, domain, organization, country, city, industry, employee count (when available).
- **Observed signals**: asset/vulnerability counts, critical vulnerability count, EOL product count, exposed service flags (RDP/database/Exchange), security tags, signal dates.
- **Deterministic score**: exposure score (0–100) and `score_version`.
- **Prompt template**: `backend/sales_intelligence/prompts/account_scoring/*.txt` (selected by `prompt_version` at runtime).

## Output

Return only valid JSON:

```json
{
  "ai_score": 0-100,
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "confidence": 0.0-1.0,
  "reasoning": "One-sentence evidence-based rationale"
}
```

**Semantics:**
- `ai_score`: Qualification strength (not a replacement for deterministic score).
- `priority`: Sales urgency based on observed signals alone.
- `confidence`: Calibrated 0–1; lower when profile is sparse, attribution uncertain, or data is stale.
- `reasoning`: Cite the strongest 1–2 observed signals; distinguish facts from uncertainty.

## Rules and validation

1. **Use only supplied data.** No external research, inferences, or invented facts.
2. **No breach claims or buying intent.** "Exposed RDP" is evidence; "you were hacked" or "you need security" is not.
3. **Confidence-aware.** Sparse profiles (few signals, old data, cloud attribution) → lower confidence.
4. **Decision clarity.** HIGH requires multi-signal or critical exposure; LOW is minimal/sparse; MEDIUM is the uncertain middle.
5. **Schema validation.** Score in [0–100], priority in enum, confidence in [0–1], reasoning non-empty and <200 chars.
6. **Tracing.** Persist model, prompt_version, input/output tokens, latency_ms, cost_usd, and trace_id for every call (success or failure).

## Integration seams

The skill is transport- and provider-agnostic. Integrate via:

1. **LLM provider** — renders prompt with `{{company_profile}}` interpolation; returns schema-valid JSON.
2. **Input validator** — ensures company profile has required fields and signal names match scoring config.
3. **Output validator** — enforces schema, ranges, and non-empty reasoning before persistence.
4. **Trace sink** — records model, prompt_version, tokens, cost, decision, and trace_id to JSONL or database for cost tracking and evals.
5. **Prequalification gate** — guards LLM invocation to avoid spend below the threshold.

## Worked example

**Input:**
```json
{
  "company_id": "acme.com",
  "organization": "Acme Corp",
  "country": "US",
  "industry": "Manufacturing",
  "employee_count": 500,
  "deterministic_score": 75,
  "score_version": "v1",
  "signals": {
    "critical_vulnerabilities": 1,
    "vulnerabilities": 12,
    "exposed_rdp": true,
    "exposed_database": true,
    "eol_products": 2,
    "assets": 45
  }
}
```

**Expected output:**
```json
{
  "ai_score": 82,
  "priority": "HIGH",
  "confidence": 0.88,
  "reasoning": "Critical vulnerability + exposed RDP/database + EOL software; multi-signal evidence but attribution is external-only."
}
```

**Reasoning**: HIGH because critical vuln + 2 exposed services + EOL products meet the multi-signal HIGH threshold. Confidence 0.88 (not 0.95) because exposures are observable from the internet but internal context is unknown.

## Cost & scaling

- **Trigger guard:** Pre-qualification gate blocks low-scoring accounts → avoids spend on obvious rejects.
- **Caching:** Cache by (company_id, prompt_version) → no recomputation for the same account under the same prompt.
- **Model selection:** Cheapest model that passes evals (e.g., `gpt-3.5-turbo` or `claude-3-haiku`) for classification; stronger tier reserved for outreach.
- **Token efficiency:** Target ≤300 input tokens, ≤150 output tokens per call; verbose models (>1000 tokens) are an upper bound on cost.
