# Outreach Draft Skill

## Purpose

Draft a first-touch email that introduces a security observation to a prospect in a credible, evidence-led way. The draft is **always reviewable by a salesperson before send** — never auto-dispatch.

## Trigger

Run after:
1. Account has passed deterministic prequalification (exposure score ≥ threshold).
2. Account-scoring skill has returned a priority (HIGH/MEDIUM/LOW).
3. Sales rep selects the account for outreach.

Do not run for LOW-priority accounts or those that fail prequalification.

## Inputs

- **Company profile**: domain, organization, country, industry, employee count.
- **Observed signals**: vulnerability counts, critical count, exposed service flags (RDP/database/Exchange/SSH), EOL products, asset counts, signal dates.
- **Deterministic score**: exposure score (0–100), score_version.
- **Account scoring result** (optional): `priority`, `ai_score`, `confidence` from the account-scoring skill.
- **Prompt template**: `backend/sales_intelligence/prompts/outreach/*.txt` (selected by `prompt_version` at runtime).

## Output

Return plain text with two parts:

```text
Subject: [specific, evidence-based subject line]

Body: [1–3 paragraphs, max 150 words total, conversational tone]
```

**Requirements:**
- Subject line is specific and mentions one concrete observed signal (not generic like "Security Question").
- Body leads with the strongest observed signal in plain language.
- Body acknowledges the company may not know they're exposed ("We maintain a database...").
- Body offers a low-friction next step (call, benchmark review, risk assessment).
- No fabricated details: contact names, breach claims, products, initiatives, or unobserved vulnerabilities.
- Tone is professional but not stiff; assume the reader is busy.

## Rules and validation

1. **Lead with evidence.** Name one concrete signal: "Your RDP service is externally accessible" not "Your security posture."
2. **Credibility first.** Explain why you know this and why it matters without overstating.
3. **No breach claims.** "Exposed service" ✓; "You were hacked" ✗. "Not evidence of compromise" ✓.
4. **No invented details.** No contact names, product pitches, deployment assumptions, or unobserved signals.
5. **Clear CTA.** End with one low-friction invitation: "Would a 15-min call be useful?" or "Should we schedule a quick review?"
6. **Length.** Subject line + body ≤ 150 words total; body ≤ 120 words.
7. **Tracing.** Persist model, prompt_version, input/output tokens, latency_ms, cost_usd, and trace_id for all calls.

## Integration seams

1. **LLM provider** — renders prompt with `{{company_profile}}` and `{{account_scoring_result}}` interpolation; returns plain-text output.
2. **Output parser** — extracts subject line (first line after "Subject:") and body; validates word count and CTA presence.
3. **Human gate** — sales rep reviews and approves before sending via email, LinkedIn, or phone.
4. **Trace sink** — records model, prompt_version, tokens, cost, and output for cost tracking and output-quality evals.
5. **Caching** — cache by (company_id, prompt_version) to avoid regenerating the same draft.

## Worked example

**Input:**
```json
{
  "company_id": "widgetco.com",
  "organization": "Widget Manufacturing Inc.",
  "country": "US",
  "industry": "Manufacturing",
  "employee_count": 250,
  "signals": {
    "critical_vulnerabilities": 0,
    "vulnerabilities": 8,
    "exposed_rdp": true,
    "exposed_database": false,
    "eol_products": 1,
    "assets": 22
  },
  "account_scoring": {
    "priority": "MEDIUM",
    "ai_score": 58,
    "confidence": 0.75
  }
}
```

**Expected output:**
```text
Subject: Question about your externally-accessible RDP service

Hi there,

We monitor external infrastructure exposure and noticed an RDP service accessible from the internet associated with Widget Manufacturing. We're not suggesting any compromise—just flagging it in case it's unintentional.

A quick benchmark of your external exposure vs. similar manufacturers in your region might be useful. Would a 15-minute call work?

Thanks,
[Sales rep]
```

**Strengths of this output:**
- Subject line is specific (mentions RDP, not generic "question").
- Opens with evidence ("RDP service...from the internet") in plain language.
- Credibility statement ("We monitor external...") without overstating.
- Reassurance ("We're not suggesting...") prevents alarm and breach rumors.
- CTA is specific and low-friction ("15-minute call").
- No invented details: no contact name, no assumed products, no claims of intent.

## Cost & scaling

- **Trigger guard:** Run only on HIGH/MEDIUM accounts (not LOW) to avoid spend on weak signals.
- **Caching:** Cache by (company_id, prompt_version) → no recomputation.
- **Model selection:** Outreach generation is more sensitive than classification; use a stronger model (e.g., `gpt-4-turbo` or `claude-3-sonnet`) than account-scoring.
- **Token efficiency:** Target ≤300 input tokens, ≤150 output tokens; monitor for verbose models.
- **Human gate:** Every draft is reviewed before send — this is not a silent background process.
