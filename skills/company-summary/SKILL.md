# Company Summary Skill

## Purpose

Generate a concise research summary of a company's observed security posture for internal sales team review. The summary is **for salespeople, not for sending to prospects** — it's the internal brief.

## Trigger

Run when:
1. A sales rep opens a company detail page (real-time).
2. A company is added to a rep's queue.
3. An analyst wants to research an account before outreach.

Do not gate on prequalification threshold; provide context for accounts at any score level.

## Inputs

- **Company profile**: domain, organization, country, city, industry, employee count, organization size.
- **Observed signals**: vulnerability counts (total and critical), exposed service flags (RDP/database/Exchange/SSH), EOL product count, asset counts, signal dates, confidence/accuracy.
- **Deterministic score**: exposure score (0–100), score_version.
- **Prompt template**: `backend/sales_intelligence/prompts/company_summary/*.txt` (selected by `prompt_version` at runtime).

## Output

Return plain text, max **120 words**. Structure:

```text
[Company name + brief context]

[Key observed signals + what they mean for sales]

[Risk level + confidence note]
```

**Requirements:**
- Opens with company name, location, industry, and size (if known).
- Leads with the strongest observed signal(s) in sales language.
- Explains why each signal matters for a cybersecurity sales conversation (e.g., "EOL Exchange is a target for ransomware").
- Notes confidence or data gaps if profile is sparse or signals are stale.
- No fabricated details: contact names, org structure, initiatives, or unobserved vulnerabilities.
- No breach claims or buying intent inferences.

## Rules and validation

1. **Use only supplied data.** No external research or enrichment beyond the profile.
2. **Sales perspective.** Translate technical signals into sales relevance: "Why should this sales rep prioritize this account?"
3. **Lead with strength.** Start with the clearest signal; omit weak or stale observations.
4. **Confidence note.** If data is sparse (few signals, old dates, cloud/shared-host attribution), say so.
5. **No breach claims.** "Exposed database" ✓; "Compromised database" ✗. Observed facts, not conclusions.
6. **No tone.** Neutral, analytical voice. Not promotional or alarmist.
7. **Length.** Max 120 words; concise is better.
8. **Tracing.** Persist model, prompt_version, input/output tokens, latency_ms, cost_usd, and trace_id.

## Integration seams

1. **LLM provider** — renders prompt with `{{company_profile}}` interpolation; returns plain-text summary.
2. **Output parser** — validates word count, checks for required structural elements (context, signals, confidence note).
3. **UI integration** — displayed in the company detail view, refreshable on demand.
4. **Trace sink** — records model, prompt_version, tokens, cost, and output for cost tracking and output-quality evals.
5. **Caching** — cache by (company_id, prompt_version) to avoid regenerating on page reload.

## Worked example

**Input:**
```json
{
  "company_id": "dataflow-analytics.com",
  "organization": "DataFlow Analytics",
  "country": "US",
  "city": "Seattle",
  "industry": "SaaS",
  "employee_count": 120,
  "signals": {
    "critical_vulnerabilities": 0,
    "vulnerabilities": 15,
    "exposed_rdp": false,
    "exposed_database": true,
    "exposed_exchange": false,
    "eol_products": 2,
    "assets": 38
  },
  "deterministic_score": 62,
  "score_version": "v1",
  "signal_dates": {
    "last_scan": "2026-09-10"
  }
}
```

**Expected output:**
```text
DataFlow Analytics is a 120-person SaaS company in Seattle. Shodan shows an externally exposed database instance and two end-of-life products (likely in use). This combination is valuable for database breach campaigns. The database exposure alone is worth a conversation; EOL products amplify the risk profile. Data is recent (scanned 2026-09-10). High confidence, medium urgency.
```

**Why this works:**
- Opens with company identity (name, size, location, industry).
- Leads with the clearest signals (exposed database, EOL products).
- Explains sales relevance ("valuable for breach campaigns").
- Specifies observation dates and confidence.
- No breach claims; no invented facts.
- 120 words exactly; crisp and actionable.

## Cost & scaling

- **No prequalification gate:** Run on all accounts (cheap classification).
- **Caching:** Cache by (company_id, prompt_version) → low cost even if rendered on page load.
- **Model selection:** Use cheapest model available (e.g., `gpt-3.5-turbo`, `claude-3-haiku`) — this is pure classification, not judgment.
- **Token efficiency:** Target ≤250 input tokens, ≤120 output tokens.
- **Batch generation:** Summaries can be pre-generated for all queued accounts and cached, reducing latency on open/load.
