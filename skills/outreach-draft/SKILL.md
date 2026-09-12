# Outreach Draft Skill

Version: `outreach-v1`

## Purpose

Draft a concise first-touch message that gives a salesperson a credible next
step based on observed security evidence. The draft is a reviewable suggestion,
not an automated send.

## Trigger

Run after an account is selected for outreach and has passed deterministic
prequalification. A salesperson should review the draft before sending it.

## Inputs

- Company profile and domain.
- Observed security signals and deterministic exposure score.
- Optional validated account-scoring result.
- Prompt file: `prompts/outreach/v1.txt`.
- Model and cost configuration.

## Output

Return a subject line and body under 150 words. Do not include a fabricated
contact name, breach, initiative, product claim, or unobserved vulnerability.

## Rules and validation

1. Lead with one concrete observed signal.
2. Explain business relevance cautiously; do not state that compromise occurred.
3. Say when evidence is incomplete or stale.
4. End with a low-friction call to action.
5. Keep the output concise and suitable for human review.
6. Persist model, prompt version, token usage, latency, cost, and trace ID.

## Dependencies

- `prompts/outreach/v1.txt`
- `sales_intelligence.backend.ai.content_service.AIContentService`
- A trace sink for successful and failed calls.

## Worked invocation

Input:

```json
{
  "company_id": "acme.com",
  "organization": "Acme Corp",
  "security_score": 75,
  "critical_vulnerability_count": 1,
  "exposed_rdp": true,
  "exposed_database": true,
  "eol_product_count": 1
}
```

Invocation:

```text
Draft outreach-v1 for Acme Corp using only the supplied profile and observed
signals. Mention one evidence-backed finding and request a short conversation.
```

Expected shape:

```text
Subject: Question about an externally exposed Acme service

Hi there — we noticed an externally exposed RDP service associated with Acme,
alongside an observed database exposure. This is not evidence of compromise,
but it may be useful to validate whether those services are intentional and
protected. Would a brief review of the external attack surface be useful?
```
